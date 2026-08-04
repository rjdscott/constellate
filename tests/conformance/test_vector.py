"""Vector plane contract: any adapter (flat, hnswlib, pgvector, qdrant) passes unchanged."""

from kp.core.protocol import VectorPlane

DIM = 4


async def test_upsert_then_search_returns_nearest(vector: VectorPlane) -> None:
    await vector.upsert([(1, [1.0, 0.0, 0.0, 0.0]), (2, [0.0, 1.0, 0.0, 0.0])])
    got = await vector.search([1.0, 0.0, 0.0, 0.0], k=1, exclude=set())
    assert [c.item_id for c in got] == [1]
    assert all(c.source == "vector" for c in got)


async def test_exclusions_are_exact(vector: VectorPlane) -> None:
    await vector.upsert([(1, [1.0, 0.0, 0.0, 0.0]), (2, [0.9, 0.1, 0.0, 0.0])])
    got = await vector.search([1.0, 0.0, 0.0, 0.0], k=2, exclude={1})
    assert 1 not in [c.item_id for c in got]
    assert 2 in [c.item_id for c in got]


async def test_missing_item_vector_is_none(vector: VectorPlane) -> None:
    assert await vector.get_item_vector(999_999_999) is None


async def test_scores_descend(vector: VectorPlane) -> None:
    await vector.upsert(
        [(1, [1.0, 0.0, 0.0, 0.0]), (2, [0.5, 0.5, 0.0, 0.0]), (3, [0.0, 0.0, 1.0, 0.0])]
    )
    got = await vector.search([1.0, 0.0, 0.0, 0.0], k=3, exclude=set())
    scores = [c.score for c in got]
    assert scores == sorted(scores, reverse=True)
