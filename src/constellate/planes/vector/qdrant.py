"""Qdrant adapter — Hydra's vector plane.

Dot-product distance on L2-normalised vectors (= cosine), matching the
pgvector adapter's inner-product score convention. Point ids are the raw
int item_id / user_id (Qdrant natively supports unsigned int ids).

Collections (created by `ensure_collections`, called by the loader and the
conformance fixture):
  items(vector size=dim, distance=Dot)
  users(vector size=dim, distance=Dot)
"""

import asyncio
from collections.abc import Iterable

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    CollectionInfo,
    Distance,
    Filter,
    HasIdCondition,
    HnswConfigDiff,
    OptimizersConfigDiff,
    PointStruct,
    SearchParams,
    VectorParams,
)

from constellate.core.errors import ConfigError
from constellate.core.types import Candidate, ItemId, UserId, Vector

# HNSW parity with the Lyra hnswlib arm and pgvector (M=16, ef_construction=200,
# ef_search=200). indexing_threshold is measured in KILOBYTES per segment (at
# 256-dim fp32, 1KB/vector, so the numbers read like point counts by
# coincidence): the 20000KB default never triggers on ~60k points spread over
# 8 segments — the collection silently runs brute-force. Lowering it forces a
# real HNSW build so the bench measures the ANN engine, not accidental exact
# search.
M = 16
EF_CONSTRUCTION = 200
EF_SEARCH = 200
INDEXING_THRESHOLD = 1000


class QdrantVector:
    def __init__(
        self,
        client: AsyncQdrantClient,
        *,
        items_collection: str = "items",
        users_collection: str = "users",
        dim: int,
    ) -> None:
        self._client = client
        self._items = items_collection
        self._users = users_collection
        self._dim = dim

    async def ensure_collections(self) -> None:
        for name in (self._items, self._users):
            if await self._client.collection_exists(name):
                self._check_config(name, await self._client.get_collection(name))
                continue
            await self._client.create_collection(
                name,
                vectors_config=VectorParams(size=self._dim, distance=Distance.DOT),
                hnsw_config=HnswConfigDiff(m=M, ef_construct=EF_CONSTRUCTION),
                optimizers_config=OptimizersConfigDiff(indexing_threshold=INDEXING_THRESHOLD),
            )

    def _check_config(self, name: str, info: CollectionInfo) -> None:
        """A pre-existing collection must be the one we would have created.

        Silently reusing a leftover collection is the expensive kind of wrong:
        the wrong distance ranks nothing like dot product, and the default
        indexing threshold leaves the collection brute-forcing while the bench
        reports it as ANN. Cheaper to refuse than to explain the numbers later.
        """
        vectors = info.config.params.vectors
        expected = {
            "size": self._dim,
            "distance": Distance.DOT,
            "hnsw m": M,
            "hnsw ef_construct": EF_CONSTRUCTION,
            "indexing_threshold": INDEXING_THRESHOLD,
        }
        actual = {
            "size": getattr(vectors, "size", None),
            "distance": getattr(vectors, "distance", None),
            "hnsw m": getattr(info.config.hnsw_config, "m", None),
            "hnsw ef_construct": getattr(info.config.hnsw_config, "ef_construct", None),
            "indexing_threshold": getattr(info.config.optimizer_config, "indexing_threshold", None),
        }
        bad = [
            f"{k} expected {expected[k]!r}, got {actual[k]!r}"
            for k in expected
            if actual[k] != expected[k]
        ]
        if bad:
            raise ConfigError(f"qdrant collection {name!r} config mismatch — " + "; ".join(bad))

    def close(self) -> None:
        # same schedule-or-run dance as the memgraph adapter: Service.close() is
        # sync, AsyncQdrantClient.close() is a coroutine (task kept off the GC).
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._client.close())
        else:
            self._closing = loop.create_task(self._client.close())

    async def search(self, vec: Vector, k: int, exclude: set[ItemId]) -> list[Candidate]:
        query_filter = (
            Filter(must_not=[HasIdCondition(has_id=sorted(exclude))]) if exclude else None
        )
        result = await self._client.query_points(
            self._items,
            query=vec,
            limit=k,
            query_filter=query_filter,
            search_params=SearchParams(hnsw_ef=EF_SEARCH),
            with_payload=False,
        )
        return [
            Candidate(item_id=int(hit.id), score=float(hit.score), source="vector")
            for hit in result.points
        ]

    async def get_item_vector(self, item_id: ItemId) -> Vector | None:
        return await self._fetch_vec(self._items, item_id)

    async def get_user_vector(self, user_id: UserId) -> Vector | None:
        return await self._fetch_vec(self._users, user_id)

    async def upsert(self, rows: Iterable[tuple[ItemId, Vector]]) -> None:
        points = [PointStruct(id=item_id, vector=vec) for item_id, vec in rows]
        await self._client.upsert(self._items, points=points)

    async def _fetch_vec(self, collection: str, point_id: int) -> Vector | None:
        records = await self._client.retrieve(collection, ids=[point_id], with_vectors=True)
        if not records:
            return None
        return records[0].vector  # type: ignore[return-value]
