"""Pipeline orchestration tested against in-memory fakes of the three protocols."""

from collections.abc import Iterable, Sequence

from constellate.config import PlatformConfig
from constellate.core.pipeline import Pipeline
from constellate.core.types import (
    Candidate,
    Edge,
    Item,
    ItemId,
    RetrievalRequest,
    UserContext,
    UserId,
    Vector,
)


class FakeRelational:
    def __init__(self, exclusions: set[int] | None = None, blocked: set[int] | None = None):
        self._exclusions = exclusions or set()
        self._blocked = blocked or set()

    async def get_user_context(self, user_id: UserId) -> UserContext:
        return UserContext(user_id=user_id, n_ratings=10)

    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]:
        return [Item(item_id=i, title=f"item {i}") for i in ids]

    async def search_items(self, q: str, limit: int = 20) -> list[Item]:
        raise NotImplementedError

    async def apply_policy(
        self, ids: Sequence[ItemId], ctx: UserContext | None, policy: dict[str, object]
    ) -> list[ItemId]:
        return [i for i in ids if i not in self._blocked]

    async def exclusions(self, user_id: UserId) -> set[ItemId]:
        return set(self._exclusions)


class FakeVector:
    def __init__(self, results: list[int]):
        self._results = results

    async def search(self, vec: Vector, k: int, exclude: set[ItemId]) -> list[Candidate]:
        ids = [i for i in self._results if i not in exclude][:k]
        return [
            Candidate(item_id=i, score=1.0 - r * 0.1, source="vector") for r, i in enumerate(ids)
        ]

    async def get_item_vector(self, item_id: ItemId) -> Vector | None:
        return [1.0, 0.0]

    async def get_user_vector(self, user_id: UserId) -> Vector | None:
        return [0.0, 1.0]

    async def upsert(self, rows: Iterable[tuple[ItemId, Vector]]) -> None:
        raise NotImplementedError


class FakeGraph:
    def __init__(self, results: list[int]):
        self._results = results
        self.seen_seeds: list[Sequence[ItemId]] = []

    async def expand(
        self,
        seeds: Sequence[ItemId],
        max_hops: int,
        limit: int,
        edge_types: Sequence[str] | None = None,
    ) -> list[Candidate]:
        self.seen_seeds.append(seeds)
        return [
            Candidate(
                item_id=i,
                score=0.5,
                source="graph",
                path=[f"m:{seeds[0]}", "t:9", f"m:{i}"],
                hops=2,
            )
            for i in self._results[:limit]
        ]

    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None:
        return None

    async def upsert_edges(self, edges: Iterable[Edge]) -> None:
        raise NotImplementedError


CONFIG = PlatformConfig(platform="lyra")


def _pipeline(
    vector_ids: list[int],
    graph_ids: list[int],
    exclusions: set[int] | None = None,
    blocked: set[int] | None = None,
) -> tuple[Pipeline, FakeGraph]:
    graph = FakeGraph(graph_ids)
    return (
        Pipeline(FakeRelational(exclusions, blocked), FakeVector(vector_ids), graph, CONFIG),
        graph,
    )


async def test_seed_flow_fuses_both_planes_and_excludes_seed() -> None:
    pipe, _ = _pipeline(vector_ids=[2, 3], graph_ids=[3, 4])
    resp = await pipe.retrieve(RetrievalRequest(seed_item_id=1, k=10, explain=True))
    ids = [r.item_id for r in resp.recommendations]
    assert ids[0] == 3  # in both planes → top after fusion
    assert 1 not in ids  # seed excluded
    both = resp.recommendations[0]
    assert set(both.sources) == {"vector", "graph"}
    assert both.reason is not None and "t:9" in both.reason


async def test_user_flow_seeds_graph_from_vector_candidates() -> None:
    pipe, graph = _pipeline(vector_ids=[7, 8], graph_ids=[9])
    await pipe.retrieve(RetrievalRequest(user_id=1, k=5))
    assert graph.seen_seeds == [[7, 8]]


async def test_user_exclusions_filter_both_planes() -> None:
    pipe, _ = _pipeline(vector_ids=[2, 3], graph_ids=[2, 4], exclusions={2})
    resp = await pipe.retrieve(RetrievalRequest(user_id=1, k=10))
    assert 2 not in [r.item_id for r in resp.recommendations]


async def test_policy_is_hard_gate() -> None:
    pipe, _ = _pipeline(vector_ids=[2, 3], graph_ids=[3], blocked={3})
    resp = await pipe.retrieve(RetrievalRequest(user_id=1, k=10))
    assert 3 not in [r.item_id for r in resp.recommendations]


async def test_ablation_vector_only_skips_graph() -> None:
    pipe, graph = _pipeline(vector_ids=[2], graph_ids=[9])
    resp = await pipe.retrieve(RetrievalRequest(user_id=1, k=5, planes=["vector", "relational"]))
    assert graph.seen_seeds == []
    assert [r.item_id for r in resp.recommendations] == [2]


async def test_response_carries_timings_and_fingerprint() -> None:
    pipe, _ = _pipeline(vector_ids=[2], graph_ids=[3])
    resp = await pipe.retrieve(RetrievalRequest(seed_item_id=1, k=5))
    assert resp.timings.total_ms > 0
    assert resp.config_fingerprint == CONFIG.fingerprint()
    assert resp.recommendations[0].rank == 1
