"""Shared service layer: REST routes and MCP tools both call this, never the
pipeline or adapters directly. Owns response enrichment (titles into
recommendation metadata) so every surface explains itself the same way.
"""

import csv
import json
from collections.abc import Sequence

from constellate.config import PlatformConfig
from constellate.core.pipeline import Pipeline
from constellate.core.protocol import GraphPlane, RelationalPlane, VectorPlane
from constellate.core.types import (
    Item,
    ItemId,
    RetrievalRequest,
    RetrievalResponse,
    UserContext,
    UserId,
)
from constellate.ingest import CANONICAL_DIR, RAW_DIR

# Genome tags are dataset-wide (not platform-scoped), so this lives at module
# state rather than on Service — every platform's Service reads the same 1128
# rows. TAGS_PATH is a module attribute (not a default arg) so tests can
# monkeypatch it and still see the change: default args bind at import time.
TAGS_PATH = RAW_DIR / "ml-25m" / "genome-tags.csv"
_tags_cache: dict[str, str] | None = None


def load_tags() -> dict[str, str]:
    """{"742": "zombies", ...} from genome-tags.csv, read once and cached."""
    global _tags_cache
    if _tags_cache is None:
        if not TAGS_PATH.is_file():
            raise FileNotFoundError(f"genome tags not found — run ingest to populate {TAGS_PATH}")
        with TAGS_PATH.open(newline="") as f:
            _tags_cache = {row["tagId"]: row["tag"] for row in csv.DictReader(f)}
    return _tags_cache


class Service:
    def __init__(
        self,
        pipeline: Pipeline,
        relational: RelationalPlane,
        vector: VectorPlane,
        graph: GraphPlane,
        config: PlatformConfig,
    ) -> None:
        self._pipeline = pipeline
        self._relational = relational
        self._vector = vector
        self._graph = graph
        self._config = config

    def close(self) -> None:
        # the vector plane holds a connection too (qdrant); the in-process
        # planes have no close() and the callable guard skips them
        for plane in (self._relational, self._vector, self._graph):
            close = getattr(plane, "close", None)
            if callable(close):
                close()

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

    async def search_items(self, q: str, limit: int = 20) -> list[Item]:
        return await self._relational.search_items(q, limit)

    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]:
        return await self._relational.hydrate(ids)

    async def user_context(self, user_id: UserId) -> UserContext:
        return await self._relational.get_user_context(user_id)

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
