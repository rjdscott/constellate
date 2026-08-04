"""`make load PLATFORM=<p>` — canonical parquet → platform-native stores.

Lyra artifacts land in data/lyra/ (gitignored):
  item_ids.npy / item_vecs.npy   mmap-able exact-search store (ADR 0002)
  user_ids.npy / user_vecs.npy   query vectors
  hnsw.bin                       seeded single-thread HNSW build (slow once)
  kuzu/                          graph db, bulk-copied

The graph gets HAS_GENRE + HAS_TAG + CO_RATED in both directions (traversal
is undirected, see planes/graph/kuzu.py). RATED stays out: 23.75M user→item
edges are the relational plane's data; item expansion never needs them and
they would dominate load time and db size. Revisit if phase 04 wants
user-seeded graph walks.

Steps skip when their outputs exist; delete data/lyra/ to rebuild.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import kuzu
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from constellate.config import load_config
from constellate.ingest import CANONICAL_DIR, DATA_DIR

GRAPH_EDGE_TYPES = ("HAS_GENRE", "HAS_TAG", "CO_RATED")


def _save_vectors(canonical: Path, out: Path) -> None:
    for name, id_col in (("item_vectors", "item_id"), ("user_vectors", "user_id")):
        df = pd.read_parquet(canonical / f"{name}.parquet")
        prefix = name.split("_")[0]
        np.save(out / f"{prefix}_ids.npy", df[id_col].to_numpy(dtype="int64"))
        np.save(out / f"{prefix}_vecs.npy", np.stack(df["vector"].to_list()).astype("float32"))


def _build_hnsw(out: Path, seed: int) -> None:
    from constellate.planes.vector.hnsw import HnswVector

    ids = np.load(out / "item_ids.npy")
    vecs = np.load(out / "item_vecs.npy")
    index = HnswVector(dim=vecs.shape[1], max_elements=len(ids) + 1000, seed=seed)
    index.load_item_vectors(ids, vecs)
    index.save_index(out / "hnsw.bin")


def _build_kuzu(canonical: Path, out: Path) -> None:
    edges = pq.read_table(
        canonical / "edges.parquet",
        filters=[("edge_type", "in", list(GRAPH_EDGE_TYPES))],
    ).to_pandas()
    fwd = edges[["src", "dst", "edge_type", "weight"]]
    rev = fwd.rename(columns={"src": "dst", "dst": "src"})[["src", "dst", "edge_type", "weight"]]
    both = (
        pd.concat([fwd, rev], ignore_index=True)
        .sort_values(["src", "dst", "edge_type", "weight"], ascending=[True, True, True, False])
        .drop_duplicates(["src", "dst", "edge_type"])
    )
    nodes = pd.DataFrame({"id": pd.concat([both["src"], both["dst"]]).unique()})

    # build into kuzu.tmp then rename: an interrupted COPY must not leave a
    # half-built db that the skip-if-exists check would mistake for done
    tmp_db = out / "kuzu.tmp"
    if tmp_db.exists():
        shutil.rmtree(tmp_db)
    db = kuzu.Database(str(tmp_db))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Node(id STRING, PRIMARY KEY(id))")
    conn.execute("CREATE REL TABLE Rel(FROM Node TO Node, edge_type STRING, weight DOUBLE)")
    with tempfile.TemporaryDirectory() as tmp:
        nodes.to_parquet(f"{tmp}/nodes.parquet", index=False)
        both.to_parquet(f"{tmp}/rels.parquet", index=False)
        esc = tmp.replace("\\", "\\\\").replace("'", "\\'")
        conn.execute(f"COPY Node FROM '{esc}/nodes.parquet'")
        conn.execute(f"COPY Rel FROM '{esc}/rels.parquet'")
    conn.close()
    db.close()
    tmp_db.rename(out / "kuzu")
    print(f"load: kuzu graph {len(nodes):,} nodes, {len(both):,} directed edges")


def load_lyra(canonical: Path = CANONICAL_DIR, out: Path | None = None) -> None:
    out = out or DATA_DIR / "lyra"
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_config("lyra")
    if not (canonical / "MANIFEST.json").is_file():
        sys.exit("load: no canonical data — run `make seed` first")

    if all(
        (out / f).is_file()
        for f in ("item_ids.npy", "item_vecs.npy", "user_ids.npy", "user_vecs.npy")
    ):
        print("load: vectors up to date")
    else:
        print("load: building vector npy store")
        _save_vectors(canonical, out)
    if (out / "hnsw.bin").is_file():
        print("load: hnsw index up to date")
    else:
        print("load: building hnsw index (single-thread, seeded — takes a minute)")
        _build_hnsw(out, cfg.data.random_seed)
    if (out / "kuzu").exists():
        print("load: kuzu graph up to date")
    else:
        print("load: building kuzu graph")
        _build_kuzu(canonical, out)
    print("load: lyra ready")


def main() -> None:
    platform = sys.argv[1] if len(sys.argv) > 1 else "lyra"
    if platform != "lyra":
        sys.exit(f"load: platform {platform!r} lands in a later phase (05: orion, 06: hydra)")
    load_lyra()


if __name__ == "__main__":
    main()
