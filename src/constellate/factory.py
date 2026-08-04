"""The only module that imports concrete adapters. Everything else sees
protocols. `build_service(platform)` wires a ready Service from the
artifacts `make seed` + `make load` produced. Async because Orion's
connection pool can only be created inside a running event loop — and every
caller (API lifespan, smoke, bench) already lives in one.
"""

import os
from pathlib import Path

import asyncpg
import kuzu
import numpy as np
from neo4j import AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient

from constellate.config import PlatformConfig, load_config
from constellate.core.errors import ConfigError
from constellate.core.pipeline import Pipeline
from constellate.core.protocol import GraphPlane, VectorPlane
from constellate.ingest import CANONICAL_DIR, DATA_DIR
from constellate.planes.graph.age import AgeGraph
from constellate.planes.graph.cte import CteGraph
from constellate.planes.graph.kuzu import KuzuGraph
from constellate.planes.graph.memgraph import MemgraphGraph
from constellate.planes.relational.duckdb import DuckDBRelational
from constellate.planes.relational.postgres import PostgresRelational
from constellate.planes.vector.flat import FlatVector
from constellate.planes.vector.hnsw import HnswVector
from constellate.planes.vector.pgvector import PgVector
from constellate.planes.vector.qdrant import QdrantVector
from constellate.service import Service

AGE_GRAPH = "constellate"  # AGE graph name make load PLATFORM=orion creates


def _lyra_vector(lyra_dir: Path, adapter: str, dim: int, seed: int) -> VectorPlane:
    ids = np.load(lyra_dir / "item_ids.npy")
    vecs = np.load(lyra_dir / "item_vecs.npy", mmap_mode="r")
    plane: FlatVector | HnswVector
    if adapter == "flat":
        plane = FlatVector(dim=dim)
        plane.load_item_vectors(ids, np.asarray(vecs))
    elif adapter == "hnsw":
        plane = HnswVector(dim=dim, max_elements=len(ids) + 1000, seed=seed)
        plane.load_index(lyra_dir / "hnsw.bin", max_elements=len(ids) + 1000)
    else:
        raise ConfigError(f"unknown vector adapter {adapter!r} (flat|hnsw)")
    plane.load_user_vectors(
        np.load(lyra_dir / "user_ids.npy"),
        np.load(lyra_dir / "user_vecs.npy", mmap_mode="r"),
    )
    return plane


def _build_lyra(cfg: PlatformConfig) -> Service:
    lyra_dir = DATA_DIR / "lyra"
    if not (lyra_dir / "item_ids.npy").is_file():
        raise ConfigError("no lyra artifacts — run `make seed && make load PLATFORM=lyra`")

    engines = cfg.engines.get("vector", {})
    adapter = str(engines.get("adapter", "flat"))
    relational = DuckDBRelational.from_canonical(CANONICAL_DIR)
    vector = _lyra_vector(lyra_dir, adapter, cfg.data.embedding_dim, cfg.data.random_seed)
    graph = KuzuGraph(kuzu.Database(str(lyra_dir / "kuzu"), read_only=True), init_schema=False)
    pipeline = Pipeline(relational, vector, graph, cfg)
    return Service(pipeline, relational, vector, graph, cfg)


async def _build_orion(cfg: PlatformConfig) -> Service:
    dsn = os.environ.get("ORION_DSN") or str(
        cfg.engines.get("relational", {}).get(
            "dsn", "postgresql://constellate:constellate@localhost:15432/constellate"
        )
    )
    try:
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=8, timeout=5)
    except (TimeoutError, OSError) as exc:
        raise ConfigError(
            f"cannot reach orion at {dsn} — run `make up PLATFORM=orion`, then load"
        ) from exc
    # same guard as _build_hydra: anything past pool creation that raises would
    # otherwise leak an un-terminated pool for the process's life
    try:
        relational = PostgresRelational(pool)
        vector = PgVector(pool)
        adapter = str(cfg.engines.get("graph", {}).get("adapter", "cte"))
        graph: GraphPlane
        if adapter == "cte":
            graph = CteGraph(pool)
        elif adapter == "age":
            graph = AgeGraph(pool, AGE_GRAPH)
        else:
            raise ConfigError(f"unknown graph adapter {adapter!r} (cte|age)")
        pipeline = Pipeline(relational, vector, graph, cfg)
        return Service(pipeline, relational, vector, graph, cfg)
    except Exception:
        pool.terminate()
        raise


async def _build_hydra(cfg: PlatformConfig) -> Service:
    dsn = os.environ.get("HYDRA_DSN") or str(
        cfg.engines.get("relational", {}).get(
            "dsn", "postgresql://constellate:constellate@localhost:15433/constellate"
        )
    )
    try:
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=8, timeout=5)
    except (TimeoutError, OSError) as exc:
        raise ConfigError(
            f"cannot reach hydra postgres at {dsn} — run `make up PLATFORM=hydra`, then load"
        ) from exc
    # everything past pool creation can raise (bad adapter name, bad url), and
    # an un-terminated pool keeps its connections open for the process's life
    try:
        relational = PostgresRelational(pool)
        vec_cfg = cfg.engines.get("vector", {})
        vec_adapter = str(vec_cfg.get("adapter", "qdrant"))
        if vec_adapter != "qdrant":
            raise ConfigError(f"unknown vector adapter {vec_adapter!r} (qdrant)")
        client = AsyncQdrantClient(
            url=os.environ.get("HYDRA_QDRANT_URL")
            or str(vec_cfg.get("url", "http://localhost:16333")),
            prefer_grpc=True,
            grpc_port=int(str(vec_cfg.get("grpc_port", 16334))),
        )
        vector = QdrantVector(client, dim=cfg.data.embedding_dim)
        graph_cfg = cfg.engines.get("graph", {})
        graph_adapter = str(graph_cfg.get("adapter", "memgraph"))
        if graph_adapter != "memgraph":
            raise ConfigError(f"unknown graph adapter {graph_adapter!r} (memgraph)")
        uri = os.environ.get("HYDRA_MEMGRAPH_URI") or str(
            graph_cfg.get("uri", "bolt://localhost:17687")
        )
        graph = MemgraphGraph(AsyncGraphDatabase.driver(uri, auth=None))
        pipeline = Pipeline(relational, vector, graph, cfg)
        return Service(pipeline, relational, vector, graph, cfg)
    except Exception:
        pool.terminate()
        raise


async def build_service(platform: str = "lyra") -> Service:
    cfg = load_config(platform)
    if platform == "lyra":
        return _build_lyra(cfg)
    if platform == "orion":
        return await _build_orion(cfg)
    if platform == "hydra":
        return await _build_hydra(cfg)
    raise ConfigError(f"unknown platform {platform!r} (lyra|orion|hydra)")
