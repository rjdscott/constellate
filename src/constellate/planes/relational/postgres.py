"""Postgres relational adapter — Orion's source of truth (ADR 0004).

Expects the tables `make load PLATFORM=orion` builds:
  items(item_id, title, year, genres text[], n_ratings, mean_rating)
  users(user_id, n_train, mean_rating)
  interactions(user_id, item_id, rating, ts, split)

Owns the asyncpg pool shared by every Orion plane adapter (one Postgres,
one pool); its close() tears the pool down for all of them — the vector and
graph adapters deliberately have no close().
"""

from collections.abc import Sequence

import asyncpg

from constellate.core.types import Item, ItemId, UserContext, UserId
from constellate.planes.relational.policy import filter_by_policy

ITEM_COLS = "item_id, title, year, genres, n_ratings, mean_rating"


def _item(r: asyncpg.Record) -> Item:
    return Item(
        item_id=r["item_id"],
        title=r["title"],
        year=r["year"],
        genres=list(r["genres"] or []),
        n_ratings=r["n_ratings"],
        mean_rating=r["mean_rating"],
        popularity=float(r["n_ratings"]),
    )


class PostgresRelational:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def close(self) -> None:
        # Service.close() is synchronous; terminate() is asyncpg's sync
        # teardown. Abrupt is fine at shutdown — nothing is mid-transaction.
        self._pool.terminate()

    async def get_user_context(self, user_id: UserId) -> UserContext:
        row = await self._pool.fetchrow("SELECT n_train FROM users WHERE user_id = $1", user_id)
        return UserContext(user_id=user_id, n_ratings=row["n_train"] if row else 0)

    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]:
        if not ids:
            return []
        rows = await self._pool.fetch(
            f"SELECT {ITEM_COLS} FROM items WHERE item_id = ANY($1::int[])",
            list(ids),
        )
        by_id = {r["item_id"]: r for r in rows}
        return [_item(r) for i in ids if (r := by_id.get(i)) is not None]

    async def search_items(self, q: str, limit: int = 20) -> list[Item]:
        # strpos(), not ILIKE: a '%' typed into the search box is a character,
        # not a wildcard
        rows = await self._pool.fetch(
            f"SELECT {ITEM_COLS} FROM items WHERE strpos(lower(title), lower($1)) > 0"
            " ORDER BY n_ratings DESC, item_id LIMIT $2",
            q,
            limit,
        )
        return [_item(r) for r in rows]

    async def apply_policy(
        self, ids: Sequence[ItemId], ctx: UserContext | None, policy: dict[str, object]
    ) -> list[ItemId]:
        if not policy:
            filter_by_policy([], policy)
            return list(ids)
        if not ids:
            filter_by_policy([], policy)
            return []
        return filter_by_policy(await self.hydrate(ids), policy)

    async def exclusions(self, user_id: UserId) -> set[ItemId]:
        rows = await self._pool.fetch(
            "SELECT DISTINCT item_id FROM interactions WHERE user_id = $1 AND split = 'train'",
            user_id,
        )
        return {r["item_id"] for r in rows}
