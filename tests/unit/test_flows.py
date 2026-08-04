"""F1-F6 flows against fake planes: checks fire, failures surface."""

import asyncio
from collections.abc import Iterable, Sequence

import pandas as pd

from constellate.bench.flows import run_flows
from constellate.config import PlatformConfig
from constellate.core.pipeline import Pipeline
from constellate.core.types import (
    Candidate,
    Edge,
    Item,
    ItemId,
    UserContext,
    UserId,
    Vector,
)
from constellate.service import Service


class FakeRelational:
    def __init__(self, year: int = 2005) -> None:
        self.year = year

    async def get_user_context(self, user_id: UserId) -> UserContext:
        return UserContext(user_id=user_id, n_ratings=1)

    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]:
        return [
            Item(item_id=i, title=f"item {i}", year=self.year, genres=["Drama"]) for i in ids
        ]

    async def apply_policy(
        self, ids: Sequence[ItemId], ctx: UserContext | None, policy: dict[str, object]
    ) -> list[ItemId]:
        return list(ids)

    async def exclusions(self, user_id: UserId) -> set[ItemId]:
        return set()


class FakeVector:
    async def search(self, vec: Vector, k: int, exclude: set[ItemId]) -> list[Candidate]:
        return [Candidate(item_id=7, score=1.0, source="vector")]

    async def get_item_vector(self, item_id: ItemId) -> Vector | None:
        return [1.0, 0.0]

    async def get_user_vector(self, user_id: UserId) -> Vector | None:
        return [0.0, 1.0]

    async def upsert(self, rows: Iterable[tuple[ItemId, Vector]]) -> None:
        raise NotImplementedError


class FakeGraph:
    async def expand(
        self,
        seeds: Sequence[ItemId],
        max_hops: int,
        limit: int,
        edge_types: Sequence[str] | None = None,
    ) -> list[Candidate]:
        return [Candidate(item_id=8, score=0.5, source="graph", path=["m:1", "t:2", "m:8"], hops=2)]

    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None:
        return ["m:1", "CO_RATED", "m:8"] if b == 8 else None

    async def upsert_edges(self, edges: Iterable[Edge]) -> None:
        raise NotImplementedError


PROBES = pd.DataFrame(
    {
        "kind": ["tag_bridge", "cold_start", "path_required"],
        "seed_item_id": [1, 2, 1],
        "expected_items": [[7, 8], [7], [8]],
    }
)


def _service(year: int = 2005) -> Service:
    cfg = PlatformConfig(platform="lyra")
    relational = FakeRelational(year=year)
    vector, graph = FakeVector(), FakeGraph()
    return Service(Pipeline(relational, vector, graph, cfg), relational, graph, cfg)


def test_all_flows_pass_on_wellbehaved_service() -> None:
    results = asyncio.run(run_flows(_service(), PROBES, user_id=1))
    assert [r.flow for r in results] == ["F1", "F2", "F3", "F4", "F5", "F6"]
    assert all(r.passed for r in results), [(r.flow, r.failures) for r in results]
    f6 = results[-1]
    assert len(f6.call_ms) == 6  # 3 repeats x (similar + refine)


def test_f4_catches_policy_violation() -> None:
    # relational hydrates year 1950 while policy demands >= 2000 and the fake
    # apply_policy lets everything through — F4 must call that out
    results = asyncio.run(run_flows(_service(year=1950), PROBES, user_id=1))
    f4 = next(r for r in results if r.flow == "F4")
    assert not f4.passed
    assert any("min_year" in msg for msg in f4.failures)
