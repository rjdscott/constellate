"""Weighted reciprocal rank fusion (RRF, Cormack et al.; k=60 default, config-driven)."""

from collections.abc import Mapping, Sequence

from constellate.core.types import Candidate, ItemId, PlaneName


class FusedCandidate:
    __slots__ = ("hops", "item_id", "path", "score", "sources")

    def __init__(self, item_id: ItemId) -> None:
        self.item_id = item_id
        self.score = 0.0
        self.sources: list[PlaneName] = []
        self.path: list[str] | None = None
        self.hops: int | None = None


def rrf(
    ranked_lists: Mapping[PlaneName, Sequence[Candidate]],
    *,
    k: int = 60,
    weights: Mapping[str, float] | None = None,
) -> list[FusedCandidate]:
    """Fuse per-plane ranked lists: score(i) = sum_p w_p / (k + rank_p(i)).

    Rank-based, so heterogeneous plane scores need no normalisation. Ties broken
    by item_id for determinism. Graph paths survive fusion so explanations can
    be rendered downstream.
    """
    fused: dict[ItemId, FusedCandidate] = {}
    for plane, candidates in ranked_lists.items():
        w = 1.0 if weights is None else weights.get(plane, 1.0)
        for rank, cand in enumerate(candidates, start=1):
            entry = fused.setdefault(cand.item_id, FusedCandidate(cand.item_id))
            entry.score += w / (k + rank)
            if plane not in entry.sources:
                entry.sources.append(plane)
            if cand.path is not None and entry.path is None:
                entry.path = cand.path
                entry.hops = cand.hops
    return sorted(fused.values(), key=lambda f: (-f.score, f.item_id))
