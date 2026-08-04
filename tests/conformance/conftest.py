"""Conformance harness: every adapter must pass these suites unchanged.

Adapters register here as they land (phase 03+). Empty registry → suites skip,
which keeps the contract executable from day one.
"""

from collections.abc import Awaitable, Callable

import duckdb
import kuzu
import pytest

from constellate.core.protocol import GraphPlane, RelationalPlane, VectorPlane
from constellate.planes.graph.kuzu import KuzuGraph
from constellate.planes.relational.duckdb import DuckDBRelational
from constellate.planes.vector.flat import FlatVector
from constellate.planes.vector.hnsw import HnswVector

DIM = 4  # conformance vectors are 4d


async def _flat() -> VectorPlane:
    return FlatVector(dim=DIM)


async def _hnsw() -> VectorPlane:
    return HnswVector(dim=DIM, max_elements=1000)


async def _duckdb() -> RelationalPlane:
    """Tiny shared dataset: user 1 rated items 1+2 in train; item 3 unrated."""
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE items(item_id INT, title TEXT, year INT, genres TEXT[],
                           n_ratings INT, mean_rating DOUBLE);
        INSERT INTO items VALUES
            (1, 'Alpha (1994)', 1994, ['Comedy'], 2, 4.5),
            (2, 'Beta (2001)', 2001, ['Drama','Comedy'], 1, 3.0),
            (3, 'Gamma (2020)', 2020, [], 0, NULL);
        CREATE TABLE users(user_id INT, n_train INT, mean_rating DOUBLE);
        INSERT INTO users VALUES (1, 2, 4.0);
        CREATE TABLE interactions(user_id INT, item_id INT, rating DOUBLE,
                                  ts BIGINT, split TEXT);
        INSERT INTO interactions VALUES
            (1, 1, 4.0, 100, 'train'), (1, 2, 4.0, 200, 'train'), (1, 3, 5.0, 300, 'test');
        """
    )
    return DuckDBRelational(conn)


# name -> async factory returning a loaded adapter (registered in phase 03+)
RELATIONAL_ADAPTERS: dict[str, Callable[[], Awaitable[RelationalPlane]]] = {
    "duckdb": _duckdb,
}
VECTOR_ADAPTERS: dict[str, Callable[[], Awaitable[VectorPlane]]] = {
    "flat": _flat,
    "hnsw": _hnsw,
}


async def _kuzu() -> GraphPlane:
    # conformance node ids use "m:"/"t:"/"g:" prefixes
    return KuzuGraph(kuzu.Database(":memory:"), item_prefix="m:")


GRAPH_ADAPTERS: dict[str, Callable[[], Awaitable[GraphPlane]]] = {
    "kuzu": _kuzu,
}

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
