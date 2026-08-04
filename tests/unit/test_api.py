"""API surface over a faked service: routes, validation, response envelope."""

from collections.abc import Iterable, Sequence

from fastapi.testclient import TestClient

from constellate.api.app import create_app
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
    async def get_user_context(self, user_id: UserId) -> UserContext:
        return UserContext(user_id=user_id, n_ratings=1)

    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]:
        return [Item(item_id=i, title=f"item {i}") for i in ids]

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
        return ["m:1", "HAS_TAG", "t:2", "HAS_TAG", "m:8"] if b == 8 else None

    async def upsert_edges(self, edges: Iterable[Edge]) -> None:
        raise NotImplementedError


def _client() -> TestClient:
    cfg = PlatformConfig(platform="lyra")
    relational, vector, graph = FakeRelational(), FakeVector(), FakeGraph()
    service = Service(Pipeline(relational, vector, graph, cfg), relational, vector, graph, cfg)
    return TestClient(create_app(service))


def test_similar_envelope() -> None:
    with _client() as client:
        body = client.post("/v1/similar", json={"seed_item_id": 1, "k": 5, "explain": True}).json()
        ids = [r["item_id"] for r in body["recommendations"]]
        assert set(ids) == {7, 8}
        assert body["config_fingerprint"]
        assert body["timings"]["total_ms"] >= 0
        assert all(r["metadata"]["title"].startswith("item") for r in body["recommendations"])


def test_recommend_requires_a_subject() -> None:
    with _client() as client:
        assert client.post("/v1/recommend", json={"k": 5}).status_code == 422


def test_explain_and_health() -> None:
    with _client() as client:
        assert client.post("/v1/explain", json={"a": 1, "b": 8}).json()["path"][0] == "m:1"
        assert client.post("/v1/explain", json={"a": 1, "b": 9}).json()["path"] is None
        health = client.get("/v1/health").json()
        assert health["status"] == "ok"
        assert health["platform"] == "lyra"
