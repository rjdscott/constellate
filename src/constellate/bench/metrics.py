"""Quality metrics. ir_measures (wraps pytrec_eval) for ranking metrics,
ranx for the paired-significance table, hand-rolled coverage/novelty
(research 05: no maintained lib for those; a dependency would be bloat).

Run format everywhere: ``{query_id: {doc_id: score}}`` with score = 1/rank so
the pipeline's ranking survives pytrec_eval's score-based re-sort exactly.
"""

import math
from collections.abc import Iterable, Mapping, Sequence

import ir_measures
from ranx import Qrels as RanxQrels
from ranx import Run as RanxRun
from ranx import compare

QrelsDict = dict[str, dict[str, int]]
RunDict = dict[str, dict[str, float]]

MEASURE_NAMES = ("R@10", "R@50", "nDCG@10", "RR@10")


def evaluate(qrels: QrelsDict, run: RunDict) -> dict[str, float]:
    """Aggregate MEASURE_NAMES over the queries present in qrels.

    Queries missing from the run score 0 — pytrec_eval would silently drop
    them from the mean otherwise, inflating every metric.
    """
    measures = [ir_measures.parse_measure(name) for name in MEASURE_NAMES]
    filled = {qid: run.get(qid, {}) for qid in qrels}
    return {
        str(m): float(v) for m, v in ir_measures.calc_aggregate(measures, qrels, filled).items()
    }


def evaluate_by_kind(qrels: QrelsDict, run: RunDict) -> dict[str, dict[str, float]]:
    """Stratified metrics; query ids are ``<kind>:<seed>`` so kind is the prefix."""
    kinds = sorted({qid.split(":", 1)[0] for qid in qrels})
    return {
        kind: evaluate(
            {q: rels for q, rels in qrels.items() if q.startswith(f"{kind}:")},
            run,
        )
        for kind in kinds
    }


def significance(
    qrels: QrelsDict, runs: Mapping[str, RunDict], metrics: Sequence[str] = ("recall@10", "ndcg@10")
) -> dict[str, object]:
    """ranx paired student-t comparison across arms; returns report.to_dict()."""
    report = compare(
        RanxQrels(qrels),
        [RanxRun(run, name=name) for name, run in runs.items()],
        metrics=list(metrics),
        stat_test="student",
    )
    out: dict[str, object] = report.to_dict()
    return out


def coverage(recommendations: Iterable[Sequence[int]], catalog_size: int) -> float:
    """Fraction of the catalog that appears in at least one top-k list."""
    seen: set[int] = set()
    for recs in recommendations:
        seen.update(recs)
    return len(seen) / catalog_size if catalog_size else 0.0


def novelty(
    recommendations: Iterable[Sequence[int]],
    n_ratings: Mapping[int, int],
    total_interactions: int,
) -> float:
    """Mean self-information -log2(p) of recommended items; p = train-rating
    share, floored at one rating so zero-rating items stay finite (maximally
    novel), higher = more long-tail."""
    values = [
        -math.log2(max(n_ratings.get(item, 0), 1) / total_interactions)
        for recs in recommendations
        for item in recs
    ]
    return sum(values) / len(values) if values else 0.0
