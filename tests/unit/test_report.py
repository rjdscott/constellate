"""Report rendering (arm-aware sections) on synthetic artifacts — no
bench/results I/O beyond `equivalence`'s config/<platform>.yaml tolerance
read, which real platform configs satisfy."""

from typing import Any

from constellate.bench.report import _arm, chronological, embedding_ablation, equivalence

RETRIEVAL_ARMS = ("vector_only", "graph_only", "hybrid")


def _metrics(r10: float, ndcg10: float) -> dict[str, float]:
    return {"R@10": r10, "R@50": r10 * 2, "nDCG@10": ndcg10, "RR@10": ndcg10}


def _artifact(
    platform: str,
    embedding_arm: str | None,
    *,
    hybrid_r10: float = 0.10,
    hybrid_ndcg10: float = 0.05,
    genome_subset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    arms = {arm: {"overall": _metrics(hybrid_r10, hybrid_ndcg10)} for arm in RETRIEVAL_ARMS}
    quality: dict[str, Any] = {
        "n_probes": 10,
        "arms": arms,
        "embedding_coverage": {
            "arm": embedding_arm or "svd",
            "items": 100,
            "native": 50,
            "fraction_native": 0.5,
        },
    }
    if genome_subset is not None:
        quality["genome_subset"] = genome_subset
    artifact: dict[str, Any] = {"platform": platform, "quality": quality}
    if embedding_arm is not None:
        artifact["embedding_arm"] = embedding_arm
    return artifact


def test_embedding_arm_missing_key_defaults_to_svd() -> None:
    assert _arm(_artifact("orion", None)) == "svd"
    assert _arm(_artifact("orion", "neural")) == "neural"


def test_embedding_ablation_absent_when_only_svd_present() -> None:
    artifacts = {"a": _artifact("orion", "svd"), "b": _artifact("orion", None)}
    assert embedding_ablation(artifacts) == []


def test_embedding_ablation_renders_with_right_signed_deltas() -> None:
    svd_a = _artifact("orion", "svd", hybrid_r10=0.10, hybrid_ndcg10=0.05)
    neural_a = _artifact("orion", "neural", hybrid_r10=0.15, hybrid_ndcg10=0.02)
    lines = embedding_ablation({"svd-run": svd_a, "neural-run": neural_a})
    text = "\n".join(lines)
    assert "## Embedding arm ablation (svd vs neural)" in text
    assert "### orion" in text
    hybrid_row = next(line for line in lines if line.startswith("| hybrid"))
    assert "+0.0500" in hybrid_row  # R@10: 0.15 - 0.10
    assert "-0.0300" in hybrid_row  # nDCG@10: 0.02 - 0.05


def test_embedding_ablation_genome_subset_table_when_both_nonempty() -> None:
    gs_svd = {"n_probes": 5, "arms": {arm: _metrics(0.2, 0.1) for arm in RETRIEVAL_ARMS}}
    gs_neural = {"n_probes": 5, "arms": {arm: _metrics(0.3, 0.2) for arm in RETRIEVAL_ARMS}}
    svd_a = _artifact("orion", "svd", genome_subset=gs_svd)
    neural_a = _artifact("orion", "neural", genome_subset=gs_neural)
    lines = embedding_ablation({"a": svd_a, "b": neural_a})
    assert any("Genome subset (5 probes" in line for line in lines)


def test_embedding_ablation_skips_genome_table_when_either_side_empty() -> None:
    svd_a = _artifact("orion", "svd", genome_subset={"n_probes": 0})
    neural_a = _artifact("orion", "neural", genome_subset={"n_probes": 0})
    lines = embedding_ablation({"a": svd_a, "b": neural_a})
    assert not any("Genome subset" in line for line in lines)
    # one side missing genome_subset entirely (older-shape artifact) also skips
    svd_a2 = _artifact("orion", "svd")
    neural_a2 = _artifact("orion", "neural", genome_subset={"n_probes": 5, "arms": {}})
    lines2 = embedding_ablation({"a": svd_a2, "b": neural_a2})
    assert not any("Genome subset" in line for line in lines2)


def test_equivalence_empty_without_both_lyra_and_others() -> None:
    assert equivalence({"a": _artifact("orion", "svd")}) == []
    assert equivalence({"a": _artifact("lyra", "svd")}) == []


def test_equivalence_pre_change_shape_svd_only() -> None:
    lyra = _artifact("lyra", None, hybrid_r10=0.10, hybrid_ndcg10=0.05)
    orion = _artifact("orion", None, hybrid_r10=0.15, hybrid_ndcg10=0.02)
    lines = equivalence({"lyra-run": lyra, "orion-run": orion})
    text = "\n".join(lines)
    assert "## Cross-platform quality equivalence (hybrid arm, vs Lyra): svd" in text
    row = next(line for line in lines if line.startswith("| orion-run"))
    assert "+0.0500" in row  # R@10 delta
    assert "-0.0300" in row  # nDCG@10 delta


def test_equivalence_partitions_arms_into_separate_sections() -> None:
    artifacts = {
        "lyra-svd": _artifact("lyra", "svd"),
        "lyra-neural": _artifact("lyra", "neural"),
        "orion-svd": _artifact("orion", "svd"),
        "orion-neural": _artifact("orion", "neural"),
    }
    lines = equivalence(artifacts)
    text = "\n".join(lines)
    assert "vs Lyra): svd" in text
    assert "vs Lyra): neural" in text
    # each section only carries the non-lyra run for its own arm
    svd_section = text.split(": svd")[1].split("## Cross-platform")[0]
    assert "orion-svd" in svd_section
    assert "orion-neural" not in svd_section


def test_chronological_orders_by_utc_not_filename() -> None:
    # sha sits before the timestamp in artifact filenames, so filename order
    # inverts chronology whenever a lexicographically-smaller sha is newer —
    # the exact case that would silently serve a stale ablation baseline
    old = {**_artifact("lyra", "svd"), "utc": "2026-08-05T01:00:00+00:00"}
    new = {**_artifact("lyra", "neural"), "utc": "2026-08-10T09:00:00+00:00"}
    filename_order = {"lyra-fa9623e-20260805T010000Z": old, "lyra-1a2b3c4-20260810T090000Z": new}
    assert sorted(filename_order) != [
        "lyra-fa9623e-20260805T010000Z",
        "lyra-1a2b3c4-20260810T090000Z",
    ]

    ordered = chronological(dict(sorted(filename_order.items())))
    assert [a["utc"] for a in ordered.values()] == [old["utc"], new["utc"]]
    # newest-per-(platform, arm) picks ride on insertion order downstream
    assert list(ordered)[-1] == "lyra-1a2b3c4-20260810T090000Z"
