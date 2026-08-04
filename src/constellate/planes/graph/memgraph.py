"""Memgraph graph adapter — Hydra's graph plane (ADR 0005).

Same doubled-edge convention as Kuzu/CTE/AGE: every logical edge is written in
both directions at upsert time, so traversal is plain directed Cypher and the
graph still behaves undirected for expansion (m1 -> tag <- m2 must reach m2).
One label (configurable), a string `key` holding the prefixed id, one `REL`
type carrying `edge_type` + `weight`.

Three planner lessons, all paid for on the 58k-node / 1.68M-edge graph:

1. *Anchor with UNWIND + a property map, never `WHERE s.key IN $seeds`.* On the
   `IN` form Memgraph ignores the `:Node(key)` index entirely — the plan is
   ScanAll(d) -> Expand into s -> Filter on s.key, reading ~962k edges and
   burning 65% of its time in that filter (159ms for a *flat 1-hop*, 117ms of it
   the filter). `UNWIND $seeds AS sk MATCH (s:Node {key: sk})` compiles to
   ScanAllByLabelPropertyValue per seed and the ScanAll disappears.
2. *Unroll hops into flat chains; no variable-length patterns.* `[:REL*1..2]`
   from 10 seeds through genre/tag hubs ran >312s at 100% of one core before it
   was killed — per-path DFS materialisation on top of the ScanAll above. The
   equivalent flat chain `(s)-[r1]->(m1)-[r2]->(d)` aggregating in-engine was
   629ms on the same seeds. So hops are unrolled exactly like the CTE adapter's
   self-joins (`_hop_sql`), one aggregating branch per hop count.
3. *One MATCH clause per hop, not one pattern.* Relationship uniqueness is
   scoped to a single MATCH, so `MATCH (s)-[r1]->(m1) MATCH (m1)-[r2]->(d)` is
   an unrestricted *walk* — the same semantics as the CTE adapter's self-joins,
   where a 3-hop path may revisit one direction of an edge. It also deletes the
   EdgeUniquenessFilter operator (294ms over 2.98M paths on the popular-seed
   case). Correctness and speed pulled the same way here: the single-pattern
   form was trail-semantic and diverged from CteGraph on 1 of 144 three-hop
   cases (a support tie-flip); split clauses make a 432-case differential
   (random graphs, multi-seed, type filters, 1-3 hops) match CteGraph exactly.

Ranking is the CTE contract reproduced in cte.py's own shape: hop counts are
unrolled into pre-aggregated `UNION ALL` branches inside one `CALL {}`, then a
single outer aggregate sums support over every hop length, takes hops = the
smallest h that reached the node, and orders (hops ASC, support DESC, dst ASC)
before the LIMIT — support counts paths of all lengths *before* the cut.
Pre-aggregating inside each branch matters: it hands the union ~50k rows instead
of ~3M and cut Apply+Union from 682ms to 13ms. Grouping on the node and applying
the prefix/seed predicates *after* the aggregate (they are predicates on the
group key, so this is a pure rewrite) keeps two string comparisons off the
multi-million-row path stream — worth 2324ms -> 1162ms on its own. Intermediate
nodes stay unconstrained (they may be tags, genres, even seeds); only the final
node is prefix-filtered and seed-excluded, exactly like cte.py. Stage 2 scores
the best-weight path at the winner's min hop count, one query per hop group.

What is left is irreducible: expansion through hub nodes. `genre:Drama` alone has
25,606 edges, so 10 popular seeds legitimately generate 2.98M 2-hop paths and
`support` is defined as counting all of them. Stage 1 for that worst case is
~560ms with ~570ms of the profile in Expand + Aggregate; a random 10-seed sample
is ~195ms and a single seed ~124ms. End-to-end `expand(..., max_hops=2,
limit=50)` measures 663ms / 201ms / 132ms for those three seed profiles.
Trimming further means changing the contract, not the query: `support` counts
every path, and every path has to be walked to be counted.

The same fan-out makes max_hops=3 unusable on hub-heavy seeds — 124s for the
popular-10 set, since a third hop multiplies 2.98M paths by another hub degree.
RetrievalRequest defaults to 2 and MAX_HOPS caps at 3; treat 3 as a
small-seed/typed-edge option, not a default.
"""

import asyncio
from collections.abc import Iterable, Sequence
from typing import Any

from neo4j import AsyncDriver

from constellate.core.types import Candidate, Edge, ItemId

MAX_HOPS = 3  # service.explain caps at 3; chains are unrolled no deeper


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

    def _chain(self, hops: int, types: Sequence[str] | None) -> str:
        """Index-anchored walk of exactly `hops` steps, ending at `d`.

        One MATCH clause per hop on purpose: relationship uniqueness is scoped to
        a single clause, so splitting them drops the EdgeUniquenessFilter and
        gives the CTE adapter's unrestricted-walk semantics exactly.
        """
        parts = [f"UNWIND $seeds AS sk MATCH (s:{self._label} {{key: sk}})"]
        prev = "s"
        for i in range(1, hops + 1):
            node = "d" if i == hops else f"m{i}"
            if i > 1:
                parts.append(f" MATCH ({prev})")
            parts.append(f"-[r{i}:REL]->({node}:{self._label})")
            prev = node
        if types:
            preds = " AND ".join(f"r{i}.edge_type IN $types" for i in range(1, hops + 1))
            parts.append(f" WHERE {preds}")
        return "".join(parts)

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
        seed_nodes = sorted(f"{self._prefix}{s}" for s in seeds)
        types = list(edge_types) if edge_types else None

        # Stage 1 — structural ranking, one query shaped like cte.py's UNION-then-
        # aggregate-then-LIMIT. Each hop count is a pre-aggregated branch, so the
        # union carries one row per (dst, h) instead of one per path; the outer
        # aggregate then sums support over all lengths and takes the shortest hop
        # count, and only then orders and limits. Grouping on the node and
        # filtering after the aggregate keeps the two string predicates off the
        # multi-million-row path stream.
        hops = min(max_hops, MAX_HOPS)
        branches = " UNION ALL ".join(
            f"{self._chain(h, types)} RETURN d, {h} AS h, count(*) AS c" for h in range(1, hops + 1)
        )
        ranked = await self._run(
            f"CALL {{ {branches} }}"
            f" WITH d, min(h) AS hops, sum(c) AS support"
            f" WHERE d.key STARTS WITH $prefix AND NOT d.key IN $seeds"
            f" RETURN d.key AS dst, hops, support"
            f" ORDER BY hops ASC, support DESC, dst ASC LIMIT $limit",
            seeds=seed_nodes,
            prefix=self._prefix,
            limit=limit,
            types=types,
        )
        if not ranked:
            return []
        order = [r["dst"] for r in ranked]
        min_hops = {r["dst"]: r["hops"] for r in ranked}

        # Stage 2 — score + explanation: strongest path at the winner's min hops.
        best: dict[str, Candidate] = {}
        by_hops: dict[int, list[str]] = {}
        for dst in order:
            by_hops.setdefault(min_hops[dst], []).append(dst)
        for h, winners in by_hops.items():
            for row in await self._best_paths(seed_nodes, winners, h, types):
                dst, score = row["dst"], row["w"] / h
                if dst not in best or score > best[dst].score:
                    best[dst] = Candidate(
                        item_id=int(dst.removeprefix(self._prefix)),
                        score=score,
                        source="graph",
                        path=[str(p) for p in row["p"]],
                        hops=h,
                    )
        return [c for dst in order if (c := best.get(dst)) is not None]

    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None:
        src, dst = f"{self._prefix}{a}", f"{self._prefix}{b}"
        for h in range(1, min(max_hops, MAX_HOPS) + 1):
            rows = await self._best_paths([src], [dst], h, None)
            if rows:
                return [str(p) for p in rows[0]["p"]]
        return None

    async def _best_paths(
        self, seed_nodes: list[str], winners: list[str], hops: int, types: list[str] | None
    ) -> list[dict[str, Any]]:
        """One strongest path (by weight product) per winner at exactly `hops`."""
        match = self._chain(hops, types)
        joiner = " AND" if types else " WHERE"  # _chain already opened a WHERE for types
        weight = " * ".join(f"r{i}.weight" for i in range(1, hops + 1))
        path = ["s.key"]
        for i in range(1, hops + 1):
            path.append(f"r{i}.edge_type")
            path.append("d.key" if i == hops else f"m{i}.key")
        return await self._run(
            f"{match}{joiner} d.key IN $winners"
            f" WITH d.key AS dst, s.key AS src, {weight} AS w, [{', '.join(path)}] AS p"
            f" ORDER BY w DESC, src ASC"
            f" WITH dst, collect({{w: w, p: p}})[0] AS best"
            f" RETURN dst, best.w AS w, best.p AS p",
            seeds=seed_nodes,
            winners=winners,
            types=types,
        )
