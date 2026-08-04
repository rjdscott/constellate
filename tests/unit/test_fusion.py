from kp.core.fusion import rrf
from kp.core.types import Candidate


def _cands(source: str, ids: list[int]) -> list[Candidate]:
    return [
        Candidate(item_id=i, score=1.0 / r, source=source)  # type: ignore[arg-type]
        for r, i in enumerate(ids, start=1)
    ]


def test_rrf_known_values() -> None:
    fused = rrf({"vector": _cands("vector", [1, 2]), "graph": _cands("graph", [2, 3])}, k=60)
    by_id = {f.item_id: f for f in fused}
    assert by_id[1].score == 1 / 61
    assert by_id[2].score == 1 / 62 + 1 / 61  # rank 2 in vector, rank 1 in graph
    assert by_id[3].score == 1 / 62
    assert fused[0].item_id == 2  # appears in both lists → wins
    assert by_id[2].sources == ["vector", "graph"]


def test_weights_shift_ranking() -> None:
    lists = {"vector": _cands("vector", [1]), "graph": _cands("graph", [2])}
    fused = rrf(lists, k=60, weights={"vector": 1.0, "graph": 3.0})
    assert fused[0].item_id == 2


def test_deterministic_tie_break_by_item_id() -> None:
    fused = rrf({"vector": _cands("vector", [5, 3])}, k=0)
    tied = rrf({"vector": _cands("vector", [5]), "graph": _cands("graph", [3])}, k=60)
    assert tied[0].item_id == 3  # equal scores → lower item_id first
    assert [f.item_id for f in fused] == [5, 3]


def test_graph_path_survives_fusion() -> None:
    graph = [Candidate(item_id=7, score=0.5, source="graph", path=["m:1", "t:2", "m:7"], hops=2)]
    fused = rrf({"vector": _cands("vector", [7]), "graph": graph}, k=60)
    assert fused[0].path == ["m:1", "t:2", "m:7"]
    assert fused[0].hops == 2
