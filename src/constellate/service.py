"""Shared service layer: REST routes and MCP tools both call this, never the
pipeline or adapters directly. Owns response enrichment (titles into
recommendation metadata) so every surface explains itself the same way.
"""

import json

from constellate.config import PlatformConfig
from constellate.core.pipeline import Pipeline
from constellate.core.protocol import GraphPlane, RelationalPlane
from constellate.core.types import ItemId, RetrievalRequest, RetrievalResponse
from constellate.ingest import CANONICAL_DIR


class Service:
    def __init__(
        self,
        pipeline: Pipeline,
        relational: RelationalPlane,
        graph: GraphPlane,
        config: PlatformConfig,
    ) -> None:
        self._pipeline = pipeline
        self._relational = relational
        self._graph = graph
        self._config = config

    async def recommend(self, request: RetrievalRequest) -> RetrievalResponse:
        response = await self._pipeline.retrieve(request)
        items = await self._relational.hydrate([r.item_id for r in response.recommendations])
        by_id = {i.item_id: i for i in items}
        for rec in response.recommendations:
            if item := by_id.get(rec.item_id):
                rec.metadata = {"title": item.title, "year": item.year, "genres": item.genres}
        return response

    async def similar(
        self, seed_item_id: ItemId, k: int = 20, explain: bool = False
    ) -> RetrievalResponse:
        return await self.recommend(
            RetrievalRequest(seed_item_id=seed_item_id, k=k, explain=explain)
        )

    async def explain(self, a: ItemId, b: ItemId, max_hops: int = 3) -> list[str] | None:
        return await self._graph.path_between(a, b, max_hops)

    async def health(self) -> dict[str, str]:
        return {
            "status": "ok",
            "platform": self._config.platform,
            "config_fingerprint": self._config.fingerprint(),
        }

    async def stats(self) -> dict[str, object]:
        manifest_path = CANONICAL_DIR / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        return {
            "platform": self._config.platform,
            "config_fingerprint": self._config.fingerprint(),
            "dataset": manifest.get("dataset"),
            "rows": {name: meta.get("rows") for name, meta in manifest.get("files", {}).items()},
        }
