"""Relational plane contract: any adapter (DuckDB, Postgres) passes unchanged.

Adapters are constructed pre-loaded with the shared conformance dataset
(defined alongside adapter registration in phase 03).
"""

from kp.core.protocol import RelationalPlane

KNOWN_USER = 1
KNOWN_ITEMS = [1, 2, 3]


async def test_user_context_shape(relational: RelationalPlane) -> None:
    ctx = await relational.get_user_context(KNOWN_USER)
    assert ctx.user_id == KNOWN_USER
    assert ctx.n_ratings >= 0


async def test_hydrate_preserves_order_and_drops_unknown(relational: RelationalPlane) -> None:
    items = await relational.hydrate([*KNOWN_ITEMS, 999_999_999])
    assert [i.item_id for i in items] == KNOWN_ITEMS


async def test_policy_is_a_hard_gate(relational: RelationalPlane) -> None:
    allowed = await relational.apply_policy(KNOWN_ITEMS, None, {})
    assert set(allowed) <= set(KNOWN_ITEMS)  # never invents items


async def test_exclusions_cover_user_history(relational: RelationalPlane) -> None:
    excl = await relational.exclusions(KNOWN_USER)
    assert isinstance(excl, set)
