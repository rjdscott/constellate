"""pgvector adapter — Orion's vector plane (ADR 0004).

HNSW over halfvec (fp16, 50% storage; recall loss negligible at 256d),
inner-product distance on L2-normalised vectors (= cosine). Filtered
queries rely on 0.8.x iterative index scans (`hnsw.iterative_scan =
relaxed_order`): the index keeps yielding until k rows survive the
exclusion anti-join instead of overfiltering.

Tables (built by `make load PLATFORM=orion`):
  item_vectors(item_id int primary key, vec halfvec(D))  + HNSW halfvec_ip_ops
  user_vectors(user_id int primary key, vec halfvec(D))
"""

from collections.abc import Iterable

import asyncpg

from constellate.core.types import Candidate, ItemId, UserId, Vector

EF_SEARCH = 200  # parity with Lyra's hnsw ablation arm


class PgVector:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def search(self, vec: Vector, k: int, exclude: set[ItemId]) -> list[Candidate]:
        qvec = _lit(vec)
        async with self._pool.acquire() as conn:
            # session GUCs: scoped to this pooled connection, cheap to reassert
            await conn.execute(f"SET hnsw.ef_search = {EF_SEARCH}")
            await conn.execute("SET hnsw.iterative_scan = relaxed_order")
            rows = await conn.fetch(
                """
                SELECT item_id, -(vec <#> $1::halfvec) AS score
                FROM item_vectors
                WHERE NOT (item_id = ANY($2::int[]))
                ORDER BY vec <#> $1::halfvec
                LIMIT $3
                """,
                qvec,
                sorted(exclude),
                k,
            )
        return [
            Candidate(item_id=r["item_id"], score=float(r["score"]), source="vector") for r in rows
        ]

    async def get_item_vector(self, item_id: ItemId) -> Vector | None:
        return await self._fetch_vec("SELECT vec FROM item_vectors WHERE item_id = $1", item_id)

    async def get_user_vector(self, user_id: UserId) -> Vector | None:
        return await self._fetch_vec("SELECT vec FROM user_vectors WHERE user_id = $1", user_id)

    async def upsert(self, rows: Iterable[tuple[ItemId, Vector]]) -> None:
        await self._pool.executemany(
            "INSERT INTO item_vectors(item_id, vec) VALUES ($1, $2::halfvec)"
            " ON CONFLICT (item_id) DO UPDATE SET vec = EXCLUDED.vec",
            [(item_id, _lit(vec)) for item_id, vec in rows],
        )

    async def _fetch_vec(self, sql: str, key: int) -> Vector | None:
        value = await self._pool.fetchval(sql, key)
        if value is None:
            return None
        return _parse(str(value))


def _lit(vec: Vector) -> str:
    """pgvector text form: '[0.1,0.2,...]' — passed as text, cast in SQL."""
    return "[" + ",".join(f"{x:g}" for x in vec) + "]"


def _parse(text: str) -> Vector:
    return [float(x) for x in text.strip("[]").split(",")]
