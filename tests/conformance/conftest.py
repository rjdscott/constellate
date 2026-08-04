"""Conformance harness: every adapter must pass these suites unchanged.

Adapters register here as they land (phase 03+). Empty registry → suites skip,
which keeps the contract executable from day one.
"""

from collections.abc import Awaitable, Callable

import pytest

from constellate.core.protocol import GraphPlane, RelationalPlane, VectorPlane

# name -> async factory returning a loaded adapter (registered in phase 03+)
RELATIONAL_ADAPTERS: dict[str, Callable[[], Awaitable[RelationalPlane]]] = {}
VECTOR_ADAPTERS: dict[str, Callable[[], Awaitable[VectorPlane]]] = {}
GRAPH_ADAPTERS: dict[str, Callable[[], Awaitable[GraphPlane]]] = {}

_SKIP = pytest.param(None, id="none", marks=pytest.mark.skip(reason="no adapters registered yet"))


def _params(registry: dict[str, Callable[[], Awaitable[object]]]) -> list[object]:
    return [pytest.param(factory, id=name) for name, factory in registry.items()] or [_SKIP]


@pytest.fixture(params=_params(RELATIONAL_ADAPTERS))
async def relational(request: pytest.FixtureRequest) -> RelationalPlane:
    plane: RelationalPlane = await request.param()
    return plane


@pytest.fixture(params=_params(VECTOR_ADAPTERS))
async def vector(request: pytest.FixtureRequest) -> VectorPlane:
    plane: VectorPlane = await request.param()
    return plane


@pytest.fixture(params=_params(GRAPH_ADAPTERS))
async def graph(request: pytest.FixtureRequest) -> GraphPlane:
    plane: GraphPlane = await request.param()
    return plane
