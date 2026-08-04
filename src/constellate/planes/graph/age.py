"""Apache AGE graph adapter — Orion's second graph plane (ADR 0004).

openCypher over the same doubled-edge convention as Kuzu/CTE. AGE 1.7 has
no shortest_path() (lands in 1.8, the ADR's revisit trigger), so hops are
unrolled into explicit relationship chains — one MATCH per hop count, each
aggregating in-engine, merged in Python to the exact Kuzu semantics:
support = paths over all hop counts, hops = min hop count reaching the
node, score = best (weight product / hops) at that min hop count.

Values cross the boundary as scalar agtype (strings/numbers), never
composite ::vertex/::edge — that keeps parsing to `json.loads` of scalars
and avoids AGE's annotated-JSON grammar entirely.
"""

import json
from collections.abc import Iterable, Sequence
from typing import Any

import asyncpg

from constellate.core.types import Candidate, Edge, ItemId

MAX_UNROLLED_HOPS = 3

SESSION_SETUP = ("LOAD 'age'", 'SET search_path = ag_catalog, "$user", public')


def _lit(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _lit_list(values: Iterable[str]) -> str:
    return "[" + ", ".join(_lit(v) for v in values) + "]"


def _chain(hops: int, types: Sequence[str] | None) -> tuple[str, str, str]:
    """(match pattern, weight product expr, per-edge type predicate)."""
    parts = ["(a:Node)"]
    for i in range(1, hops + 1):
        node = "(b:Node)" if i == hops else f"(m{i}:Node)"
        parts.append(f"-[r{i}:REL]->{node}")
    # toFloat: the CSV bulk loader lands numeric-looking properties as agtype
    # strings; bare string * string throws "Invalid input parameter types for
    # agtype_mul" on any multi-hop weight product
    weight = " * ".join(f"toFloat(r{i}.weight)" for i in range(1, hops + 1))
    type_pred = ""
    if types:
        lits = _lit_list(types)
        type_pred = "".join(f" AND r{i}.edge_type IN {lits}" for i in range(1, hops + 1))
    return "".join(parts), weight, type_pred


class AgeGraph:
    def __init__(self, pool: asyncpg.Pool, graph: str, *, item_prefix: str = "item:") -> None:
        self._pool = pool
        self._graph = graph
        self._prefix = item_prefix

    async def _cypher(self, query: str, columns: str) -> list[list[Any]]:
        async with self._pool.acquire() as conn:
            for stmt in SESSION_SETUP:
                await conn.execute(stmt)
            rows = await conn.fetch(
                f"SELECT * FROM cypher({_lit(self._graph)}, $q${query}$q$) AS ({columns})"
            )
        # every column is scalar agtype → its text form is valid JSON
        return [[json.loads(v) for v in row.values()] for row in rows]

    async def upsert_edges(self, edges: Iterable[Edge]) -> None:
        for e in edges:
            for src, dst in ((e.src, e.dst), (e.dst, e.src)):
                await self._cypher(
                    f"MERGE (a:Node {{key: {_lit(src)}}}) MERGE (b:Node {{key: {_lit(dst)}}}) "
                    f"MERGE (a)-[r:REL {{edge_type: {_lit(e.edge_type)}}}]->(b) "
                    f"SET r.weight = {e.weight}",
                    "n agtype",
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
        seed_list = _lit_list(seed_nodes)
        support: dict[str, int] = {}
        min_hops: dict[str, int] = {}
        for h in range(1, min(max_hops, MAX_UNROLLED_HOPS) + 1):
            pattern, _, type_pred = _chain(h, edge_types)
            rows = await self._cypher(
                f"MATCH {pattern} WHERE a.key IN {seed_list}"
                f" AND b.key STARTS WITH {_lit(self._prefix)}"
                f" AND NOT b.key IN {seed_list}{type_pred}"
                f" RETURN b.key, count(*)",
                "id agtype, n agtype",
            )
            for node_id, n in rows:
                support[node_id] = support.get(node_id, 0) + int(n)
                min_hops.setdefault(node_id, h)
        order = sorted(support, key=lambda i: (min_hops[i], -support[i], i))[:limit]
        if not order:
            return []

        best: dict[str, Candidate] = {}
        by_hops: dict[int, list[str]] = {}
        for node_id in order:
            by_hops.setdefault(min_hops[node_id], []).append(node_id)
        for h, winners in by_hops.items():
            for row in await self._paths(seed_nodes, winners, h, edge_types):
                *path, weight = row
                dst = str(path[-1])
                score = float(weight) / h
                if dst not in best or score > best[dst].score:
                    best[dst] = Candidate(
                        item_id=int(dst.removeprefix(self._prefix)),
                        score=score,
                        source="graph",
                        path=[str(p) for p in path],
                        hops=h,
                    )
        return [best[node_id] for node_id in order if node_id in best]

    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None:
        src, dst = f"{self._prefix}{a}", f"{self._prefix}{b}"
        for h in range(1, min(max_hops, MAX_UNROLLED_HOPS) + 1):
            rows = await self._paths([src], [dst], h, None, limit=1)
            if rows:
                *path, _ = rows[0]
                return [str(p) for p in path]
        return None

    async def _paths(
        self,
        seed_nodes: list[str],
        winners: list[str],
        hops: int,
        types: Sequence[str] | None,
        limit: int | None = None,
    ) -> list[list[Any]]:
        """Paths (interleaved node/edge_type columns + weight product) at
        exactly `hops`, strongest first; caller keeps first-per-winner."""
        pattern, weight, type_pred = _chain(hops, types)
        returns = ["a.key"]
        for i in range(1, hops + 1):
            returns.append(f"r{i}.edge_type")
            returns.append(f"m{i}.key" if i < hops else "b.key")
        cols = ", ".join(f"c{i} agtype" for i in range(len(returns) + 1))
        query = (
            f"MATCH {pattern} WHERE a.key IN {_lit_list(seed_nodes)}"
            f" AND b.key IN {_lit_list(winners)}{type_pred}"
            f" RETURN {', '.join(returns)}, {weight} ORDER BY {weight} DESC"
        )
        if limit:
            query += f" LIMIT {int(limit)}"
        return await self._cypher(query, cols)
