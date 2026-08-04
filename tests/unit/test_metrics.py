"""Metrics + fusion tuning on tiny hand-checkable fixtures."""

import math

from constellate.bench.metrics import coverage, evaluate, evaluate_by_kind, novelty, significance
from constellate.bench.run import split_validation, tune_graph_weight

QRELS = {
    "tag_bridge:1": {"10": 1, "11": 1},
    "tag_bridge:2": {"20": 1},
    "cold_start:3": {"30": 1},
    "cold_start:4": {"40": 1},
}


def _run_from_ranking(ranking: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    return {qid: {doc: 1.0 / r for r, doc in enumerate(docs, 1)} for qid, docs in ranking.items()}


def test_evaluate_hand_checked() -> None:
    run = _run_from_ranking(
        {
            "tag_bridge:1": ["10", "99", "11"],  # both relevant found, ranks 1+3
            "tag_bridge:2": ["99", "98"],  # miss
            "cold_start:3": ["30"],  # hit at 1
            "cold_start:4": ["99", "40"],  # hit at 2
        }
    )
    scores = evaluate(QRELS, run)
    assert scores["R@10"] == (1.0 + 0.0 + 1.0 + 1.0) / 4  # recall per query, averaged
    assert scores["RR@10"] == (1.0 + 0.0 + 1.0 + 0.5) / 4  # first hits at 1, none, 1, 2
    assert 0 < scores["nDCG@10"] < 1


def test_evaluate_by_kind_strata() -> None:
    run = _run_from_ranking(
        {
            "tag_bridge:1": ["10"],
            "tag_bridge:2": ["20"],
            "cold_start:3": ["9"],
            "cold_start:4": ["9"],
        }
    )
    by_kind = evaluate_by_kind(QRELS, run)
    assert by_kind["tag_bridge"]["RR@10"] == 1.0
    assert by_kind["cold_start"]["RR@10"] == 0.0


def test_significance_shape() -> None:
    a = _run_from_ranking({q: ["1"] for q in QRELS})
    b = _run_from_ranking({q: list(QRELS[q]) for q in QRELS})  # perfect run
    report = significance(QRELS, {"vector_only": a, "hybrid": b})
    assert isinstance(report["hybrid"]["comparisons"]["vector_only"]["recall@10"], float)  # type: ignore[index]


def test_coverage_and_novelty() -> None:
    recs = [[1, 2], [2, 3]]
    assert coverage(recs, catalog_size=10) == 0.3  # items 1,2,3 of 10
    # item pops: 1→8, 2→2, 3→0(floored to 1); total 16
    n = novelty(recs, {1: 8, 2: 2}, total_interactions=16)
    expected = (-math.log2(8 / 16) - math.log2(2 / 16) * 2 - math.log2(1 / 16)) / 4
    assert abs(n - expected) < 1e-9
    assert coverage([], 10) == 0.0
    assert novelty([], {}, 16) == 0.0


def test_split_validation_stratified_disjoint() -> None:
    qids = [f"{kind}:{i}" for kind in ("a", "b") for i in range(10)]
    val = split_validation(qids, seed=42)
    assert len(val) == 10
    assert sum(q.startswith("a:") for q in val) == 5  # half per kind
    assert val == split_validation(qids, seed=42)  # deterministic


def test_tune_graph_weight_prefers_graph_when_it_wins() -> None:
    # vector never finds the relevant doc, graph always ranks it first
    vector_run = _run_from_ranking({q: ["98", "99"] for q in QRELS})
    graph_run = _run_from_ranking({q: [next(iter(QRELS[q])), "98"] for q in QRELS})
    result = tune_graph_weight(
        QRELS, vector_run, graph_run, {"tag_bridge:1", "cold_start:3"}, rrf_k=60
    )
    assert result["best_graph_weight"] >= 1.0
    assert result["test"]["tuned"]["nDCG@10"] >= result["test"]["baseline_w1.0"]["nDCG@10"]


def test_tune_graph_weight_ties_stay_at_baseline() -> None:
    same = _run_from_ranking({q: list(QRELS[q]) for q in QRELS})
    result = tune_graph_weight(QRELS, same, same, {"tag_bridge:1", "cold_start:3"}, rrf_k=60)
    assert result["best_graph_weight"] == 1.0
