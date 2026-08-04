"""`make load PLATFORM=orion` — canonical parquet → one Postgres 18.

Everything lands in the same database (that is the whole point, ADR 0004):
relational tables, halfvec vector tables + HNSW, the doubled-edge table the
CTE adapter reads, and the AGE graph. Steps are idempotent via a
load_manifest table; `make down PLATFORM=orion && docker volume rm
constellate-orion_orion-data` for a full rebuild.

AGE bulk load uses ag_catalog.load_labels_from_file / load_edges_from_file,
which read files on the *server*, jailed under /tmp/age/: the compose file
bind-mounts data/orion/age-import to /tmp/age/age-import. A remote DSN
needs those CSVs shipped to the server first (docs/runbooks/run-orion.md).
"""

import os
import time
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path

import asyncpg
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from constellate.ingest import CANONICAL_DIR, DATA_DIR
from constellate.load import doubled_edges

ORION_DSN = os.environ.get(
    "ORION_DSN", "postgresql://constellate:constellate@localhost:15432/constellate"
)
AGE_GRAPH = "constellate"
AGE_IMPORT_HOST = DATA_DIR / "orion" / "age-import"
AGE_IMPORT_CONTAINER = "age-import"  # AGE 1.7 jails load paths under /tmp/age/
INTERACTIONS_CHUNK = 500_000
VECTOR_CHUNK = 2_000

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;
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
CREATE TABLE IF NOT EXISTS graph_edges(
    src text NOT NULL, dst text NOT NULL, edge_type text NOT NULL,
    weight double precision NOT NULL, PRIMARY KEY (src, dst, edge_type));
CREATE INDEX IF NOT EXISTS graph_edges_cover
    ON graph_edges (src, edge_type) INCLUDE (dst, weight);
"""


async def _done(conn: asyncpg.Connection, step: str) -> bool:
    return await conn.fetchval("SELECT 1 FROM load_manifest WHERE step = $1", step) is not None


async def _mark(conn: asyncpg.Connection, step: str, rows: int, t0: float) -> None:
    await conn.execute(
        "INSERT INTO load_manifest(step, rows) VALUES ($1, $2)"
        " ON CONFLICT (step) DO UPDATE SET rows = $2, completed_at = now()",
        step,
        rows,
    )
    print(f"load: {step} — {rows:,} rows in {time.perf_counter() - t0:.1f}s")


def _vec_lit(vec: Iterable[float]) -> str:
    return "[" + ",".join(f"{x:g}" for x in vec) + "]"


async def _load_items(conn: asyncpg.Connection, canonical: Path) -> int:
    items = pd.read_parquet(canonical / "items.parquet")
    inter = pq.read_table(
        canonical / "interactions.parquet",
        columns=["item_id", "rating", "split"],
        filters=[("split", "=", "train")],
    ).to_pandas()
    # column named "count" would shadow the namedtuple method in itertuples;
    # zip over columns sidesteps the trap entirely
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
    ids = df[id_col].to_numpy(dtype="int64")
    vecs = np.stack(df["vector"].to_list()).astype("float32")
    dim = vecs.shape[1]
    await conn.execute(
        f"CREATE TABLE IF NOT EXISTS {name}({id_col} int PRIMARY KEY, vec halfvec({dim}) NOT NULL)"
    )
    sql = f"INSERT INTO {name}({id_col}, vec) VALUES ($1, $2::halfvec) ON CONFLICT DO NOTHING"
    for start in range(0, len(ids), VECTOR_CHUNK):
        chunk = [
            (int(i), _vec_lit(v))
            for i, v in zip(
                ids[start : start + VECTOR_CHUNK], vecs[start : start + VECTOR_CHUNK], strict=True
            )
        ]
        await conn.executemany(sql, chunk)
    return len(ids)


async def _load_edges(conn: asyncpg.Connection, canonical: Path) -> int:
    both = doubled_edges(canonical)
    records = list(
        zip(both["src"], both["dst"], both["edge_type"], both["weight"].astype(float), strict=True)
    )
    await conn.copy_records_to_table("graph_edges", records=records)
    return len(records)


async def _build_hnsw(conn: asyncpg.Connection) -> int:
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS item_vectors_hnsw ON item_vectors"
        " USING hnsw (vec halfvec_ip_ops) WITH (m = 16, ef_construction = 200)"
    )
    return 1


async def _load_age(conn: asyncpg.Connection, canonical: Path) -> int:
    """AGE graph via its server-side CSV bulk loader (the only fast path).

    Node CSVs need a numeric linkage column literally named `id`, which is
    why the adapter's node-identity property is `key` (see planes/graph/age).
    """
    both = doubled_edges(canonical)
    keys = pd.concat([both["src"], both["dst"]]).unique()
    node_id = {key: i + 1 for i, key in enumerate(keys)}

    AGE_IMPORT_HOST.mkdir(parents=True, exist_ok=True)
    nodes = pd.DataFrame({"id": [node_id[k] for k in keys], "key": keys})
    nodes.to_csv(AGE_IMPORT_HOST / "nodes.csv", index=False)
    edges = pd.DataFrame(
        {
            "start_id": both["src"].map(node_id),
            "start_vertex_type": "Node",
            "end_id": both["dst"].map(node_id),
            "end_vertex_type": "Node",
            "edge_type": both["edge_type"],
            "weight": both["weight"].astype(float),
        }
    )
    edges.to_csv(AGE_IMPORT_HOST / "edges.csv", index=False)

    await conn.execute("LOAD 'age'")
    await conn.execute('SET search_path = ag_catalog, "$user", public')
    exists = await conn.fetchval("SELECT 1 FROM ag_graph WHERE name = $1", AGE_GRAPH)
    if exists:
        await conn.execute(f"SELECT drop_graph('{AGE_GRAPH}', true)")
    await conn.execute(f"SELECT create_graph('{AGE_GRAPH}')")
    await conn.execute(f"SELECT create_vlabel('{AGE_GRAPH}', 'Node')")
    await conn.execute(f"SELECT create_elabel('{AGE_GRAPH}', 'REL')")
    await conn.execute(
        f"SELECT load_labels_from_file('{AGE_GRAPH}', 'Node',"
        f" '{AGE_IMPORT_CONTAINER}/nodes.csv', true)"
    )
    await conn.execute(
        f"SELECT load_edges_from_file('{AGE_GRAPH}', 'REL', '{AGE_IMPORT_CONTAINER}/edges.csv')"
    )
    # btree on the key property so anchored MATCHes don't seq-scan 117k nodes
    await conn.execute(
        f'CREATE INDEX IF NOT EXISTS node_key_idx ON "{AGE_GRAPH}"."Node"'
        " (ag_catalog.agtype_access_operator(VARIADIC"
        " ARRAY[properties, '\"key\"'::agtype]))"
    )
    return len(both)


async def load_orion(canonical: Path = CANONICAL_DIR, dsn: str = ORION_DSN) -> None:
    if not (canonical / "MANIFEST.json").is_file():
        raise SystemExit("load: no canonical data — run `make seed` first")
    try:
        conn = await asyncpg.connect(dsn, timeout=5)
    except OSError as exc:  # includes ConnectionRefusedError
        raise SystemExit(
            f"load: cannot reach orion at {dsn} — run `make up PLATFORM=orion`"
        ) from exc
    try:
        await conn.execute(SCHEMA)
        steps: list[tuple[str, Callable[[asyncpg.Connection], Awaitable[int]]]] = [
            ("items", lambda c: _load_items(c, canonical)),
            ("users", lambda c: _load_users(c, canonical)),
            ("interactions", lambda c: _load_interactions(c, canonical)),
            ("item_vectors", lambda c: _load_vectors(c, canonical, "item_vectors", "item_id")),
            ("user_vectors", lambda c: _load_vectors(c, canonical, "user_vectors", "user_id")),
            ("graph_edges", lambda c: _load_edges(c, canonical)),
            ("hnsw_index", _build_hnsw),
            ("age_graph", lambda c: _load_age(c, canonical)),
        ]
        for step, fn in steps:
            if await _done(conn, step):
                print(f"load: {step} up to date")
                continue
            t0 = time.perf_counter()
            # step + manifest mark commit atomically: a crash mid-step rolls
            # everything back, so reruns can never duplicate COPYed rows or
            # wedge on a half-loaded table
            async with conn.transaction():
                rows = await fn(conn)
                await _mark(conn, step, rows, t0)
        await conn.execute("ANALYZE")
        print("load: orion ready")
    finally:
        await conn.close()
