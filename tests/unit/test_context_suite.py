"""Context plane (ADR 0012): neutral<->wire conversions, the agent loop
against a fake driver + fake tool executor, and deterministic task scoring
on synthetic transcripts. No network, no anthropic/ollama SDK imports."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from constellate.context.drivers import (
    DriverTurn,
    ToolCall,
    to_anthropic_messages,
    to_anthropic_tools,
    to_ollama_messages,
    to_ollama_tools,
)
from constellate.context.loop import ToolCallRecord, Transcript, Turn, _run_loop, _strip_think
from constellate.context.suite import (
    TaskScore,
    _check_cross_platform,
    _check_explain_connection,
    _check_multistep,
    _check_no_tool,
    _retrieval_check,
    build_artifact,
)

# --- neutral -> anthropic --------------------------------------------------


def test_to_anthropic_messages_merges_consecutive_tool_results() -> None:
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "checking",
            "tool_calls": [{"id": "t1", "name": "similar_movies", "args": {"item_id": 1}}],
        },
        {"role": "tool", "tool_call_id": "t1", "content": '{"ok": true}'},
        {"role": "tool", "tool_call_id": "t2", "content": '{"ok": false}'},
    ]
    out = to_anthropic_messages(messages)
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert out[1]["content"] == [
        {"type": "text", "text": "checking"},
        {"type": "tool_use", "id": "t1", "name": "similar_movies", "input": {"item_id": 1}},
    ]
    # both tool results merged into the one trailing user turn
    assert [b["tool_use_id"] for b in out[2]["content"]] == ["t1", "t2"]


def test_to_anthropic_tools_shape() -> None:
    tools = [{"name": "similar_movies", "description": "desc", "input_schema": {"type": "object"}}]
    assert to_anthropic_tools(tools) == [
        {"name": "similar_movies", "description": "desc", "input_schema": {"type": "object"}}
    ]


# --- neutral -> ollama ------------------------------------------------------


def test_to_ollama_messages_shapes_tool_calls_and_results() -> None:
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "1", "name": "similar_movies", "args": {"item_id": 1}}],
        },
        {"role": "tool", "tool_call_id": "1", "content": '{"ok": true}'},
    ]
    out = to_ollama_messages(messages)
    assert out[0] == {"role": "user", "content": "hi"}
    assert out[1] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "similar_movies", "arguments": {"item_id": 1}}}],
    }
    assert out[2] == {"role": "tool", "content": '{"ok": true}'}


def test_to_ollama_tools_shape() -> None:
    tools = [{"name": "similar_movies", "description": "desc", "input_schema": {"type": "object"}}]
    assert to_ollama_tools(tools) == [
        {
            "type": "function",
            "function": {
                "name": "similar_movies",
                "description": "desc",
                "parameters": {"type": "object"},
            },
        }
    ]


# --- the loop, against a scripted driver + fake tool executor -------------


@dataclass
class ScriptedDriver:
    turns: list[DriverTurn]
    name: str = "fake"
    model: str = "fake-model"
    calls: list[list[dict[str, Any]]] = field(default_factory=list)

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> DriverTurn:
        self.calls.append([dict(m) for m in messages])
        return self.turns.pop(0)


async def _fake_call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"tool": name, "item_id": args.get("item_id"), "title": "Fake Title"}


def test_loop_feeds_tool_result_back_and_stops_on_text() -> None:
    driver = ScriptedDriver(
        turns=[
            DriverTurn(
                text="looking it up",
                tool_calls=[ToolCall(name="similar_movies", args={"item_id": 1}, id="c1")],
                input_tokens=10,
                output_tokens=5,
            ),
            DriverTurn(text="Fake Title is a good pick.", input_tokens=3, output_tokens=2),
        ]
    )
    transcript = asyncio.run(
        _run_loop(driver, "recommend something", [], _fake_call_tool, max_turns=8)
    )

    assert transcript.hit_turn_limit is False
    assert transcript.final_text == "Fake Title is a good pick."
    assert [tc.name for tc in transcript.tool_calls_made] == ["similar_movies"]
    assert transcript.input_tokens == 13
    assert transcript.output_tokens == 7
    # the tool result was fed back on the second call to the driver
    second_call_messages = driver.calls[1]
    tool_msgs = [m for m in second_call_messages if m["role"] == "tool"]
    assert tool_msgs and tool_msgs[0]["tool_call_id"] == "c1"
    assert "Fake Title" in tool_msgs[0]["content"]
    # the transcript stores a digest, not the raw call
    assert transcript.turns[0].tool_calls[0].result_digest.startswith("{")


def test_loop_hits_turn_limit_when_never_answering() -> None:
    always_calls = DriverTurn(
        text=None,
        tool_calls=[ToolCall(name="similar_movies", args={"item_id": 1}, id="c")],
    )
    driver = ScriptedDriver(turns=[always_calls, always_calls])
    transcript = asyncio.run(_run_loop(driver, "prompt", [], _fake_call_tool, max_turns=2))

    assert transcript.hit_turn_limit is True
    assert transcript.final_text == ""
    assert len(transcript.tool_calls_made) == 2


def test_strip_think_blocks_from_final_text() -> None:
    stripped, chars = _strip_think("<think>reasoning here</think>Paris is the capital.")
    assert stripped == "Paris is the capital."
    assert chars == len("reasoning here")


def test_loop_strips_think_blocks_and_counts_them() -> None:
    driver = ScriptedDriver(
        turns=[
            DriverTurn(
                text="<think>hmm</think>The answer is Paris.", input_tokens=1, output_tokens=1
            )
        ]
    )
    transcript = asyncio.run(
        _run_loop(driver, "capital of france?", [], _fake_call_tool, max_turns=8)
    )
    assert transcript.final_text == "The answer is Paris."
    assert transcript.thinking_chars == len("hmm")


# --- scoring ---------------------------------------------------------------


def _turn(name: str, args: dict[str, Any], digest: str) -> Turn:
    return Turn(
        role="assistant",
        text=None,
        tool_calls=[ToolCallRecord(name=name, args=args, result_digest=digest)],
    )


def _transcript(turns: list[Turn], final_text: str = "") -> Transcript:
    tool_calls_made = [
        ToolCall(name=r.name, args=r.args, id="x") for t in turns for r in t.tool_calls
    ]
    return Transcript(
        task_id="t",
        turns=turns,
        tool_calls_made=tool_calls_made,
        final_text=final_text,
        wall_ms=1.0,
        input_tokens=1,
        output_tokens=1,
        hit_turn_limit=False,
    )


SIMILAR_DIGEST = '{"recommendations": [{"rank": 1, "item_id": 79132, "title": "Inception (2010)"}]}'


def test_retrieval_check_right_tool_and_grounded() -> None:
    transcript = _transcript(
        [_turn("similar_movies", {"item_id": 2571, "k": 5, "platform": "lyra"}, SIMILAR_DIGEST)],
        final_text="You might like Inception (2010).",
    )
    check = _retrieval_check(
        [{"tool": "similar_movies", "item_id": 2571, "k": 5, "platform": "lyra"}]
    )
    score = check(transcript)
    assert score == TaskScore(True, True, "ok")


def test_retrieval_check_wrong_tool() -> None:
    transcript = _transcript(
        [_turn("recommend_for_user", {"user_id": 1, "k": 5, "platform": "lyra"}, SIMILAR_DIGEST)],
        final_text="Inception (2010) is great.",
    )
    check = _retrieval_check(
        [{"tool": "similar_movies", "item_id": 2571, "k": 5, "platform": "lyra"}]
    )
    score = check(transcript)
    assert score.tool_calls_ok is False


def test_retrieval_check_missing_required_arg() -> None:
    transcript = _transcript(
        [_turn("similar_movies", {"item_id": 2571, "platform": "lyra"}, SIMILAR_DIGEST)],  # no k
        final_text="Inception (2010) is great.",
    )
    check = _retrieval_check(
        [{"tool": "similar_movies", "item_id": 2571, "k": 5, "platform": "lyra"}]
    )
    score = check(transcript)
    assert score.tool_calls_ok is False
    assert "k" in score.notes


def test_retrieval_check_ungrounded_answer() -> None:
    transcript = _transcript(
        [_turn("similar_movies", {"item_id": 2571, "k": 5, "platform": "lyra"}, SIMILAR_DIGEST)],
        final_text="Sure, here you go.",
    )
    check = _retrieval_check(
        [{"tool": "similar_movies", "item_id": 2571, "k": 5, "platform": "lyra"}]
    )
    score = check(transcript)
    assert score.tool_calls_ok is True
    assert score.answer_grounded is False


def test_no_tool_task_passes_with_answer_and_no_call() -> None:
    transcript = _transcript([], final_text="Paris.")
    score = _check_no_tool(transcript)
    assert score == TaskScore(True, True, "ok")


def test_no_tool_task_fails_on_spurious_call() -> None:
    transcript = _transcript(
        [_turn("similar_movies", {"item_id": 1, "k": 1, "platform": "lyra"}, SIMILAR_DIGEST)],
        final_text="Paris.",
    )
    score = _check_no_tool(transcript)
    assert score.tool_calls_ok is False
    assert score.answer_grounded is False


def test_explain_connection_check() -> None:
    digest = (
        '{"platform": "lyra", "a": 2571, "b": 589, "path": ["item:2571", "CO_RATED", "item:589"]}'
    )
    ok_transcript = _transcript(
        [_turn("explain_connection", {"item_a": 2571, "item_b": 589, "platform": "lyra"}, digest)],
        final_text="Movie 2571 and 589 are connected via CO_RATED.",
    )
    check = _check_explain_connection(item_a=2571, item_b=589, platform="lyra")
    assert check(ok_transcript) == TaskScore(True, True, "ok")

    wrong_platform = _transcript(
        [_turn("explain_connection", {"item_a": 2571, "item_b": 589, "platform": "hydra"}, digest)],
        final_text="Movie 2571 and 589 are connected.",
    )
    assert check(wrong_platform).tool_calls_ok is False


def test_multistep_check_uses_top_hit_from_first_digest() -> None:
    second_digest = '{"a": 2571, "b": 79132, "path": []}'
    transcript = _transcript(
        [
            _turn("similar_movies", {"item_id": 2571, "k": 10, "platform": "lyra"}, SIMILAR_DIGEST),
            _turn(
                "explain_connection",
                {"item_a": 2571, "item_b": 79132, "platform": "lyra"},
                second_digest,
            ),
        ],
        final_text="Inception (2010) connects to The Matrix.",
    )
    score = _check_multistep(transcript)
    assert score.tool_calls_ok is True
    assert score.answer_grounded is True


def test_multistep_check_fails_when_second_call_ignores_top_hit() -> None:
    second_digest = '{"a": 2571, "b": 1, "path": []}'
    transcript = _transcript(
        [
            _turn("similar_movies", {"item_id": 2571, "k": 10, "platform": "lyra"}, SIMILAR_DIGEST),
            _turn(
                "explain_connection",
                {"item_a": 2571, "item_b": 1, "platform": "lyra"},
                second_digest,
            ),
        ],
        final_text="done",
    )
    score = _check_multistep(transcript)
    assert score.tool_calls_ok is False


def test_cross_platform_check() -> None:
    transcript = _transcript(
        [
            _turn("similar_movies", {"item_id": 2571, "k": 10, "platform": "lyra"}, SIMILAR_DIGEST),
            _turn(
                "similar_movies", {"item_id": 2571, "k": 10, "platform": "hydra"}, SIMILAR_DIGEST
            ),
        ],
        final_text="Both platforms suggest Inception (2010).",
    )
    score = _check_cross_platform(transcript)
    assert score == TaskScore(True, True, "ok")


def test_cross_platform_check_fails_on_same_platform_twice() -> None:
    transcript = _transcript(
        [
            _turn("similar_movies", {"item_id": 2571, "k": 10, "platform": "lyra"}, SIMILAR_DIGEST),
            _turn("similar_movies", {"item_id": 2571, "k": 10, "platform": "lyra"}, SIMILAR_DIGEST),
        ],
        final_text="Inception (2010).",
    )
    score = _check_cross_platform(transcript)
    assert score.tool_calls_ok is False


# --- artifact aggregate math -------------------------------------------


@dataclass
class _FakeDriverInfo:
    name: str
    model: str


def _fake_result(task_id: str, ok: bool, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    return {
        "rep": 0,
        "task_id": task_id,
        "score": TaskScore(ok, ok, "ok" if ok else "fail"),
        "transcript": Transcript(
            task_id=task_id,
            turns=[],
            tool_calls_made=[],
            final_text="x",
            wall_ms=100.0 if ok else 200.0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            hit_turn_limit=False,
        ),
    }


def test_build_artifact_fidelity_and_cost_anthropic() -> None:
    driver = _FakeDriverInfo(name="anthropic", model="claude-haiku-4-5-20251001")
    results = [
        _fake_result("t1", True, input_tokens=1000, output_tokens=2000),
        _fake_result("t1", False, input_tokens=500, output_tokens=500),
    ]
    artifact = build_artifact(driver, results)  # type: ignore[arg-type]
    assert artifact["aggregate"]["fidelity"] == 0.5
    assert artifact["aggregate"]["total_input_tokens"] == 1500
    assert artifact["aggregate"]["total_output_tokens"] == 2500
    # 1500/1e6 * 1.00 + 2500/1e6 * 5.00
    assert artifact["aggregate"]["est_cost_usd"] == round(
        1500 / 1_000_000 + 2500 / 1_000_000 * 5, 6
    )
    assert artifact["tasks"]["t1"]["n_reps"] == 2
    assert artifact["tasks"]["t1"]["fidelity"] == 0.5


def test_build_artifact_cost_zero_for_local_driver() -> None:
    driver = _FakeDriverInfo(name="local", model="qwen3:8b")
    results = [_fake_result("t1", True, input_tokens=1000, output_tokens=2000)]
    artifact = build_artifact(driver, results)  # type: ignore[arg-type]
    assert artifact["aggregate"]["est_cost_usd"] == 0.0


def test_title_key_folds_article_year_and_markdown() -> None:
    from constellate.context.suite import _mentions_any, _title_key

    key = _title_key("Terminator, The (1984)")
    assert key == "terminator"
    assert _mentions_any("Top hit: **The Terminator (1984)** — a classic.", {key})
    assert _mentions_any(
        "1. **Diving Bell and the Butterfly, The** (2007)",
        {_title_key("Diving Bell and the Butterfly, The (2007)")},
    )
    assert not _mentions_any("I could not find anything relevant.", {key})


def test_title_key_strips_alternate_title_parentheticals() -> None:
    from constellate.context.suite import _mentions_any, _title_key

    key = _title_key("Diving Bell and the Butterfly, The (Scaphandre et le papillon, Le) (2007)")
    assert key == "diving bell and butterfly"
    assert _mentions_any("Top pick: **The Diving Bell and the Butterfly** (2007).", {key})
