"""Policy gates: closed vocabulary, hard filters, engine-agnostic.

Every relational adapter hydrates then filters through this one function so
the vocabulary and the gate semantics can never drift between platforms.
An unknown policy key raises instead of silently allowing everything.
"""

from typing import Any

from constellate.core.errors import KnowledgePlaneError
from constellate.core.types import Item, ItemId

POLICY_KEYS = frozenset({"min_year", "max_year", "genres_any", "genres_exclude", "min_ratings"})


def filter_by_policy(items: list[Item], policy: dict[str, object]) -> list[ItemId]:
    unknown = set(policy) - POLICY_KEYS
    if unknown:
        raise KnowledgePlaneError(f"unknown policy keys: {sorted(unknown)}")
    p: dict[str, Any] = policy
    out: list[ItemId] = []
    for item in items:
        if "min_year" in p and (item.year is None or item.year < p["min_year"]):
            continue
        if "max_year" in p and (item.year is None or item.year > p["max_year"]):
            continue
        if "genres_any" in p and not set(item.genres) & set(p["genres_any"]):
            continue
        if "genres_exclude" in p and set(item.genres) & set(p["genres_exclude"]):
            continue
        if "min_ratings" in p and item.n_ratings < p["min_ratings"]:
            continue
        out.append(item.item_id)
    return out
