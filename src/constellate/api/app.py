"""FastAPI app: `uv run uvicorn constellate.api.app:app`.

One process serves every platform (ADR 0011): a lazy registry builds a Service
the first time a platform is asked for and caches it, so a platform whose
engines are down costs a 503 on its own requests instead of the whole process.
`platform` defaults to $PLATFORM (lyra). Every retrieval response carries
per-step timings and the config fingerprint — a benchmark result you cannot tie
to a config is noise.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from constellate.config import CONFIG_DIR
from constellate.core.types import (
    Item,
    ItemId,
    RetrievalRequest,
    RetrievalResponse,
    UserContext,
    UserId,
)
from constellate.factory import build_service
from constellate.service import Service, load_tags

PLATFORMS = sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))  # config/ is the registry
RESULTS_DIR = Path(__file__).resolve().parents[3] / "bench" / "results"
DEV_ORIGIN = "http://localhost:5173"  # vite dev server
MAX_ITEM_IDS = 100  # /v1/items — one hydrate round trip caps out here


class SimilarRequest(BaseModel):
    seed_item_id: ItemId
    k: int = 20
    explain: bool = False


class ExplainRequest(BaseModel):
    a: ItemId
    b: ItemId
    max_hops: int = 3


def create_app(service: Service | None = None) -> FastAPI:
    default_platform = os.environ.get("PLATFORM", "lyra")
    # an injected service (tests, embedding) pre-warms the default platform slot
    services: dict[str, Service] = {default_platform: service} if service else {}
    build_lock = asyncio.Lock()  # concurrent first requests would build two pools

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            for warmed in services.values():
                warmed.close()

    app = FastAPI(title="constellate", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[DEV_ORIGIN],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def warm(platform: str) -> Service:
        if cached := services.get(platform):  # fast path: no lock once warm
            return cached
        async with build_lock:
            if platform not in services:
                services[platform] = await build_service(platform)
            return services[platform]

    async def svc(platform: str | None) -> Service:
        name = platform or default_platform
        if name not in PLATFORMS:
            raise HTTPException(404, f"unknown platform {name!r} (have: {', '.join(PLATFORMS)})")
        try:
            return await warm(name)
        except Exception as exc:  # engines down, artifacts missing, bad config
            raise HTTPException(503, f"platform {name!r} unavailable: {exc}") from exc

    @app.get("/v1/platforms")
    async def platforms() -> list[dict[str, object]]:
        """Liveness per platform — building the service is the probe: it opens
        the pools and reads the artifacts, which is what "alive" has to mean."""
        out: list[dict[str, object]] = []
        for name in PLATFORMS:
            try:
                health = await (await warm(name)).health()
            except Exception:
                if broken := services.pop(name, None):
                    broken.close()
                out.append({"platform": name, "alive": False, "config_fingerprint": None})
            else:
                out.append(
                    {
                        "platform": name,
                        "alive": True,
                        "config_fingerprint": health["config_fingerprint"],
                    }
                )
        return out

    @app.post("/v1/recommend")
    async def recommend(
        request: RetrievalRequest, platform: str | None = None
    ) -> RetrievalResponse:
        if request.user_id is None and request.seed_item_id is None:
            raise HTTPException(422, "user_id or seed_item_id required")
        return await (await svc(platform)).recommend(request)

    @app.post("/v1/similar")
    async def similar(request: SimilarRequest, platform: str | None = None) -> RetrievalResponse:
        return await (await svc(platform)).similar(
            request.seed_item_id, k=request.k, explain=request.explain
        )

    @app.post("/v1/explain")
    async def explain(request: ExplainRequest, platform: str | None = None) -> dict[str, object]:
        path = await (await svc(platform)).explain(request.a, request.b, request.max_hops)
        return {"a": request.a, "b": request.b, "path": path}

    @app.get("/v1/search/items")
    async def search_items(
        q: str = Query(min_length=1), limit: int = 20, platform: str | None = None
    ) -> list[Item]:
        return await (await svc(platform)).search_items(q, limit)

    @app.get("/v1/items")
    async def items(ids: str = Query(min_length=1), platform: str | None = None) -> list[Item]:
        try:
            parsed = [int(raw) for raw in ids.split(",") if raw.strip()][:MAX_ITEM_IDS]
        except ValueError as exc:
            raise HTTPException(422, "ids must be a comma-separated list of integers") from exc
        if not parsed:
            raise HTTPException(422, "ids must be a comma-separated list of integers")
        return await (await svc(platform)).hydrate(parsed)

    @app.get("/v1/tags")
    async def tags() -> dict[str, str]:
        try:
            return load_tags()
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/v1/users/{user_id}")
    async def user(user_id: UserId, platform: str | None = None) -> UserContext:
        ctx = await (await svc(platform)).user_context(user_id)
        if ctx.n_ratings == 0:  # adapters return an empty context for unknown users
            raise HTTPException(404, f"no ratings for user {user_id}")
        return ctx

    @app.get("/v1/health")
    async def health(platform: str | None = None) -> dict[str, str]:
        return await (await svc(platform)).health()

    @app.get("/v1/stats")
    async def stats(platform: str | None = None) -> dict[str, object]:
        return await (await svc(platform)).stats()

    @app.get("/v1/bench-results")
    async def bench_results() -> list[dict[str, object]]:
        """Committed artifacts only — the harness stays the one latency oracle."""
        return [
            {
                "name": path.stem,
                "platform": raw.get("platform"),
                "config_fingerprint": raw.get("config_fingerprint"),
                "utc": raw.get("utc"),
            }
            for path in sorted(RESULTS_DIR.glob("*.json"))
            if (raw := json.loads(path.read_text()))
        ]

    @app.get("/v1/bench-results/{name}")
    async def bench_result(name: str) -> dict[str, object]:
        if name not in {p.stem for p in RESULTS_DIR.glob("*.json")}:  # also the traversal guard
            raise HTTPException(404, f"no bench result {name!r}")
        artifact: dict[str, object] = json.loads((RESULTS_DIR / f"{name}.json").read_text())
        return artifact

    return app


app = create_app()
