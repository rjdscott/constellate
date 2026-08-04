"""`make load PLATFORM=hydra` — canonical parquet → Postgres, then project.

Hydra's shape (ADR 0005): Postgres 18 is the *source of truth* and holds
everything — relational tables, the vector tables (plain `real[]`, this is
vanilla postgres with no pgvector) and the doubled-edge table. Qdrant and
Memgraph are derived projections, rebuilt from Postgres alone by
`make rebuild PLATFORM=hydra` — which is the shape a future CDC pipeline
would take, and why the rebuild reads no parquet.

Postgres steps are idempotent via the same load_manifest table Orion uses
(each step's writes and its manifest mark commit in one transaction).
`rebuild_hydra()` is deliberately *not* manifest-gated: it always drops and
regenerates both projections, and runs at the end of a first load.

Memgraph's LOAD CSV reads files on the *server*: compose bind-mounts
data/hydra/import to /import, so the loader COPYs the CSVs out of Postgres
onto the host and Memgraph reads them back through the mount.
"""

import asyncio
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import asyncpg
import pandas as pd
import pyarrow.parquet as pq
from neo4j import AsyncGraphDatabase, AsyncSession
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import CollectionStatus, PointStruct

from constellate.ingest import CANONICAL_DIR, DATA_DIR
from constellate.load import doubled_edges

# manifest convention is shared with orion, not orion-specific — same table,
# same atomic step+mark contract (ADR 0004 / phase-05 review finding)
from constellate.load_orion import _done, _mark
from constellate.planes.vector.qdrant import QdrantVector

HYDRA_DSN = os.environ.get(
    "HYDRA_DSN", "postgresql://constellate:constellate@localhost:15433/constellate"
)
QDRANT_URL = os.environ.get("HYDRA_QDRANT_URL", "http://localhost:16333")
MEMGRAPH_URI = os.environ.get("HYDRA_MEMGRAPH_URI", "bolt://localhost:17687")

IMPORT_HOST = DATA_DIR / "hydra" / "import"
IMPORT_CONTAINER = "/import"

INTERACTIONS_CHUNK = 500_000
VECTOR_CHUNK = 8_192
QDRANT_BATCH = 4_096
DELETE_BATCH = 200_000
PERIODIC_COMMIT = 50_000
INDEX_TIMEOUT = 120.0  # seconds to wait for qdrant's optimizer to settle

DISTINCT_KEYS = "SELECT src AS key FROM graph_edges UNION SELECT dst FROM graph_edges"

SCHEMA = """
CREATE TABLE IF NOT EXISTS load_manifest(
    step text PRIMARY KEY, rows bigint NOT NULL, completed_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS items(
    item_id int PRIMARY KEY, title text NOT NULL, year int, genres text[] NOT NULL,
    n_ratings int NOT NULL, mean_rating double precision);
CREATE TABLE IF NOT EXISTS users(
    user_id int PRIMARY KEY, n_train int NOT NULL, mean_rating double precision);
CREATE TABLE IF NOT EXISTS interactions(
    user_id int NOT NULL, item_id int NOT NULL, rating real NOT NULL,
    ts bigint NOT NULL, split text NOT NULL);
CREATE INDEX IF NOT EXISTS interactions_user_split ON interactions(user_id, split);
CREATE TABLE IF NOT EXISTS item_vectors(item_id int PRIMARY KEY, vec real[] NOT NULL);
CREATE TABLE IF NOT EXISTS user_vectors(user_id int PRIMARY KEY, vec real[] NOT NULL);
CREATE TABLE IF NOT EXISTS graph_edges(
    src text NOT NULL, dst text NOT NULL, edge_type text NOT NULL,
    weight double precision NOT NULL, PRIMARY KEY (src, dst, edge_type));
"""


async def _connect(dsn: str) -> asyncpg.Connection:
    try:
        return await asyncpg.connect(dsn, timeout=5)
    except OSError as exc:  # includes ConnectionRefusedError
        raise SystemExit(
            f"load: cannot reach hydra postgres at {dsn} — run `make up PLATFORM=hydra`"
        ) from exc


# --- postgres load steps (manifest-gated) ------------------------------------


async def _load_items(conn: asyncpg.Connection, canonical: Path) -> int:
    items = pd.read_parquet(canonical / "items.parquet")
    inter = pq.read_table(
        canonical / "interactions.parquet",
        columns=["item_id", "rating", "split"],
        filters=[("split", "=", "train")],
    ).to_pandas()
    agg = inter.groupby("item_id")["rating"].agg(n_train="count", mean_r="mean")
    items = items.join(agg, on="item_id")
    records = [
        (
            int(item_id),
            str(title),
            None if pd.isna(year) else int(year),
            list(genres),
            0 if pd.isna(n) else int(n),
            None if pd.isna(mean) else float(mean),
        )
        for item_id, title, year, genres, n, mean in zip(
            items["item_id"],
            items["title"],
            items["year"],
            items["genres"],
            items["n_train"],
            items["mean_r"],
            strict=True,
        )
    ]
    await conn.copy_records_to_table("items", records=records)
    return len(records)


async def _load_users(conn: asyncpg.Connection, canonical: Path) -> int:
    users = pd.read_parquet(canonical / "users.parquet")
    records = [
        (int(u), int(n), None if pd.isna(m) else float(m))
        for u, n, m in zip(users["user_id"], users["n_train"], users["mean_rating"], strict=True)
    ]
    await conn.copy_records_to_table("users", records=records)
    return len(records)


async def _load_interactions(conn: asyncpg.Connection, canonical: Path) -> int:
    pf = pq.ParquetFile(canonical / "interactions.parquet")
    total = 0
    for batch in pf.iter_batches(batch_size=INTERACTIONS_CHUNK):
        cols = [
            batch.column(name).to_pylist()
            for name in ("user_id", "item_id", "rating", "ts", "split")
        ]
        records = list(zip(*cols, strict=True))
        await conn.copy_records_to_table("interactions", records=records)
        total += len(records)
    return total


async def _load_vectors(conn: asyncpg.Connection, canonical: Path, name: str, id_col: str) -> int:
    df = pd.read_parquet(canonical / f"{name}.parquet", columns=[id_col, "vector"])
    ids = df[id_col].to_list()
    vecs = df["vector"].to_list()
    for start in range(0, len(ids), VECTOR_CHUNK):
        stop = start + VECTOR_CHUNK
        records = [
            (int(i), [float(x) for x in v])
            for i, v in zip(ids[start:stop], vecs[start:stop], strict=True)
        ]
        await conn.copy_records_to_table(name, records=records)
    return len(ids)


async def _load_edges(conn: asyncpg.Connection, canonical: Path) -> int:
    both = doubled_edges(canonical)
    records = list(
        zip(both["src"], both["dst"], both["edge_type"], both["weight"].astype(float), strict=True)
    )
    await conn.copy_records_to_table("graph_edges", records=records)
    return len(records)


# --- derived projections (never manifest-gated) ------------------------------


async def _await_indexed(client: AsyncQdrantClient, collection: str) -> None:
    """Barrier: block until the optimizer stops moving and the collection is green.

    Not equality with the point count — the adapter's 1000-point indexing
    threshold leaves each segment's tail unindexed on purpose, so the steady
    state is `indexed < total` forever. Poll for *stability* instead: two
    consecutive reads with the same `indexed_vectors_count` and a green status
    mean the build is done, and a bench started right after measures HNSW
    rather than a half-built index.
    """
    deadline = time.perf_counter() + INDEX_TIMEOUT
    previous = -1
    while time.perf_counter() < deadline:
        info = await client.get_collection(collection)
        indexed = info.indexed_vectors_count or 0
        if indexed == previous and info.status == CollectionStatus.GREEN:
            print(f"rebuild: qdrant {collection} indexed {indexed:,}/{info.points_count or 0:,}")
            return
        previous = indexed
        await asyncio.sleep(1)
    sys.exit(f"rebuild: qdrant {collection} still indexing after {INDEX_TIMEOUT:.0f}s")


async def _project_qdrant(conn: asyncpg.Connection, dim: int) -> dict[str, int]:
    client = AsyncQdrantClient(url=QDRANT_URL, timeout=120)
    counts: dict[str, int] = {}
    try:
        for collection in ("items", "users"):
            if await client.collection_exists(collection):
                await client.delete_collection(collection)
        # collection config (HNSW params, indexing threshold) lives in the
        # adapter — the loader must never drift from what serving expects
        await QdrantVector(client, dim=dim).ensure_collections()
        for collection, table, id_col in (
            ("items", "item_vectors", "item_id"),
            ("users", "user_vectors", "user_id"),
        ):
            t0 = time.perf_counter()
            total = 0
            batch: list[PointStruct] = []
            # server-side cursor: 220k 256-dim vectors stream, never fully materialised
            async with conn.transaction():
                async for row in conn.cursor(f"SELECT {id_col}, vec FROM {table}"):
                    batch.append(PointStruct(id=row[0], vector=list(row[1])))
                    if len(batch) >= QDRANT_BATCH:
                        await client.upsert(collection, points=batch)
                        total += len(batch)
                        batch = []
            if batch:
                await client.upsert(collection, points=batch)
                total += len(batch)
            dt = time.perf_counter() - t0
            print(f"rebuild: qdrant {collection} — {total:,} points sent in {dt:.1f}s")
            await _await_indexed(client, collection)
            # counted from qdrant, never from the streamed total: comparing
            # postgres against a number postgres produced can only ever agree
            counts[collection] = (await client.count(collection, exact=True)).count
    finally:
        await client.close()
    return counts


async def _export_csvs(conn: asyncpg.Connection) -> None:
    IMPORT_HOST.mkdir(parents=True, exist_ok=True)
    await conn.copy_from_query(
        f"SELECT key FROM ({DISTINCT_KEYS}) t",
        output=IMPORT_HOST / "nodes.csv",
        format="csv",
        header=True,
    )
    await conn.copy_from_query(
        "SELECT src, dst, edge_type, weight FROM graph_edges",
        output=IMPORT_HOST / "edges.csv",
        format="csv",
        header=True,
    )


async def _project_memgraph(conn: asyncpg.Connection) -> tuple[int, int]:
    t0 = time.perf_counter()
    await _export_csvs(conn)
    print(f"rebuild: memgraph csv export in {time.perf_counter() - t0:.1f}s")

    driver = AsyncGraphDatabase.driver(MEMGRAPH_URI, auth=None)
    try:
        async with driver.session() as session:
            # DROP GRAPH needs analytical storage mode, which we do not want to
            # leave the instance in; batched DETACH DELETE keeps one tx small
            t1 = time.perf_counter()
            deleted = 0
            while True:
                summary = await (
                    await session.run(
                        "MATCH (n:Node) WITH n LIMIT $b DETACH DELETE n", b=DELETE_BATCH
                    )
                ).consume()
                if not summary.counters.nodes_deleted:
                    break
                deleted += summary.counters.nodes_deleted
            print(f"rebuild: memgraph wiped {deleted:,} nodes in {time.perf_counter() - t1:.1f}s")

            # index first: the edge pass MATCHes both endpoints by key
            await (await session.run("CREATE INDEX ON :Node(key)")).consume()

            t1 = time.perf_counter()
            await (
                await session.run(
                    f"USING PERIODIC COMMIT {PERIODIC_COMMIT}"
                    f' LOAD CSV FROM "{IMPORT_CONTAINER}/nodes.csv" WITH HEADER AS row'
                    " CREATE (:Node {key: row.key})"
                )
            ).consume()
            nodes = await _scalar(session, "MATCH (n:Node) RETURN count(n) AS n")
            print(f"rebuild: memgraph {nodes:,} nodes in {time.perf_counter() - t1:.1f}s")

            # graph_edges is already doubled — one directed CREATE per row
            t1 = time.perf_counter()
            await (
                await session.run(
                    f"USING PERIODIC COMMIT {PERIODIC_COMMIT}"
                    f' LOAD CSV FROM "{IMPORT_CONTAINER}/edges.csv" WITH HEADER AS row'
                    " MATCH (a:Node {key: row.src}), (b:Node {key: row.dst})"
                    " CREATE (a)-[:REL {edge_type: row.edge_type,"
                    " weight: ToFloat(row.weight)}]->(b)"
                )
            ).consume()
            edges = await _scalar(session, "MATCH ()-[r:REL]->() RETURN count(r) AS n")
            print(f"rebuild: memgraph {edges:,} edges in {time.perf_counter() - t1:.1f}s")
        return nodes, edges
    finally:
        await driver.close()


async def _scalar(session: AsyncSession, query: str) -> int:
    record = await (await session.run(query)).single()
    assert record is not None
    return int(record["n"])


async def rebuild_hydra(dsn: str = HYDRA_DSN) -> None:
    """Drop and regenerate both projections from Postgres alone."""
    t0 = time.perf_counter()
    conn = await _connect(dsn)
    try:
        dim = await conn.fetchval("SELECT array_length(vec, 1) FROM item_vectors LIMIT 1")
        if dim is None:
            raise SystemExit("rebuild: postgres has no vectors — run `make load PLATFORM=hydra`")
        pg: dict[str, int] = {
            "items": await conn.fetchval("SELECT count(*) FROM item_vectors"),
            "users": await conn.fetchval("SELECT count(*) FROM user_vectors"),
        }
        pg_edges = await conn.fetchval("SELECT count(*) FROM graph_edges")
        pg_nodes = await conn.fetchval(f"SELECT count(*) FROM ({DISTINCT_KEYS}) t")

        qd = await _project_qdrant(conn, dim)
        nodes, edges = await _project_memgraph(conn)

        bad = [f"{k}: postgres {pg[k]:,} != qdrant {qd[k]:,}" for k in pg if pg[k] != qd[k]]
        if nodes != pg_nodes:
            bad.append(f"nodes: postgres {pg_nodes:,} != memgraph {nodes:,}")
        if edges != pg_edges:
            bad.append(f"edges: postgres {pg_edges:,} != memgraph {edges:,}")
        if bad:
            sys.exit("rebuild: projection mismatch — " + "; ".join(bad))
        print(
            f"rebuild: verified {pg['items']:,} item + {pg['users']:,} user vectors,"
            f" {pg_nodes:,} nodes, {pg_edges:,} edges"
            f" — hydra projections ready in {time.perf_counter() - t0:.1f}s"
        )
    finally:
        await conn.close()


async def load_hydra(canonical: Path = CANONICAL_DIR, dsn: str = HYDRA_DSN) -> None:
    if not (canonical / "MANIFEST.json").is_file():
        raise SystemExit("load: no canonical data — run `make seed` first")
    conn = await _connect(dsn)
    try:
        await conn.execute(SCHEMA)
        steps: list[tuple[str, Callable[[asyncpg.Connection], Awaitable[int]]]] = [
            ("items", lambda c: _load_items(c, canonical)),
            ("users", lambda c: _load_users(c, canonical)),
            ("interactions", lambda c: _load_interactions(c, canonical)),
            ("item_vectors", lambda c: _load_vectors(c, canonical, "item_vectors", "item_id")),
            ("user_vectors", lambda c: _load_vectors(c, canonical, "user_vectors", "user_id")),
            ("graph_edges", lambda c: _load_edges(c, canonical)),
        ]
        for step, fn in steps:
            if await _done(conn, step):
                print(f"load: {step} up to date")
                continue
            t0 = time.perf_counter()
            # step + manifest mark commit atomically: a crash mid-step rolls
            # everything back, so reruns can never duplicate COPYed rows
            async with conn.transaction():
                rows = await fn(conn)
                await _mark(conn, step, rows, t0)
        await conn.execute("ANALYZE")
    finally:
        await conn.close()
    # projections are part of a first load, not a separate ceremony
    await rebuild_hydra(dsn)
    print("load: hydra ready")
