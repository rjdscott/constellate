"""Graph plane contract: any adapter (Kuzu, CTE, AGE, Memgraph) passes unchanged."""

from constellate.core.protocol import GraphPlane
from constellate.core.types import Edge


async def _seed(graph: GraphPlane) -> None:
    await graph.upsert_edges(
        [
            Edge(src="m:1", dst="t:10", edge_type="HAS_TAG", weight=0.9),
            Edge(src="m:2", dst="t:10", edge_type="HAS_TAG", weight=0.8),
            Edge(src="m:2", dst="g:5", edge_type="HAS_GENRE", weight=1.0),
        ]
    )


async def test_two_hop_expansion_reaches_tag_sibling(graph: GraphPlane) -> None:
    await _seed(graph)
    got = await graph.expand([1], max_hops=2, limit=10)
    ids = [c.item_id for c in got]
    assert 2 in ids  # m:1 -HAS_TAG-> t:10 <-HAS_TAG- m:2
    assert all(c.source == "graph" for c in got)


async def test_expansion_carries_paths_and_hops(graph: GraphPlane) -> None:
    await _seed(graph)
    got = await graph.expand([1], max_hops=2, limit=10)
    hit = next(c for c in got if c.item_id == 2)
    assert hit.path is not None and hit.path[0].endswith("1") and hit.path[-1].endswith("2")
    assert hit.hops == 2


async def test_hop_limit_respected(graph: GraphPlane) -> None:
    await _seed(graph)
    got = await graph.expand([1], max_hops=1, limit=10)
    assert 2 not in [c.item_id for c in got]  # m:2 is two hops from m:1


async def test_path_between(graph: GraphPlane) -> None:
    await _seed(graph)
    path = await graph.path_between(1, 2, max_hops=2)
    assert path is not None and len(path) >= 3
    assert await graph.path_between(1, 999_999, max_hops=2) is None
