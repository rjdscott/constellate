"""Memgraph graph adapter — Hydra's graph plane (ADR 0005).

Same doubled-edge convention as Kuzu/CTE/AGE: every logical edge is written in
both directions at upsert time, so traversal is plain directed Cypher and the
graph still behaves undirected for expansion (m1 -> tag <- m2 must reach m2).
One label (configurable), a string `key` holding the prefixed id, one `REL`
type carrying `edge_type` + `weight`.

Unlike AGE, Memgraph has real variable-length patterns, so stage 1 is a single
`[:REL*1..H]` match aggregating in-engine with the reference tie-break
(hops ASC, support DESC, dst ASC) — that ordering is what RRF consumes. Stage 2
scores the best-weight path at the winner's min hop count, one query per hop
group; same metadata semantics as the CTE adapter.

Caveat — trail vs walk: Cypher's relationship-uniqueness rule forbids reusing
the same *directed* relationship twice inside one path, while the CTE adapter's
self-joins are unrestricted walks. Because edges are doubled, an out-and-back
step traverses two distinct relationships, so 1- and 2-hop results are
identical — a 432-case differential against CteGraph (random graphs, multi-seed,
type filters) matched exactly at max_hops 1-2. At 3 hops a walk that revisits
one direction of an edge (a->b->a->b) inflates CTE `support` by a few counts
and can flip a near-tie between two candidates at the same hop count; that hit
1 of 144 three-hop cases. Service.explain defaults to 2 hops; no conformance
case exercises 3.
"""

import asyncio
from collections.abc import Iterable, Sequence
from typing import Any

from neo4j import AsyncDriver

from constellate.core.types import Candidate, Edge, ItemId

MAX_HOPS = 3  # service.explain caps at 3; the variable-length match goes no deeper


class MemgraphGraph:
    def __init__(
        self, driver: AsyncDriver, *, label: str = "Node", item_prefix: str = "item:"
    ) -> None:
        self._driver = driver
        self._label = label
        self._prefix = item_prefix

    async def ensure_schema(self) -> None:
        """Label+property index on the traversal anchor. Idempotent in Memgraph."""
        await self._run(f"CREATE INDEX ON :{self._label}(key)")

    def close(self) -> None:
        # Service.close() is sync but AsyncDriver.close() is a coroutine: inside a
        # running loop we can only schedule it (task kept so it isn't GC'd mid-flight);
        # outside one, asyncio.run drives it to completion.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._driver.close())
        else:
            self._closing = loop.create_task(self._driver.close())

    async def _run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        async with self._driver.session() as session:
            result = await session.run(query, **params)
            return await result.data()

    async def upsert_edges(self, edges: Iterable[Edge]) -> None:
        rows = [
            {"src": src, "dst": dst, "t": e.edge_type, "w": e.weight}
            for e in edges
            for src, dst in ((e.src, e.dst), (e.dst, e.src))
        ]
        if not rows:
            return
        await self._run(
            f"UNWIND $rows AS row"
            f" MERGE (a:{self._label} {{key: row.src}})"
            f" MERGE (b:{self._label} {{key: row.dst}})"
            f" MERGE (a)-[r:REL {{edge_type: row.t}}]->(b)"
            f" SET r.weight = row.w",
            rows=rows,
        )

    async def expand(
        self,
        seeds: Sequence[ItemId],
        max_hops: int,
        limit: int,
        edge_types: Sequence[str] | None = None,
    ) -> list[Candidate]:
        if not seeds:
            return []
        hops = min(max_hops, MAX_HOPS)
        seed_nodes = sorted(f"{self._prefix}{s}" for s in seeds)
        types = list(edge_types) if edge_types else None
        type_pred = " AND all(r IN rs WHERE r.edge_type IN $types)" if types else ""

        ranked = await self._run(
            f"MATCH (s:{self._label})-[rs:REL*1..{hops}]->(d:{self._label})"
            f" WHERE s.key IN $seeds AND d.key STARTS WITH $prefix"
            f" AND NOT d.key IN $seeds{type_pred}"
            f" WITH d.key AS dst, size(rs) AS len"
            f" RETURN dst, min(len) AS hops, count(*) AS support"
            f" ORDER BY hops ASC, support DESC, dst ASC LIMIT $limit",
            seeds=seed_nodes,
            prefix=self._prefix,
            limit=limit,
            types=types,
        )
        if not ranked:
            return []
        order = [r["dst"] for r in ranked]
        by_hops: dict[int, list[str]] = {}
        for r in ranked:
            by_hops.setdefault(r["hops"], []).append(r["dst"])

        best: dict[str, Candidate] = {}
        for h, winners in by_hops.items():
            for row in await self._best_paths(seed_nodes, winners, h, types):
                dst, score = row["dst"], row["w"] / h
                if dst not in best or score > best[dst].score:
                    best[dst] = Candidate(
                        item_id=int(dst.removeprefix(self._prefix)),
                        score=score,
                        source="graph",
                        path=_interleave(row["ns"], row["ts"]),
                        hops=h,
                    )
        return [dst_c for dst in order if (dst_c := best.get(dst)) is not None]

    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None:
        src, dst = f"{self._prefix}{a}", f"{self._prefix}{b}"
        for h in range(1, min(max_hops, MAX_HOPS) + 1):
            rows = await self._best_paths([src], [dst], h, None)
            if rows:
                return _interleave(rows[0]["ns"], rows[0]["ts"])
        return None

    async def _best_paths(
        self, seed_nodes: list[str], winners: list[str], hops: int, types: list[str] | None
    ) -> list[dict[str, Any]]:
        """One strongest path (by weight product) per winner at exactly `hops`."""
        type_pred = " AND all(r IN rs WHERE r.edge_type IN $types)" if types else ""
        return await self._run(
            f"MATCH p = (s:{self._label})-[rs:REL*{hops}..{hops}]->(d:{self._label})"
            f" WHERE s.key IN $seeds AND d.key IN $winners{type_pred}"
            f" WITH d.key AS dst, s.key AS src,"
            f" reduce(w = 1.0, r IN rs | w * r.weight) AS w,"
            f" [n IN nodes(p) | n.key] AS ns, [r IN relationships(p) | r.edge_type] AS ts"
            f" ORDER BY w DESC, src ASC"
            f" WITH dst, collect({{w: w, ns: ns, ts: ts}})[0] AS best"
            f" RETURN dst, best.w AS w, best.ns AS ns, best.ts AS ts",
            seeds=seed_nodes,
            winners=winners,
            types=types,
        )


def _interleave(nodes: list[str], types: list[str]) -> list[str]:
    """(n0..nh, t1..th) → [n0, t1, n1, t2, n2, ...] path."""
    path = [nodes[0]]
    for edge_type, node in zip(types, nodes[1:], strict=True):
        path.extend((edge_type, node))
    return path
