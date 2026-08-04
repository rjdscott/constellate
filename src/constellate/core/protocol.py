"""Plane contracts. Adapters implement these; nothing imports adapters but the factory."""

from collections.abc import Iterable, Sequence
from typing import Protocol

from constellate.core.types import Candidate, Edge, Item, ItemId, UserContext, UserId, Vector


class RelationalPlane(Protocol):
    """Source of truth: user context, hydration, policy gates, exclusions."""

    async def get_user_context(self, user_id: UserId) -> UserContext: ...

    async def hydrate(self, ids: Sequence[ItemId]) -> list[Item]: ...

    async def apply_policy(
        self, ids: Sequence[ItemId], ctx: UserContext | None, policy: dict[str, object]
    ) -> list[ItemId]: ...

    async def exclusions(self, user_id: UserId) -> set[ItemId]: ...


class VectorPlane(Protocol):
    """Derived projection: nearest-neighbour candidate generation."""

    async def search(self, vec: Vector, k: int, exclude: set[ItemId]) -> list[Candidate]: ...

    async def get_item_vector(self, item_id: ItemId) -> Vector | None: ...

    async def get_user_vector(self, user_id: UserId) -> Vector | None: ...

    async def upsert(self, rows: Iterable[tuple[ItemId, Vector]]) -> None: ...


class GraphPlane(Protocol):
    """Derived projection: typed weighted traversal with paths."""

    async def expand(
        self,
        seeds: Sequence[ItemId],
        max_hops: int,
        limit: int,
        edge_types: Sequence[str] | None = None,
    ) -> list[Candidate]: ...

    async def path_between(self, a: ItemId, b: ItemId, max_hops: int) -> list[str] | None: ...

    async def upsert_edges(self, edges: Iterable[Edge]) -> None: ...
