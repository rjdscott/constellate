"""LLM drivers behind one adapter (ADR 0012): Anthropic API (Haiku-class) and
a local Ollama model, each converting our neutral message/tool shape to its
own wire format. The neutral shape: role ``user`` | ``assistant`` | ``tool``,
``content`` text, and on assistant messages an optional ``tool_calls`` list
of ``{"id", "name", "args"}``; a ``tool`` message carries ``tool_call_id`` and
the tool's result as ``content``. Tools are ``{"name", "description",
"input_schema"}`` (already the MCP tool schema shape).
"""

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

# 2026-08 pricing: https://www.anthropic.com/pricing (Haiku 4.5)
HAIKU_45_USD_PER_MTOK_IN = 1.00
HAIKU_45_USD_PER_MTOK_OUT = 5.00


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    id: str


@dataclass
class DriverTurn:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class Driver(Protocol):
    name: str
    model: str

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> DriverTurn: ...


# --- pure conversions (neutral -> wire format), factored out so they're
# testable without either SDK ------------------------------------------------


def to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anthropic requires tool results as ``tool_result`` blocks inside a
    ``user`` turn, and turns must strictly alternate — so consecutive
    neutral ``tool`` messages (one per call in a turn) merge into one."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls") or []:
                blocks.append(
                    {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["args"]}
                )
            out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": msg["tool_call_id"],
                "content": msg["content"],
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            raise ValueError(f"unknown message role {role!r}")
    return out


def to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in tools
    ]


def to_ollama_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for msg in messages:
        role = msg["role"]
        if role == "tool":
            out.append({"role": "tool", "content": msg["content"]})
        elif role == "assistant" and msg.get("tool_calls"):
            out.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": [
                        {"function": {"name": tc["name"], "arguments": tc["args"]}}
                        for tc in msg["tool_calls"]
                    ],
                }
            )
        else:
            out.append({"role": role, "content": msg.get("content") or ""})
    return out


def to_ollama_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


class AnthropicDriver:
    """Anthropic Messages API. API key from ``ANTHROPIC_API_KEY`` — never
    logged, never included in error text."""

    name = "anthropic"

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        import anthropic  # lazy: optional `context` extra, no core dep

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise SystemExit("ANTHROPIC_API_KEY not set — put it in .env or export it")
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> DriverTurn:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=to_anthropic_messages(messages),  # type: ignore[arg-type]
            tools=to_anthropic_tools(tools),  # type: ignore[arg-type]
        )
        text = "".join(b.text for b in response.content if b.type == "text") or None
        tool_calls = [
            ToolCall(name=b.name, args=dict(b.input), id=b.id)
            for b in response.content
            if b.type == "tool_use"
        ]
        return DriverTurn(
            text=text,
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


class OllamaDriver:
    """Local Ollama, plain httpx against POST {base_url}/api/chat."""

    name = "local"

    def __init__(self, model: str = "qwen3:8b", base_url: str | None = None) -> None:
        self.model = model
        self.base_url = base_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> DriverTurn:
        payload = {
            "model": self.model,
            "messages": to_ollama_messages(messages),
            "tools": to_ollama_tools(tools),
            "stream": False,
            "options": {"temperature": 0},
        }
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        message = data.get("message") or {}
        tool_calls = [
            ToolCall(
                name=tc["function"]["name"],
                args=dict(tc["function"].get("arguments") or {}),
                id=str(i),
            )
            for i, tc in enumerate(message.get("tool_calls") or [])
        ]
        return DriverTurn(
            text=message.get("content") or None,
            tool_calls=tool_calls,
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
        )
