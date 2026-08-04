"""SQL self-join graph adapter — Orion's default graph plane (ADR 0004).

The thesis adapter: plain Postgres, no extension. One edge table with both
directions stored at write time (same undirected-via-doubling convention as
the Kuzu adapter) and a covering index `(src, edge_type) INCLUDE (dst,
weight)` so each hop is index-only. Research 03: at 2-3 hops explicit
self-joins beat the recursive executor and keep the plan visible — so hops
are unrolled, not recursed.

Two-stage expansion mirrors the Kuzu adapter exactly (quality equivalence
across platforms is the phase-05 gate): stage 1 aggregates (candidate,
min-hops, path support) in-engine; stage 2 fetches one best path per winner
for the score (weight product / hops) and the explanation. Notably absent:
the literal-inlining contortions the Kuzu planner forced — Postgres pushes
`$n` parameters into every plan without drama.
"""

from collections.abc import Iterable, Sequence

import asyncpg

from constellate.core.types import Candidate, Edge, ItemId

MAX_UNROLLED_HOPS = 3  # service.explain caps at 3; unrolled joins go no deeper

SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_edges(
    src text NOT NULL, dst text NOT NULL, edge_type text NOT NULL,
    weight double precision NOT NULL,
    PRIMARY KEY (src, dst, edge_type));
CREATE INDEX IF NOT EXISTS graph_edges_cover
    ON graph_edges (src, edge_type) INCLUDE (dst, weight);
"""


def _hop_sql(hops: int, with_types: bool) -> str:
    """SELECT yielding (dst, weight-product, hops) for exactly `hops` steps."""
    joins, weight = "graph_edges e1", "e1.weight"
    for i in range(2, hops + 1):
        joins += f" JOIN graph_edges e{i} ON e{i}.src = e{i - 1}.dst"
        weight += f" * e{i}.weight"
    where = "e1.src = ANY($1)"
    if with_types:
        where += "".join(f" AND e{i}.edge_type = ANY($4)" for i in range(1, hops + 1))
    return f"SELECT e{hops}.dst AS dst, {weight} AS w, {hops} AS hops FROM {joins} WHERE {where}"


class CteGraph:
    def __init__(self, pool: asyncpg.Pool, *, item_prefix: str = "item:") -> None:
        self._pool = pool
        self._prefix = item_prefix

    async def upsert_edges(self, edges: Iterable[Edge]) -> None:
        rows = []
        for e in edges:
            for src, dst in ((e.src, e.dst), (e.dst, e.src)):
                rows.append((src, dst, e.edge_type, e.weight))
        await self._pool.executemany(
            "INSERT INTO graph_edges(src, dst, edge_type, weight) VALUES ($1, $2, $3, $4)"
            " ON CONFLICT (src, dst, edge_type) DO UPDATE SET weight = EXCLUDED.weight",
            rows,
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
        hops = min(max_hops, MAX_UNROLLED_HOPS)
        seed_nodes = sorted(f"{self._prefix}{s}" for s in seeds)
        types = list(edge_types) if edge_types else None

        union = " UNION ALL ".join(_hop_sql(h, types is not None) for h in range(1, hops + 1))
        stage1 = f"""
            WITH paths AS ({union})
            SELECT dst, min(hops) AS hops, count(*) AS support
            FROM paths
            WHERE dst LIKE $2 || '%' AND NOT dst = ANY($1)
            GROUP BY dst
            ORDER BY hops ASC, support DESC, dst ASC
            LIMIT $3
        """
        args: list[object] = [seed_nodes, self._prefix, limit]
        if types is not None:
            args.append(types)
        ranked = await self._pool.fetch(stage1, *args)
        if not ranked:
            return []
        by_hops: dict[int, list[str]] = {}
        order: list[str] = []
        for r in ranked:
            by_hops.setdefault(r["hops"], []).append(r["dst"])
            order.append(r["dst"])

        best: dict[str, Candidate] = {}
        for h, winners in by_hops.items():
            for row in await self._best_paths(seed_nodes, winners, h, types):
                path = _interleave(row)
                dst = path[-1]
                score = row["w"] / h
                if dst not in best or score > best[dst].score:
                    best[dst] = Candidate(
                        item_id=int(dst.removeprefix(self._prefix)),
                        score=score,
                        source="graph",
                        path=path,
                        hops=h,
                    )
        return [best[dst] for dst in order if dst in best]

    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None:
        src, dst = f"{self._prefix}{a}", f"{self._prefix}{b}"
        for h in range(1, min(max_hops, MAX_UNROLLED_HOPS) + 1):
            rows = await self._best_paths([src], [dst], h, None)
            if rows:
                return _interleave(rows[0])
        return None

    async def _best_paths(
        self, seed_nodes: list[str], winners: list[str], hops: int, types: list[str] | None
    ) -> list[asyncpg.Record]:
        """One strongest path (by weight product) per winner at exactly `hops`."""
        cols = ["e1.src AS n0"]
        weight = "e1.weight"
        joins = "graph_edges e1"
        for i in range(2, hops + 1):
            joins += f" JOIN graph_edges e{i} ON e{i}.src = e{i - 1}.dst"
            weight += f" * e{i}.weight"
        for i in range(1, hops + 1):
            cols.append(f"e{i}.edge_type AS t{i}")
            cols.append(f"e{i}.dst AS n{i}")
        where = f"e1.src = ANY($1) AND e{hops}.dst = ANY($2)"
        if types is not None:
            where += "".join(f" AND e{i}.edge_type = ANY($3)" for i in range(1, hops + 1))
        sql = f"""
            SELECT DISTINCT ON (e{hops}.dst) {", ".join(cols)}, {weight} AS w
            FROM {joins} WHERE {where}
            ORDER BY e{hops}.dst, w DESC, e1.src ASC
        """
        args: list[object] = [seed_nodes, winners]
        if types is not None:
            args.append(types)
        return list(await self._pool.fetch(sql, *args))


def _interleave(row: asyncpg.Record) -> list[str]:
    """(n0, t1, n1, t2, n2, ...) record → [n0, t1, n1, ...] path."""
    path = [row["n0"]]
    i = 1
    while f"t{i}" in row:
        path.extend((row[f"t{i}"], row[f"n{i}"]))
        i += 1
    return path
