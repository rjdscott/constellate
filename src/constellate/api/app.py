"""FastAPI app: `uv run uvicorn constellate.api.app:app`.

Platform comes from $PLATFORM (default lyra). Every retrieval response
carries per-step timings and the config fingerprint — a benchmark result you
cannot tie to a config is noise.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from constellate.core.types import ItemId, RetrievalRequest, RetrievalResponse
from constellate.factory import build_service
from constellate.service import Service


class SimilarRequest(BaseModel):
    seed_item_id: ItemId
    k: int = 20
    explain: bool = False


class ExplainRequest(BaseModel):
    a: ItemId
    b: ItemId
    max_hops: int = 3


def create_app(service: Service | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.service = service or await build_service(os.environ.get("PLATFORM", "lyra"))
        try:
            yield
        finally:
            app.state.service.close()

    app = FastAPI(title="constellate", lifespan=lifespan)

    def svc() -> Service:
        out: Service = app.state.service
        return out

    @app.post("/v1/recommend")
    async def recommend(request: RetrievalRequest) -> RetrievalResponse:
        if request.user_id is None and request.seed_item_id is None:
            raise HTTPException(422, "user_id or seed_item_id required")
        return await svc().recommend(request)

    @app.post("/v1/similar")
    async def similar(request: SimilarRequest) -> RetrievalResponse:
        return await svc().similar(request.seed_item_id, k=request.k, explain=request.explain)

    @app.post("/v1/explain")
    async def explain(request: ExplainRequest) -> dict[str, object]:
        path = await svc().explain(request.a, request.b, request.max_hops)
        return {"a": request.a, "b": request.b, "path": path}

    @app.get("/v1/health")
    async def health() -> dict[str, str]:
        return await svc().health()

    @app.get("/v1/stats")
    async def stats() -> dict[str, object]:
        return await svc().stats()

    return app


app = create_app()
