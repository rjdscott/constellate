"""DuckDB relational adapter — Lyra's source of truth.

Expects three tables/views on the connection it is given:
  items(item_id, title, year, genres, n_ratings, mean_rating)
  users(user_id, n_train, mean_rating)
  interactions(user_id, item_id, rating, ts, split)

`from_canonical` builds them from data/canonical/: item stats materialize
once (small), interactions stay a view over the parquet — it is sorted by
user_id, so exclusion lookups hit zonemap-pruned row groups, not a scan.

Policy is a hard gate with a closed vocabulary; an unknown policy key raises
instead of silently allowing everything through.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb

from constellate.core.types import Item, ItemId, UserContext, UserId
from constellate.planes.relational.policy import filter_by_policy

ITEM_COLS = "item_id, title, year, genres, n_ratings, mean_rating"


def _item(r: Any) -> Item:
    return Item(
        item_id=r[0],
        title=r[1],
        year=r[2],
        genres=list(r[3] or []),
        n_ratings=r[4],
        mean_rating=r[5],
        popularity=float(r[4]),
    )


class DuckDBRelational:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    @classmethod
    def from_canonical(cls, canonical: Path) -> "DuckDBRelational":
        conn = duckdb.connect(":memory:")
        conn.execute(
            f"""
            CREATE TABLE items AS
            SELECT i.item_id, i.title, i.year, i.genres,
                   coalesce(s.n, 0)::INT AS n_ratings, s.mean AS mean_rating
            FROM read_parquet('{canonical / "items.parquet"}') i
            LEFT JOIN (
                SELECT item_id, count(*) AS n, avg(rating) AS mean
                FROM read_parquet('{canonical / "interactions.parquet"}')
                WHERE split = 'train' GROUP BY item_id
            ) s USING (item_id);
            CREATE TABLE users AS
            SELECT * FROM read_parquet('{canonical / "users.parquet"}');
            CREATE VIEW interactions AS
            SELECT * FROM read_parquet('{canonical / "interactions.parquet"}');
            """
        )
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    async def get_user_context(self, user_id: UserId) -> UserContext:
        row = self._conn.execute(
            "SELECT n_train FROM users WHERE user_id = ?", [user_id]
        ).fetchone()
        return UserContext(user_id=user_id, n_ratings=row[0] if row else 0)

    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]:
        if not ids:
            return []
        rows = self._conn.execute(
            f"SELECT {ITEM_COLS} FROM items WHERE item_id IN ?",
            [list(ids)],
        ).fetchall()
        by_id = {r[0]: r for r in rows}
        return [_item(r) for i in ids if (r := by_id.get(i)) is not None]

    async def search_items(self, q: str, limit: int = 20) -> list[Item]:
        # contains(), not ILIKE: a '%' typed into the search box is a character,
        # not a wildcard
        rows = self._conn.execute(
            f"SELECT {ITEM_COLS} FROM items WHERE contains(lower(title), lower(?))"
            " ORDER BY n_ratings DESC, item_id LIMIT ?",
            [q, limit],
        ).fetchall()
        return [_item(r) for r in rows]

    async def apply_policy(
        self, ids: Sequence[ItemId], ctx: UserContext | None, policy: dict[str, object]
    ) -> list[ItemId]:
        if not policy:
            filter_by_policy([], policy)  # still validates the (empty) vocabulary
            return list(ids)
        if not ids:
            filter_by_policy([], policy)
            return []
        return filter_by_policy(await self.hydrate(ids), policy)

    async def exclusions(self, user_id: UserId) -> set[ItemId]:
        rows = self._conn.execute(
            "SELECT DISTINCT item_id FROM interactions WHERE user_id = ? AND split = 'train'",
            [user_id],
        ).fetchall()
        return {r[0] for r in rows}
