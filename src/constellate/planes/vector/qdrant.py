"""Qdrant adapter — Hydra's vector plane.

Dot-product distance on L2-normalised vectors (= cosine), matching the
pgvector adapter's inner-product score convention. Point ids are the raw
int item_id / user_id (Qdrant natively supports unsigned int ids).

Collections (created by `ensure_collections`, called by the loader and the
conformance fixture):
  items(vector size=dim, distance=Dot)
  users(vector size=dim, distance=Dot)
"""

from collections.abc import Iterable

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    HasIdCondition,
    HnswConfigDiff,
    OptimizersConfigDiff,
    PointStruct,
    SearchParams,
    VectorParams,
)

from constellate.core.types import Candidate, ItemId, UserId, Vector

# HNSW parity with the Lyra hnswlib arm and pgvector (M=16, ef_construction=200,
# ef_search=200). Qdrant's default indexing_threshold (20k per segment) never
# triggers on ~60k points spread over 8 segments — the collection silently runs
# brute-force. Lowering it forces a real HNSW build so the bench measures the
# ANN engine, not accidental exact search.
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
            if not await self._client.collection_exists(name):
                await self._client.create_collection(
                    name,
                    vectors_config=VectorParams(size=self._dim, distance=Distance.DOT),
                    hnsw_config=HnswConfigDiff(m=M, ef_construct=EF_CONSTRUCTION),
                    optimizers_config=OptimizersConfigDiff(indexing_threshold=INDEXING_THRESHOLD),
                )

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
