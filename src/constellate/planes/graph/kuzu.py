"""Kuzu graph adapter (ADR 0003 — pinned 0.11.3, archived upstream).

One node table (prefixed string ids: "item:1", "tag:42") and one rel table.
Edges are stored in BOTH directions at upsert so traversal is plain directed
Cypher everywhere — Lyra's graph is semantically undirected for expansion
(m1 → tag ← m2 must reach m2), and doubling on write is cheaper and clearer
than fighting per-engine undirected-traversal dialects.

Score of an expanded candidate = max over its paths of
(product of edge weights) / hops — nearer and stronger wins.
"""

from collections.abc import Iterable, Sequence
from typing import Any

import kuzu

from constellate.core.types import Candidate, Edge, ItemId

SCHEMA = [
    "CREATE NODE TABLE IF NOT EXISTS Node(id STRING, PRIMARY KEY(id))",
    "CREATE REL TABLE IF NOT EXISTS Rel(FROM Node TO Node, edge_type STRING, weight DOUBLE)",
]


def _lit(value: str) -> str:
    """Single-quoted Cypher string literal."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _lit_list(values: "Iterable[str]") -> str:
    return "[" + ", ".join(_lit(v) for v in values) + "]"


class KuzuGraph:
    def __init__(
        self, db: kuzu.Database, *, item_prefix: str = "item:", init_schema: bool = True
    ) -> None:
        self._conn = kuzu.Connection(db)
        self._prefix = item_prefix
        if init_schema:  # skip for read-only databases loaded via `make load`
            for stmt in SCHEMA:
                self._conn.execute(stmt)

    def _item_id(self, node_id: str) -> ItemId:
        return int(node_id.removeprefix(self._prefix))

    def _query(self, cypher: str, params: dict[str, Any] | None = None) -> kuzu.QueryResult:
        result = self._conn.execute(cypher, params or {})
        assert not isinstance(result, list)  # only multi-statement strings return lists
        return result

    async def upsert_edges(self, edges: Iterable[Edge]) -> None:
        for e in edges:
            for src, dst in ((e.src, e.dst), (e.dst, e.src)):
                self._conn.execute(
                    "MERGE (a:Node {id: $src}) MERGE (b:Node {id: $dst}) "
                    "MERGE (a)-[r:Rel {edge_type: $t}]->(b) SET r.weight = $w",
                    {"src": src, "dst": dst, "t": e.edge_type, "w": e.weight},
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
        # Kuzu planner traps, learned the hard way (see phase-03 progress log):
        # a prepared-statement `$param`, a `list_contains()`, or ANY extra
        # predicate on the far node (`NOT IN`, even `<>`) blocks predicate
        # pushdown into the recursive match and turns a ~70ms anchored
        # expansion into a minutes-long full-graph walk. So: literals only,
        # `IN` for the anchor, and seed exclusion happens in Python below.
        seed_node_ids = {f"{self._prefix}{s}" for s in seeds}
        seed_list = _lit_list(sorted(seed_node_ids))
        type_filter = ""
        if edge_types:
            type_filter = f" (r, n | WHERE r.edge_type IN {_lit_list(edge_types)})"

        # Stage 1 — structural ranking with aggregates only. A 2-hop
        # neighbourhood can be 300k+ paths; they stay inside kuzu and only
        # (candidate, hops, support) rows cross into Python. Ranking is
        # nearest-first, then most-connected — this order feeds RRF.
        ranked = self._query(
            f"""
            MATCH (a:Node)-[e:Rel*1..{int(max_hops)}{type_filter}]->(b:Node)
            WHERE a.id IN {seed_list}
              AND starts_with(b.id, {_lit(self._prefix)})
            RETURN b.id AS id, min(length(e)) AS hops, count(*) AS support
            ORDER BY hops ASC, support DESC, id ASC
            LIMIT {int(limit) + len(seed_node_ids)}
            """
        )
        order: list[str] = []
        while ranked.has_next():
            row: Any = ranked.get_next()
            node_id = str(row[0])
            if node_id not in seed_node_ids:  # seed exclusion, post-LIMIT over-fetch
                order.append(node_id)
        order = order[:limit]
        if not order:
            return []

        # Stage 2 — one SHORTEST path per (seed, winner) pair: the score
        # (weight product / hops) and the explanation, at bounded row count.
        paths = self._query(
            f"""
            MATCH (a:Node)-[e:Rel* SHORTEST 1..{int(max_hops)}{type_filter}]->(b:Node)
            WHERE a.id IN {seed_list}
              AND b.id IN {_lit_list(order)}
            RETURN a.id, b.id, e
            """
        )
        best: dict[str, Candidate] = {}
        while paths.has_next():
            src_id, dst_id, rel = paths.get_next()
            path, hops, weight = self._render(str(src_id), str(dst_id), rel)
            score = weight / hops
            key = str(dst_id)
            if key not in best or score > best[key].score:
                best[key] = Candidate(
                    item_id=self._item_id(key), score=score, source="graph", path=path, hops=hops
                )
        return [best[node_id] for node_id in order if node_id in best]

    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None:
        result = self._query(
            f"""
            MATCH (x:Node {{id: {_lit(f"{self._prefix}{a}")}}})
                  -[e:Rel* SHORTEST 1..{int(max_hops)}]->
                  (y:Node {{id: {_lit(f"{self._prefix}{b}")}}})
            RETURN x.id, y.id, e LIMIT 1
            """
        )
        if not result.has_next():
            return None
        src_id, dst_id, rel = result.get_next()
        path, _, _ = self._render(str(src_id), str(dst_id), rel)
        return path

    @staticmethod
    def _render(src_id: str, dst_id: str, rel: Any) -> tuple[list[str], int, float]:
        """Recursive-rel value → (interleaved path, hops, weight product)."""
        nodes = [n["id"] for n in rel["_nodes"]]  # intermediate nodes only
        rels = rel["_rels"]
        ids = [src_id, *nodes, dst_id]
        path: list[str] = [ids[0]]
        weight = 1.0
        for i, r in enumerate(rels):
            weight *= r["weight"]
            path.extend((r["edge_type"], ids[i + 1]))
        return path, len(rels), weight
