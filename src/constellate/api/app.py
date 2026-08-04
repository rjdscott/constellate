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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

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
UI_DIST_DIR = Path(__file__).resolve().parents[3] / "ui" / "dist"  # module attr, same as
# RESULTS_DIR/TAGS_PATH — tests monkeypatch this before calling create_app()
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


class SPAStaticFiles(StaticFiles):
    """`ui/dist`, serving `index.html` for any path the SPA owns (react-router
    client-side routes like `/playground`) instead of Starlette's default 404 —
    the standard FastAPI SPA pattern. Mounted at `/` *after* every `/v1/*`
    route below, so those routes always match first and are never shadowed."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # A malformed /v1/* path (e.g. a traversal attempt normalized down
            # to something no route matches) must still 404, not silently
            # become the SPA shell — only genuine SPA routes fall back.
            # collapse duplicate leading slashes: Starlette won't route
            # "//v1/health" to the API, and the raw path wouldn't match the
            # "/v1/" prefix either — the SPA shell must not answer for it
            request_path = "/" + str(scope["path"]).lstrip("/")
            is_api_path = request_path == "/v1" or request_path.startswith("/v1/")
            if exc.status_code == 404 and not is_api_path:
                return await super().get_response("index.html", scope)
            raise


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

    @asynccontextmanager
    async def scoped(platform: str | None) -> AsyncIterator[Service]:
        """Resolve, warm, and guard one platform for one request. Any engine
        failure — at build time or after (a pool dying under a warmed service)
        — becomes a typed 503 and evicts the broken service so the next
        request rebuilds it (ADR 0011: clear per-platform degradation)."""
        name = platform or default_platform
        if name not in PLATFORMS:
            raise HTTPException(404, f"unknown platform {name!r} (have: {', '.join(PLATFORMS)})")
        try:
            yield await warm(name)
        except HTTPException:
            raise
        except Exception as exc:  # engines down, artifacts missing, bad config
            if broken := services.pop(name, None):
                broken.close()
            raise HTTPException(503, f"platform {name!r} unavailable: {exc}") from exc

    @app.get("/v1/platforms")
    async def platforms() -> list[dict[str, object]]:
        """Liveness per platform: build (pools + artifacts) on first call, then
        Service.health()'s real per-plane point lookups on every call — a
        platform whose engine dies after warming flips to alive:false and is
        evicted so the next call retries the build."""
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
        async with scoped(platform) as service:
            return await service.recommend(request)

    @app.post("/v1/similar")
    async def similar(request: SimilarRequest, platform: str | None = None) -> RetrievalResponse:
        async with scoped(platform) as service:
            return await service.similar(request.seed_item_id, k=request.k, explain=request.explain)

    @app.post("/v1/explain")
    async def explain(request: ExplainRequest, platform: str | None = None) -> dict[str, object]:
        async with scoped(platform) as service:
            path = await service.explain(request.a, request.b, request.max_hops)
        return {"a": request.a, "b": request.b, "path": path}

    @app.get("/v1/search/items")
    async def search_items(
        q: str = Query(min_length=1), limit: int = 20, platform: str | None = None
    ) -> list[Item]:
        async with scoped(platform) as service:
            return await service.search_items(q, limit)

    @app.get("/v1/items")
    async def items(ids: str = Query(min_length=1), platform: str | None = None) -> list[Item]:
        try:
            parsed = [int(raw) for raw in ids.split(",") if raw.strip()][:MAX_ITEM_IDS]
        except ValueError as exc:
            raise HTTPException(422, "ids must be a comma-separated list of integers") from exc
        if not parsed:
            raise HTTPException(422, "ids must be a comma-separated list of integers")
        async with scoped(platform) as service:
            return await service.hydrate(parsed)

    @app.get("/v1/tags")
    async def tags() -> dict[str, str]:
        try:
            return load_tags()
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/v1/users/{user_id}")
    async def user(user_id: UserId, platform: str | None = None) -> UserContext:
        async with scoped(platform) as service:
            ctx = await service.user_context(user_id)
        if ctx.n_ratings == 0:  # adapters return an empty context for unknown users
            raise HTTPException(404, f"no ratings for user {user_id}")
        return ctx

    @app.get("/v1/health")
    async def health(platform: str | None = None) -> dict[str, str]:
        async with scoped(platform) as service:
            return await service.health()

    @app.get("/v1/stats")
    async def stats(platform: str | None = None) -> dict[str, object]:
        async with scoped(platform) as service:
            return await service.stats()

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

    if UI_DIST_DIR.is_dir():
        app.mount("/", SPAStaticFiles(directory=UI_DIST_DIR, html=True), name="ui")

    return app


app = create_app()
