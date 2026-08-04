"""The only module that imports concrete adapters. Everything else sees
protocols. `build_service(platform)` wires a ready Service from the
artifacts `make seed` + `make load` produced.
"""

from pathlib import Path

import kuzu
import numpy as np

from constellate.config import load_config
from constellate.core.errors import ConfigError
from constellate.core.pipeline import Pipeline
from constellate.core.protocol import VectorPlane
from constellate.ingest import CANONICAL_DIR, DATA_DIR
from constellate.planes.graph.kuzu import KuzuGraph
from constellate.planes.relational.duckdb import DuckDBRelational
from constellate.planes.vector.flat import FlatVector
from constellate.planes.vector.hnsw import HnswVector
from constellate.service import Service


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


def build_service(platform: str = "lyra") -> Service:
    cfg = load_config(platform)
    if platform != "lyra":
        raise ConfigError(f"platform {platform!r} lands in a later phase (05: orion, 06: hydra)")

    lyra_dir = DATA_DIR / "lyra"
    if not (lyra_dir / "item_ids.npy").is_file():
        raise ConfigError("no lyra artifacts — run `make seed && make load PLATFORM=lyra`")

    engines = cfg.engines.get("vector", {})
    adapter = str(engines.get("adapter", "flat"))
    relational = DuckDBRelational.from_canonical(CANONICAL_DIR)
    vector = _lyra_vector(lyra_dir, adapter, cfg.data.embedding_dim, cfg.data.random_seed)
    graph = KuzuGraph(kuzu.Database(str(lyra_dir / "kuzu"), read_only=True), init_schema=False)
    pipeline = Pipeline(relational, vector, graph, cfg)
    return Service(pipeline, relational, graph, cfg)
