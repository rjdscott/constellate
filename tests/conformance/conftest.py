"""Conformance harness: every adapter must pass these suites unchanged.

Adapters register here as they land (phase 03+). Empty registry → suites skip,
which keeps the contract executable from day one.

Orion adapters need a live Postgres (`make up PLATFORM=orion`); they register
only when $ORION_DSN (default: the compose DSN) answers, so the suite stays
runnable without docker — but a running Orion is never silently ignored.
Isolation: each factory takes one pooled connection and creates TEMP tables
(session-scoped, auto-dropped); AGE graphs are namespaced per-test and swept
on the next run.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import asyncpg
import duckdb
import kuzu
import pytest
from neo4j import AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient

from constellate.core.protocol import GraphPlane, RelationalPlane, VectorPlane
from constellate.planes.graph.age import AgeGraph
from constellate.planes.graph.kuzu import KuzuGraph
from constellate.planes.graph.memgraph import MemgraphGraph
from constellate.planes.relational.duckdb import DuckDBRelational
from constellate.planes.relational.postgres import PostgresRelational
from constellate.planes.vector.flat import FlatVector
from constellate.planes.vector.hnsw import HnswVector
from constellate.planes.vector.pgvector import PgVector
from constellate.planes.vector.qdrant import QdrantVector

DIM = 4  # conformance vectors are 4d

ORION_DSN = os.environ.get(
    "ORION_DSN", "postgresql://constellate:constellate@localhost:15432/constellate"
)
HYDRA_QDRANT_URL = os.environ.get("HYDRA_QDRANT_URL", "http://localhost:16333")
HYDRA_MEMGRAPH_URI = os.environ.get("HYDRA_MEMGRAPH_URI", "bolt://localhost:17687")


def _orion_reachable() -> bool:
    async def probe() -> None:
        conn = await asyncpg.connect(ORION_DSN, timeout=3)
        try:  # bootstrap fresh volumes/CI: types must exist before TEMP tables use them
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS age")
        finally:
            await conn.close()

    try:
        asyncio.run(probe())
        return True
    except Exception:
        # ORION_REQUIRED=1 (CI) turns silent deregistration into a hard fail:
        # a green suite must never mean "the orion container quietly died"
        if os.environ.get("ORION_REQUIRED"):
            raise
        return False


HAS_ORION = _orion_reachable()


def _hydra_reachable() -> bool:
    """Both derived engines must answer; hydra postgres reuses the orion-tested adapter."""

    async def probe() -> None:
        client = AsyncQdrantClient(url=HYDRA_QDRANT_URL, timeout=3)
        try:
            await client.get_collections()
        finally:
            await client.close()
        driver = AsyncGraphDatabase.driver(HYDRA_MEMGRAPH_URI)
        try:
            await driver.verify_connectivity()
        finally:
            await driver.close()

    try:
        asyncio.run(probe())
        return True
    except Exception:
        # HYDRA_REQUIRED=1 (CI): a green suite must never mean "hydra quietly died"
        if os.environ.get("HYDRA_REQUIRED"):
            raise
        return False


HAS_HYDRA = _hydra_reachable()


async def _orion_pool() -> asyncpg.Pool:
    """Single-connection pool: TEMP tables live in its one session."""
    return await asyncpg.create_pool(ORION_DSN, min_size=1, max_size=1)


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


async def _postgres() -> RelationalPlane:
    """Same tiny dataset as _duckdb, in session-scoped TEMP tables."""
    pool = await _orion_pool()
    await pool.execute(
        """
        CREATE TEMP TABLE items(item_id int, title text, year int, genres text[],
                                n_ratings int, mean_rating double precision);
        INSERT INTO items VALUES
            (1, 'Alpha (1994)', 1994, ARRAY['Comedy'], 2, 4.5),
            (2, 'Beta (2001)', 2001, ARRAY['Drama','Comedy'], 1, 3.0),
            (3, 'Gamma (2020)', 2020, ARRAY[]::text[], 0, NULL);
        CREATE TEMP TABLE users(user_id int, n_train int, mean_rating double precision);
        INSERT INTO users VALUES (1, 2, 4.0);
        CREATE TEMP TABLE interactions(user_id int, item_id int, rating double precision,
                                       ts bigint, split text);
        INSERT INTO interactions VALUES
            (1, 1, 4.0, 100, 'train'), (1, 2, 4.0, 200, 'train'), (1, 3, 5.0, 300, 'test');
        """
    )
    return PostgresRelational(pool)


async def _pgvector() -> VectorPlane:
    pool = await _orion_pool()
    await pool.execute(
        f"""
        CREATE TEMP TABLE item_vectors(item_id int PRIMARY KEY, vec halfvec({DIM}));
        CREATE TEMP TABLE user_vectors(user_id int PRIMARY KEY, vec halfvec({DIM}));
        """
    )
    return PgVector(pool)


async def _cte() -> GraphPlane:
    from constellate.planes.graph.cte import CteGraph

    pool = await _orion_pool()
    await pool.execute(
        """
        CREATE TEMP TABLE graph_edges(src text NOT NULL, dst text NOT NULL,
            edge_type text NOT NULL, weight double precision NOT NULL,
            PRIMARY KEY (src, dst, edge_type));
        """
    )
    return CteGraph(pool, item_prefix="m:")


async def _age() -> GraphPlane:
    pool = await _orion_pool()
    graph = f"conf_{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute("LOAD 'age'")
        await conn.execute('SET search_path = ag_catalog, "$user", public')
        # sweep graphs a previous crashed run left behind, then make ours
        stale = await conn.fetch("SELECT name FROM ag_graph WHERE name LIKE 'conf_%'")
        for row in stale:
            await conn.execute(f"SELECT drop_graph('{row['name']}', true)")
        await conn.execute(f"SELECT create_graph('{graph}')")
    return AgeGraph(pool, graph, item_prefix="m:")


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

if HAS_ORION:
    RELATIONAL_ADAPTERS["postgres"] = _postgres
    VECTOR_ADAPTERS["pgvector"] = _pgvector
    GRAPH_ADAPTERS["cte"] = _cte
    GRAPH_ADAPTERS["age"] = _age


async def _qdrant() -> VectorPlane:
    """Per-test collections; teardown deletes them and closes the client."""
    suffix = uuid.uuid4().hex[:8]
    plane = QdrantVector(
        AsyncQdrantClient(url=HYDRA_QDRANT_URL),
        items_collection=f"conf_items_{suffix}",
        users_collection=f"conf_users_{suffix}",
        dim=DIM,
    )
    await plane.ensure_collections()
    return plane


async def _memgraph() -> GraphPlane:
    """Per-test node label isolates tests on the shared single-db instance."""
    plane = MemgraphGraph(
        AsyncGraphDatabase.driver(HYDRA_MEMGRAPH_URI),
        label=f"Conf_{uuid.uuid4().hex[:8]}",
        item_prefix="m:",
    )
    await plane.ensure_schema()
    return plane


if HAS_HYDRA:
    VECTOR_ADAPTERS["qdrant"] = _qdrant
    GRAPH_ADAPTERS["memgraph"] = _memgraph

_SKIP = pytest.param(None, id="none", marks=pytest.mark.skip(reason="no adapters registered yet"))


def _params(registry: dict[str, Callable[[], Awaitable[object]]]) -> list[object]:
    return [pytest.param(factory, id=name) for name, factory in registry.items()] or [_SKIP]


async def _teardown(plane: object) -> None:
    pool = getattr(plane, "_pool", None)  # orion adapters: close the test's pool
    if isinstance(pool, asyncpg.Pool):
        pool.terminate()
    if isinstance(plane, QdrantVector):
        for name in (plane._items, plane._users):
            await plane._client.delete_collection(name)
        await plane._client.close()
    if isinstance(plane, MemgraphGraph):
        # drop this test's nodes and its index; the label is unique per test
        await plane._run(f"MATCH (n:{plane._label}) DETACH DELETE n")
        await plane._run(f"DROP INDEX ON :{plane._label}(key)")
        await plane._driver.close()


@pytest.fixture(params=_params(RELATIONAL_ADAPTERS))
async def relational(request: pytest.FixtureRequest) -> AsyncIterator[RelationalPlane]:
    plane: RelationalPlane = await request.param()
    yield plane
    await _teardown(plane)


@pytest.fixture(params=_params(VECTOR_ADAPTERS))
async def vector(request: pytest.FixtureRequest) -> AsyncIterator[VectorPlane]:
    plane: VectorPlane = await request.param()
    yield plane
    await _teardown(plane)


@pytest.fixture(params=_params(GRAPH_ADAPTERS))
async def graph(request: pytest.FixtureRequest) -> AsyncIterator[GraphPlane]:
    plane: GraphPlane = await request.param()
    yield plane
    await _teardown(plane)
