"""MCP server: the same service layer as the REST routes, over stdio (ADR 0008).

Three hand-written tools with agent-oriented docstrings — no bridging
machinery. `platform` selects lyra/orion/hydra per call (ADR 0011 shape).

    uv run python -m constellate.mcp_server             # stdio, for Claude Code
    uv run python -m constellate.mcp_server --selftest  # in-memory client, lyra
"""

import asyncio
import sys

from fastmcp import FastMCP

from constellate.config import CONFIG_DIR
from constellate.core.types import Recommendation, RetrievalRequest
from constellate.factory import build_service
from constellate.service import Service

mcp = FastMCP("constellate")

PLATFORMS = sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))
_services: dict[str, Service] = {}
_lock = asyncio.Lock()


async def _service(platform: str) -> Service:
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform {platform!r} (have: {', '.join(PLATFORMS)})")
    if cached := _services.get(platform):
        return cached
    async with _lock:
        if platform not in _services:
            _services[platform] = await build_service(platform)
        return _services[platform]


def _rec_payload(rec: Recommendation) -> dict[str, object]:
    out: dict[str, object] = {
        "rank": rec.rank,
        "item_id": rec.item_id,
        "title": rec.metadata.get("title"),
        "year": rec.metadata.get("year"),
        "score": rec.score,
        "sources": rec.sources,
    }
    if rec.path:
        out["path"] = rec.path
    return out


@mcp.tool
async def recommend_for_user(
    user_id: int, platform: str = "lyra", k: int = 10, explain: bool = True
) -> dict[str, object]:
    """Recommend movies for a MovieLens user via multi-plane retrieval
    (relational eligibility + vector similarity + graph expansion, fused).

    Use when you have a user id and want ranked movie recommendations.
    `platform` picks the storage backend (lyra = embedded, orion = unified
    Postgres, hydra = composed Postgres+Qdrant+Memgraph) — results are
    quality-equivalent across platforms, so choose by which stack is running.
    With `explain=True` each recommendation carries `path`, the graph
    traversal that produced it (nodes like "item:318", "tag:640"; edge types
    RATED / HAS_TAG / HAS_GENRE / CO_RATED).
    """
    service = await _service(platform)
    response = await service.recommend(RetrievalRequest(user_id=user_id, k=k, explain=explain))
    return {
        "platform": platform,
        "config_fingerprint": response.config_fingerprint,
        "recommendations": [_rec_payload(r) for r in response.recommendations],
        "timings_ms": response.timings.model_dump(),
    }


@mcp.tool
async def similar_movies(
    item_id: int, platform: str = "lyra", k: int = 10, explain: bool = True
) -> dict[str, object]:
    """Find movies similar to a seed movie (by MovieLens item id).

    Use when you have one movie and want its neighborhood — the graph arm's
    co-rating and shared-tag structure plus vector similarity. To find an
    item id from a title, ask the user or use the REST /v1/search/items
    endpoint; this tool needs the numeric id. Same `platform` and `explain`
    semantics as recommend_for_user.
    """
    service = await _service(platform)
    response = await service.similar(item_id, k=k, explain=explain)
    return {
        "platform": platform,
        "config_fingerprint": response.config_fingerprint,
        "recommendations": [_rec_payload(r) for r in response.recommendations],
        "timings_ms": response.timings.model_dump(),
    }


@mcp.tool
async def explain_connection(
    item_a: int, item_b: int, platform: str = "lyra", max_hops: int = 3
) -> dict[str, object]:
    """Explain how two movies are connected in the knowledge graph.

    Returns the strongest path between them (alternating node, edge-type,
    node — e.g. ["item:2571", "CO_RATED", "item:589"]), or null when no path
    exists within `max_hops`. Keep max_hops at 3 or below; hub-heavy nodes
    make deeper searches expensive.
    """
    service = await _service(platform)
    path = await service.explain(item_a, item_b, max_hops)
    return {"platform": platform, "a": item_a, "b": item_b, "path": path}


def _close_all() -> None:
    for service in _services.values():
        service.close()
    _services.clear()


async def _selftest(platforms: list[str]) -> int:
    """In-memory client driving every tool against real engines."""
    from fastmcp import Client

    failures = 0
    async with Client(mcp) as client:
        for platform in platforms:
            for tool, args in [
                ("similar_movies", {"item_id": 2571, "platform": platform, "k": 3}),
                ("recommend_for_user", {"user_id": 1, "platform": platform, "k": 3}),
                ("explain_connection", {"item_a": 2571, "item_b": 589, "platform": platform}),
            ]:
                try:
                    result = await client.call_tool(tool, args)
                    data = result.data
                    ok = bool(data.get("recommendations") or data.get("path"))
                    print(f"{platform:6s} {tool:20s} {'ok' if ok else 'EMPTY'}")
                    failures += 0 if ok else 1
                except Exception as exc:
                    print(f"{platform:6s} {tool:20s} FAIL {exc}")
                    failures += 1
    _close_all()
    return failures


def main() -> None:
    if "--selftest" in sys.argv:
        platforms = [a for a in sys.argv[1:] if not a.startswith("-")] or ["lyra"]
        sys.exit(1 if asyncio.run(_selftest(platforms)) else 0)
    try:
        mcp.run()  # stdio
    finally:
        _close_all()


if __name__ == "__main__":
    main()
