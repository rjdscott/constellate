"""The agent loop over the MCP tools, in-process (ADR 0012): drive a
`Driver` against the same FastMCP server the selftest exercises
(`constellate.mcp_server._selftest`), turn by turn, until it answers or hits
`max_turns`.
"""

import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client

from constellate.context.drivers import Driver, DriverTurn, ToolCall
from constellate.mcp_server import mcp

# qwen3 emits <think>...</think> reasoning blocks in its text output; they
# never belong in a stored/scored answer, but their length is worth keeping.
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)

CallTool = Callable[[str, dict[str, Any]], Awaitable[Any]]


@dataclass
class ToolCallRecord:
    name: str
    args: dict[str, Any]
    result_digest: str  # first 500 chars of the tool's JSON result


@dataclass
class Turn:
    role: str
    text: str | None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


@dataclass
class Transcript:
    task_id: str  # filled by the caller (suite.py), empty here
    turns: list[Turn]
    tool_calls_made: list[ToolCall]
    final_text: str
    wall_ms: float
    input_tokens: int
    output_tokens: int
    hit_turn_limit: bool
    thinking_chars: int = 0


def _strip_think(text: str | None) -> tuple[str | None, int]:
    if not text:
        return None, 0
    thinking_chars = sum(len(m) for m in _THINK_RE.findall(text))
    stripped = _THINK_RE.sub("", text).strip()
    return (stripped or None), thinking_chars


def _neutral_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
        for t in mcp_tools
    ]


async def _run_loop(
    driver: Driver,
    prompt: str,
    tools: list[dict[str, Any]],
    call_tool: CallTool,
    max_turns: int,
) -> Transcript:
    """Core loop, independent of the real MCP client so it's unit-testable
    with a fake driver and a fake `call_tool`."""
    t0 = time.perf_counter()
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    turns: list[Turn] = []
    tool_calls_made: list[ToolCall] = []
    input_tokens = output_tokens = thinking_chars = 0
    final_text = ""
    hit_turn_limit = False

    for _ in range(max_turns):
        driver_turn: DriverTurn = await driver.chat(messages, tools)
        input_tokens += driver_turn.input_tokens
        output_tokens += driver_turn.output_tokens
        text, chars = _strip_think(driver_turn.text)
        thinking_chars += chars

        if not driver_turn.tool_calls:
            final_text = text or ""
            turns.append(Turn(role="assistant", text=text, tool_calls=[]))
            break

        messages.append(
            {
                "role": "assistant",
                "content": text,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "args": tc.args} for tc in driver_turn.tool_calls
                ],
            }
        )
        records: list[ToolCallRecord] = []
        for tc in driver_turn.tool_calls:
            tool_calls_made.append(tc)
            result = await call_tool(tc.name, tc.args)
            result_json = json.dumps(result, default=str)
            records.append(
                ToolCallRecord(name=tc.name, args=tc.args, result_digest=result_json[:500])
            )
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_json})
        turns.append(Turn(role="assistant", text=text, tool_calls=records))
    else:
        hit_turn_limit = True

    return Transcript(
        task_id="",
        turns=turns,
        tool_calls_made=tool_calls_made,
        final_text=final_text,
        wall_ms=(time.perf_counter() - t0) * 1000,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        hit_turn_limit=hit_turn_limit,
        thinking_chars=thinking_chars,
    )


async def run_task(driver: Driver, prompt: str, *, max_turns: int = 8) -> Transcript:
    """Run one task end to end against the real MCP tools, in-process."""
    async with Client(mcp) as client:
        mcp_tools = await client.list_tools()
        tools = _neutral_tools(mcp_tools)

        async def call_tool(name: str, args: dict[str, Any]) -> Any:
            return (await client.call_tool(name, args)).data

        return await _run_loop(driver, prompt, tools, call_tool, max_turns)
