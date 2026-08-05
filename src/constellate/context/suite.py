"""Fixed context-plane task suite (ADR 0012): deterministic scoring of
tool-call behavior, not prose quality, run against either driver.

    uv run python -m constellate.context.suite --driver anthropic
    uv run python -m constellate.context.suite --driver local --reps 3 --model qwen3:8b

Demo-class numbers only — never citable alongside the benchmark harness
(ADR 0011); artifacts land in `bench/context/`, outside `bench/report.py`'s
glob on purpose.
"""

import argparse
import asyncio
import dataclasses
import json
import os
import platform as host_platform
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from constellate.context.drivers import (
    HAIKU_45_USD_PER_MTOK_IN,
    HAIKU_45_USD_PER_MTOK_OUT,
    AnthropicDriver,
    Driver,
    OllamaDriver,
)
from constellate.context.loop import ToolCallRecord, Transcript, run_task

BENCH_DIR = Path(__file__).resolve().parents[3] / "bench" / "context"

_TITLE_RE = re.compile(r'"title":\s*"([^"]*)"')
_ITEM_ID_RE = re.compile(r'"item_id":\s*(\d+)')


@dataclass
class TaskScore:
    tool_calls_ok: bool
    answer_grounded: bool
    notes: str


@dataclass
class Task:
    id: str
    prompt: str
    check: Callable[[Transcript], TaskScore]


# --- scoring helpers ---------------------------------------------------


def _tool_records(transcript: Transcript) -> list[ToolCallRecord]:
    return [rec for turn in transcript.turns for rec in turn.tool_calls]


def _title_key(title: str) -> str:
    """Normalize a movie title for containment checks: models rewrite the
    catalog's "Terminator, The (1984)" as "The Terminator (1984)" (or keep
    it, unpredictably) and wrap titles in markdown, so raw substring
    matching scores grounded answers as hallucinations. Strip every
    parenthetical (years AND ml-25m's original-language alternate titles,
    e.g. "Diving Bell and the Butterfly, The (Scaphandre et le papillon,
    Le) (2007)"), collapse non-alphanumerics, and drop article tokens
    entirely — applied to both sides, so either article form matches
    either way."""
    t = re.sub(r"\([^)]*\)", " ", title.lower())
    t = re.sub(r"[^a-z0-9]+", " ", t)
    words = [w for w in t.split() if w not in ("the", "a", "an")]
    key = " ".join(words)
    if not key:  # degenerate: title was entirely parenthetical
        words = [
            w
            for w in re.sub(r"[^a-z0-9]+", " ", title.lower()).split()
            if w not in ("the", "a", "an")
        ]
        key = " ".join(words)
    return key


def _titles_in_digest(digest: str) -> set[str]:
    return {key for m in _TITLE_RE.findall(digest) if (key := _title_key(m))}


def _first_item_id(digest: str) -> int | None:
    m = _ITEM_ID_RE.search(digest)
    return int(m.group(1)) if m else None


def _mentions_any(text: str, candidates: set[str]) -> bool:
    haystack = f" {_title_key(text)} "
    return any(f" {c} " in haystack for c in candidates if c)


def _expect_calls(
    transcript: Transcript, expected: list[dict[str, object]]
) -> tuple[bool, list[str]]:
    """`expected`: one dict per call, in order, `{"tool": name, **args}`."""
    records = _tool_records(transcript)
    if len(records) != len(expected):
        got = [r.name for r in records]
        return False, [f"expected {len(expected)} tool call(s), got {len(records)}: {got}"]
    problems: list[str] = []
    for i, (record, exp) in enumerate(zip(records, expected, strict=True)):
        want_tool = exp["tool"]
        if record.name != want_tool:
            problems.append(f"call {i}: expected tool {want_tool!r}, got {record.name!r}")
            continue
        for key, want in exp.items():
            if key == "tool":
                continue
            got_arg = record.args.get(key)
            if got_arg != want:
                problems.append(f"call {i} arg {key!r}: expected {want!r}, got {got_arg!r}")
    return not problems, problems


def _retrieval_check(expected: list[dict[str, object]]) -> Callable[[Transcript], TaskScore]:
    """Generic checker for tasks whose tool result(s) carry item titles:
    tool_calls_ok from `_expect_calls`, grounded if the final answer mentions
    a title actually returned by any of the calls."""

    def check(transcript: Transcript) -> TaskScore:
        ok, problems = _expect_calls(transcript, expected)
        titles: set[str] = set()
        for record in _tool_records(transcript):
            titles |= _titles_in_digest(record.result_json or record.result_digest)
        grounded = bool(transcript.final_text) and _mentions_any(transcript.final_text, titles)
        if not grounded:
            problems.append("final answer missing or doesn't mention a returned title")
        return TaskScore(ok, grounded, "; ".join(problems) or "ok")

    return check


def _check_explain_connection(
    item_a: int, item_b: int, platform: str
) -> Callable[[Transcript], TaskScore]:
    """explain_connection returns a graph path, not titles — grounded here
    means a non-empty answer that references the two ids asked about."""

    def check(transcript: Transcript) -> TaskScore:
        ok, problems = _expect_calls(
            transcript,
            [
                {
                    "tool": "explain_connection",
                    "item_a": item_a,
                    "item_b": item_b,
                    "platform": platform,
                }
            ],
        )
        text = transcript.final_text
        grounded = bool(text) and (str(item_a) in text or str(item_b) in text)
        if not grounded:
            problems.append("final answer missing or doesn't reference either item id")
        return TaskScore(ok, grounded, "; ".join(problems) or "ok")

    return check


def _check_multistep(transcript: Transcript) -> TaskScore:
    """similar_movies(2571, lyra) then explain_connection(2571, <top hit>,
    lyra) — the second call's expected item_b is only known once the first
    call's own result digest is read."""
    records = _tool_records(transcript)
    problems: list[str] = []
    if len(records) != 2:
        got = [r.name for r in records]
        return TaskScore(False, False, f"expected 2 tool calls, got {len(records)}: {got}")

    first, second = records
    if first.name != "similar_movies" or first.args.get("item_id") != 2571:
        problems.append(
            f"call 0: expected similar_movies(item_id=2571), got {first.name}({first.args})"
        )
    if first.args.get("platform", "lyra") != "lyra":
        problems.append(f"call 0 arg platform: expected 'lyra', got {first.args.get('platform')!r}")

    top_id = _first_item_id(first.result_json or first.result_digest)
    if second.name != "explain_connection":
        problems.append(f"call 1: expected explain_connection, got {second.name!r}")
    else:
        ids = {second.args.get("item_a"), second.args.get("item_b")}
        if 2571 not in ids or (top_id is not None and top_id not in ids):
            problems.append(f"call 1 args {second.args}: expected item pair {{2571, {top_id}}}")
        if second.args.get("platform", "lyra") != "lyra":
            problems.append(
                f"call 1 arg platform: expected 'lyra', got {second.args.get('platform')!r}"
            )

    titles = _titles_in_digest(first.result_json or first.result_digest)
    grounded = bool(transcript.final_text) and _mentions_any(transcript.final_text, titles)
    if not grounded:
        problems.append("final answer missing or doesn't mention the similar-movies result")
    return TaskScore(not problems, grounded, "; ".join(problems) or "ok")


def _check_cross_platform(transcript: Transcript) -> TaskScore:
    """Same similar_movies question on lyra and hydra — two calls, same
    item_id, platforms differing, order not asserted."""
    records = _tool_records(transcript)
    problems: list[str] = []
    similar = [r for r in records if r.name == "similar_movies"]
    if len(records) != 2 or len(similar) != 2:
        got = [r.name for r in records]
        problems.append(f"expected exactly 2 similar_movies calls, got {len(records)}: {got}")

    platforms = {r.args.get("platform") for r in similar}
    item_ids = {r.args.get("item_id") for r in similar}
    if platforms != {"lyra", "hydra"}:
        problems.append(f"expected platforms {{'lyra', 'hydra'}}, got {platforms}")
    if item_ids != {2571}:
        problems.append(f"expected item_id=2571 on both calls, got {item_ids}")

    titles: set[str] = set()
    for r in similar:
        titles |= _titles_in_digest(r.result_json or r.result_digest)
    grounded = bool(transcript.final_text) and _mentions_any(transcript.final_text, titles)
    if not grounded:
        problems.append("final answer missing or doesn't mention a returned title")
    return TaskScore(not problems, grounded, "; ".join(problems) or "ok")


def _check_no_tool(transcript: Transcript) -> TaskScore:
    records = _tool_records(transcript)
    ok = not records
    grounded = ok and bool(transcript.final_text)
    if ok and grounded:
        notes = "ok"
    elif records:
        notes = f"expected no tool calls, got {[r.name for r in records]}"
    else:
        notes = "no tool calls made, but final answer was empty"
    return TaskScore(ok, grounded, notes)


# --- the fixed suite -----------------------------------------------------

TASKS: list[Task] = [
    Task(
        id="recommend-lyra-explicit",
        prompt="Recommend 5 movies for user 7 on the lyra platform.",
        check=_retrieval_check(
            [{"tool": "recommend_for_user", "user_id": 7, "k": 5, "platform": "lyra"}]
        ),
    ),
    Task(
        id="recommend-hydra-explicit",
        prompt="Recommend 3 movies for user 12 on the hydra platform.",
        check=_retrieval_check(
            [{"tool": "recommend_for_user", "user_id": 12, "k": 3, "platform": "hydra"}]
        ),
    ),
    Task(
        id="similar-matrix-lyra",
        prompt="Find the 5 movies most similar to movie 2571 (The Matrix) on the lyra platform.",
        check=_retrieval_check(
            [{"tool": "similar_movies", "item_id": 2571, "k": 5, "platform": "lyra"}]
        ),
    ),
    Task(
        id="similar-terminator-hydra",
        prompt=(
            "Find the 4 movies most similar to movie 589 (Terminator 2: Judgment Day) "
            "on the hydra platform."
        ),
        check=_retrieval_check(
            [{"tool": "similar_movies", "item_id": 589, "k": 4, "platform": "hydra"}]
        ),
    ),
    Task(
        id="explain-matrix-terminator",
        prompt=(
            "On the lyra platform, explain how movie 2571 (The Matrix) and movie 589 "
            "(Terminator 2: Judgment Day) are connected."
        ),
        check=_check_explain_connection(item_a=2571, item_b=589, platform="lyra"),
    ),
    Task(
        id="multistep-similar-then-explain",
        prompt=(
            "On the lyra platform, find the movie most similar to movie 2571 (The Matrix), "
            "then explain how movie 2571 is connected to that result."
        ),
        check=_check_multistep,
    ),
    Task(
        id="cross-platform-similar",
        prompt=(
            "Find movies similar to movie 2571 (The Matrix) on both the lyra and hydra "
            "platforms, and compare the two result sets."
        ),
        check=_check_cross_platform,
    ),
    Task(
        id="no-tool-capital-of-france",
        prompt="What is the capital of France?",
        check=_check_no_tool,
    ),
]


# --- running + artifact ---------------------------------------------------


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _est_cost_usd(driver: Driver, input_tokens: int, output_tokens: int) -> float:
    if driver.name != "anthropic":
        return 0.0
    return (
        input_tokens / 1_000_000 * HAIKU_45_USD_PER_MTOK_IN
        + output_tokens / 1_000_000 * HAIKU_45_USD_PER_MTOK_OUT
    )


async def run_suite(driver: Driver, *, reps: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for rep in range(reps):
        for task in TASKS:
            # one exploding task-rep (driver hiccup, hallucinated args the
            # tool rejects) must not lose the rest of the run — record the
            # failure and keep going, same posture as the MCP selftest
            try:
                transcript = await run_task(driver, task.prompt)
            except Exception as exc:
                transcript = Transcript(
                    task_id=task.id,
                    turns=[],
                    tool_calls_made=[],
                    final_text="",
                    wall_ms=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    hit_turn_limit=False,
                )
                score = TaskScore(False, False, f"task crashed: {type(exc).__name__}: {exc}")
                results.append(
                    {"rep": rep, "task_id": task.id, "score": score, "transcript": transcript}
                )
                continue
            transcript.task_id = task.id
            score = task.check(transcript)
            if transcript.hit_turn_limit:
                score.notes = f"hit turn limit; {score.notes}"
            results.append(
                {"rep": rep, "task_id": task.id, "score": score, "transcript": transcript}
            )
    return results


def _slim_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    """Artifacts store the human-readable digest, never the full tool JSON —
    scoring already happened in memory against the untruncated results."""
    for turn in transcript.get("turns", []):
        for record in turn.get("tool_calls", []):
            record.pop("result_json", None)
    return transcript


def build_artifact(driver: Driver, results: list[dict[str, Any]]) -> dict[str, Any]:
    per_task: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        per_task.setdefault(r["task_id"], []).append(r)

    total_input = sum(r["transcript"].input_tokens for r in results)
    total_output = sum(r["transcript"].output_tokens for r in results)
    n_ok = sum(1 for r in results if r["score"].tool_calls_ok and r["score"].answer_grounded)

    task_summaries = {}
    for task_id, reps in per_task.items():
        wall_ms = [r["transcript"].wall_ms for r in reps]
        task_summaries[task_id] = {
            "n_reps": len(reps),
            "fidelity": sum(
                1 for r in reps if r["score"].tool_calls_ok and r["score"].answer_grounded
            )
            / len(reps),
            "mean_wall_ms": round(sum(wall_ms) / len(wall_ms), 1),
            "max_wall_ms": round(max(wall_ms), 1),
        }

    return {
        "driver": driver.name,
        "model": driver.model,
        "host": {
            "machine": host_platform.machine(),
            "cpu_count": os.cpu_count(),
            "python": host_platform.python_version(),
        },
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "n_tasks": len(TASKS),
        "n_reps": len(results) // len(TASKS) if TASKS else 0,
        "aggregate": {
            "fidelity": n_ok / len(results) if results else 0.0,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "est_cost_usd": round(_est_cost_usd(driver, total_input, total_output), 6),
        },
        "tasks": task_summaries,
        "results": [
            {
                "rep": r["rep"],
                "task_id": r["task_id"],
                "score": dataclasses.asdict(r["score"]),
                "transcript": _slim_transcript(dataclasses.asdict(r["transcript"])),
            }
            for r in results
        ],
    }


def _print_summary(artifact: dict[str, Any]) -> None:
    print(f"driver={artifact['driver']} model={artifact['model']} reps={artifact['n_reps']}")
    print(f"{'task':32s} {'fidelity':>9s} {'mean_ms':>9s} {'max_ms':>9s}")
    for task_id, summary in artifact["tasks"].items():
        print(
            f"{task_id:32s} {summary['fidelity']:9.2f} "
            f"{summary['mean_wall_ms']:9.1f} {summary['max_wall_ms']:9.1f}"
        )
    agg = artifact["aggregate"]
    print(
        f"overall fidelity={agg['fidelity']:.2f} "
        f"tokens(in/out)={agg['total_input_tokens']}/{agg['total_output_tokens']} "
        f"est_cost_usd={agg['est_cost_usd']}"
    )


def _model_slug(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", model)


def _build_driver(name: str, model: str | None) -> Driver:
    if name == "anthropic":
        return AnthropicDriver(model=model) if model else AnthropicDriver()
    return OllamaDriver(model=model) if model else OllamaDriver()


async def main_async(driver_name: str, model: str | None, reps: int) -> Path:
    driver = _build_driver(driver_name, model)
    results = await run_suite(driver, reps=reps)
    artifact = build_artifact(driver, results)
    _print_summary(artifact)

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = BENCH_DIR / f"{driver.name}-{_model_slug(driver.model)}-{stamp}.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n")
    print(f"artifact: {path}")
    return path


def main() -> None:
    from dotenv import load_dotenv  # CLI entry only — never at import time

    load_dotenv()

    parser = argparse.ArgumentParser(description="Constellate context-plane task suite")
    parser.add_argument("--driver", choices=["anthropic", "local"], required=True)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--model", default=None, help="override the driver's default model")
    args = parser.parse_args()
    asyncio.run(main_async(args.driver, args.model, args.reps))


if __name__ == "__main__":
    main()
