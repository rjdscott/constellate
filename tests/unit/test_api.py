"""API surface over a faked service: routes, validation, response envelope,
platform registry (ADR 0011)."""

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from constellate.api import app as app_module
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

CATALOGUE = [
    Item(item_id=1, title="Alpha (1994)", popularity=2.0),
    Item(item_id=2, title="Beta (2001)", popularity=1.0),
    Item(item_id=3, title="alphabet soup (2020)", popularity=5.0),
]


class FakeRelational:
    async def get_user_context(self, user_id: UserId) -> UserContext:
        return UserContext(user_id=user_id, n_ratings=1 if user_id == 1 else 0)

    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]:
        return [Item(item_id=i, title=f"item {i}") for i in ids]

    async def search_items(self, q: str, limit: int = 20) -> list[Item]:
        hits = [i for i in CATALOGUE if q.lower() in i.title.lower()]
        return sorted(hits, key=lambda i: (-i.popularity, i.item_id))[:limit]

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


def _service(platform: str = "lyra") -> Service:
    cfg = PlatformConfig.model_validate({"platform": platform})
    relational, vector, graph = FakeRelational(), FakeVector(), FakeGraph()
    return Service(Pipeline(relational, vector, graph, cfg), relational, vector, graph, cfg)


def _client() -> TestClient:
    return TestClient(create_app(_service()))


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


def test_explain_true_carries_structured_path() -> None:
    with _client() as client:
        explained = client.post(
            "/v1/similar", json={"seed_item_id": 1, "k": 5, "explain": True}
        ).json()
        graph_rec = next(r for r in explained["recommendations"] if r["item_id"] == 8)
        assert graph_rec["path"] == ["m:1", "t:2", "m:8"]
        assert graph_rec["reason"] == "m:1 → t:2 → m:8"
        plain = client.post("/v1/similar", json={"seed_item_id": 1, "k": 5}).json()
        assert all(r["path"] is None for r in plain["recommendations"])


def test_default_and_explicit_platform_hit_the_same_service() -> None:
    with _client() as client:
        assert client.get("/v1/health").json()["platform"] == "lyra"
        assert client.get("/v1/health", params={"platform": "lyra"}).json()["platform"] == "lyra"


def test_unknown_platform_is_404_listing_the_valid_ones() -> None:
    with _client() as client:
        response = client.get("/v1/health", params={"platform": "vega"})
        assert response.status_code == 404
        assert "lyra" in response.json()["detail"]


def test_platforms_are_built_once_and_failures_are_503(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[str] = []

    async def fake_build(platform: str) -> Service:
        built.append(platform)
        if platform == "hydra":
            raise ConnectionError("memgraph unreachable")
        return _service(platform)

    monkeypatch.setattr(app_module, "build_service", fake_build)
    with _client() as client:
        assert client.get("/v1/health", params={"platform": "orion"}).json()["platform"] == "orion"
        client.get("/v1/health", params={"platform": "orion"})
        down = client.get("/v1/health", params={"platform": "hydra"})
        assert down.status_code == 503
        assert "memgraph unreachable" in down.json()["detail"]
    assert built == ["orion", "hydra"]  # orion cached, hydra never cached


def test_platforms_listing_reports_liveness(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_build(platform: str) -> Service:
        if platform == "hydra":
            raise ConnectionError("memgraph unreachable")
        return _service(platform)

    monkeypatch.setattr(app_module, "build_service", fake_build)
    with _client() as client:
        rows = client.get("/v1/platforms").json()
    assert {r["platform"]: r["alive"] for r in rows} == {
        "hydra": False,
        "lyra": True,
        "orion": True,
    }
    assert all(r["config_fingerprint"] for r in rows if r["alive"])
    assert all(r["config_fingerprint"] is None for r in rows if not r["alive"])


def test_item_search() -> None:
    with _client() as client:
        hits = client.get("/v1/search/items", params={"q": "alpha"}).json()
        assert [i["item_id"] for i in hits] == [3, 1]  # popularity DESC
        assert client.get("/v1/search/items", params={"q": "alpha", "limit": 1}).json() == hits[:1]
        assert client.get("/v1/search/items", params={"q": ""}).status_code == 422


def test_items_hydrate() -> None:
    with _client() as client:
        hits = client.get("/v1/items", params={"ids": "1,2,3"}).json()
        assert [i["item_id"] for i in hits] == [1, 2, 3]
        assert all(i["title"].startswith("item") for i in hits)
        # dedup is not required — passthrough to hydrate(), which honours order
        assert client.get("/v1/items", params={"ids": ""}).status_code == 422
        assert client.get("/v1/items", params={"ids": "a,b"}).status_code == 422


def test_items_hydrate_caps_at_100() -> None:
    with _client() as client:
        many = ",".join(str(i) for i in range(1, 151))
        hits = client.get("/v1/items", params={"ids": many}).json()
        assert len(hits) == 100
        assert [i["item_id"] for i in hits] == list(range(1, 101))


def test_tags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    csv_path = tmp_path / "genome-tags.csv"
    csv_path.write_text("tagId,tag\n742,zombies\n1,007\n")
    from constellate import service as service_module

    monkeypatch.setattr(service_module, "TAGS_PATH", csv_path)
    monkeypatch.setattr(service_module, "_tags_cache", None)
    with _client() as client:
        assert client.get("/v1/tags").json() == {"742": "zombies", "1": "007"}


def test_tags_404_when_csv_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from constellate import service as service_module

    monkeypatch.setattr(service_module, "TAGS_PATH", tmp_path / "missing.csv")
    monkeypatch.setattr(service_module, "_tags_cache", None)
    with _client() as client:
        response = client.get("/v1/tags")
        assert response.status_code == 404
        assert "genome tags" in response.json()["detail"]


def test_user_context_404_without_ratings() -> None:
    with _client() as client:
        assert client.get("/v1/users/1").json()["n_ratings"] == 1
        assert client.get("/v1/users/999").status_code == 404


def test_serves_ui_dist_with_spa_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>Constellate</title>")
    monkeypatch.setattr(app_module, "UI_DIST_DIR", tmp_path)
    with _client() as client:
        assert "Constellate" in client.get("/").text
        # client-side route, no matching file on disk — falls back to index.html
        assert "Constellate" in client.get("/playground").text
        assert client.get("/v1/health").json()["platform"] == "lyra"  # /v1/* never shadowed


def test_no_ui_dist_means_no_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "UI_DIST_DIR", tmp_path / "does-not-exist")
    with _client() as client:
        assert client.get("/").status_code == 404
        assert client.get("/v1/health").status_code == 200


def test_bench_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    artifact = {"platform": "lyra", "config_fingerprint": "abc123", "utc": "2026-08-04T08:29:17Z"}
    (tmp_path / "lyra-f7eb799-20260804T082917Z.json").write_text(json.dumps(artifact))
    (tmp_path.parent / "secret.json").write_text(json.dumps({"nope": True}))
    monkeypatch.setattr(app_module, "RESULTS_DIR", tmp_path)
    with _client() as client:
        listing = client.get("/v1/bench-results").json()
        assert listing == [
            {
                "name": "lyra-f7eb799-20260804T082917Z",
                "platform": "lyra",
                "config_fingerprint": "abc123",
                "utc": "2026-08-04T08:29:17Z",
            }
        ]
        assert client.get(f"/v1/bench-results/{listing[0]['name']}").json() == artifact
        assert client.get("/v1/bench-results/%2e%2e%2fsecret").status_code == 404
        assert client.get("/v1/bench-results/nope").status_code == 404
