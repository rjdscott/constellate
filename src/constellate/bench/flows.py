"""The six flows every platform must answer (prep doc §flows). Hard checks,
not measurements: each flow returns what failed, phase-04 latency numbers come
from the open-loop harness, not from here.

F1 similar        seed item -> fused neighbours, explanations present
F2 personalised   user history -> top-N
F3 cold start     thin-ratings probe seed -> non-empty similar
F4 policy         hard gates actually filter (year floor, genre exclusion)
F5 explanation    multi-hop path returned for a path_required probe pair
F6 agent chain    3 chained calls x3 repeats, per-call latency recorded
"""

import time
from dataclasses import dataclass, field

import pandas as pd

from constellate.core.types import RetrievalRequest, RetrievalResponse
from constellate.service import Service

F4_MIN_YEAR = 2000
F4_EXCLUDE_GENRE = "Horror"
F6_REPEATS = 3


@dataclass
class FlowResult:
    flow: str
    description: str
    failures: list[str] = field(default_factory=list)
    call_ms: list[float] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_json(self) -> dict[str, object]:
        return {
            "flow": self.flow,
            "description": self.description,
            "passed": self.passed,
            "failures": list(self.failures),
            "call_ms": [round(t, 1) for t in self.call_ms],
        }


def _first_seed(probes: pd.DataFrame, kind: str) -> int:
    rows = probes[probes["kind"] == kind]
    if rows.empty:
        raise ValueError(f"probe set has no {kind!r} probes")
    return int(rows.iloc[0]["seed_item_id"])


def _note(result: FlowResult, response: RetrievalResponse, check: str) -> None:
    result.call_ms.append(response.timings.total_ms)
    if not response.recommendations:
        result.failures.append(f"{check}: no recommendations")


async def run_flows(service: Service, probes: pd.DataFrame, user_id: int) -> list[FlowResult]:
    results: list[FlowResult] = []

    f1 = FlowResult("F1", "similar(seed): fused neighbours with explanations")
    seed = _first_seed(probes, "tag_bridge")
    resp = await service.similar(seed, k=10, explain=True)
    _note(f1, resp, f"similar({seed})")
    if resp.recommendations and not any(r.reason for r in resp.recommendations):
        f1.failures.append("no recommendation carries a graph explanation")
    results.append(f1)

    f2 = FlowResult("F2", "personalised top-N for a user")
    _note(f2, await service.recommend(RetrievalRequest(user_id=user_id, k=10)), "recommend")
    results.append(f2)

    f3 = FlowResult("F3", "cold-start seed (thin ratings, genome tags)")
    cold = _first_seed(probes, "cold_start")
    _note(f3, await service.similar(cold, k=10, explain=True), f"similar({cold})")
    results.append(f3)

    f4 = FlowResult("F4", "policy-constrained: hard gates filter results")
    policy: dict[str, object] = {"min_year": F4_MIN_YEAR, "genres_exclude": [F4_EXCLUDE_GENRE]}
    resp = await service.recommend(RetrievalRequest(user_id=user_id, k=10, policy=policy))
    _note(f4, resp, "recommend+policy")
    for rec in resp.recommendations:
        year, genres = rec.metadata.get("year"), rec.metadata.get("genres", [])
        if isinstance(year, int) and year < F4_MIN_YEAR:
            f4.failures.append(f"item {rec.item_id} year {year} violates min_year")
        if isinstance(genres, list) and F4_EXCLUDE_GENRE in genres:
            f4.failures.append(f"item {rec.item_id} violates genres_exclude")
    results.append(f4)

    f5 = FlowResult("F5", "multi-hop explanation path between two items")
    row = probes[probes["kind"] == "path_required"].iloc[0]
    a, b = int(row["seed_item_id"]), int(row["expected_items"][0])
    path = await service.explain(a, b, max_hops=3)
    if path is None:
        f5.failures.append(f"no path found between {a} and {b} (expected within 3 hops)")
    results.append(f5)

    f6 = FlowResult("F6", "agent chain x3: similar -> refine with policy -> explain")
    for _ in range(F6_REPEATS):
        first = await service.similar(seed, k=10)
        _note(f6, first, "chain/similar")
        if not first.recommendations:
            break
        top = first.recommendations[0].item_id
        refined = await service.recommend(
            RetrievalRequest(seed_item_id=top, k=10, policy={"min_year": 1990})
        )
        _note(f6, refined, "chain/refine")
        t0 = time.perf_counter()  # explain returns a bare path, no timings — time it here
        await service.explain(seed, top, max_hops=3)
        f6.call_ms.append((time.perf_counter() - t0) * 1000)
    results.append(f6)

    return results
