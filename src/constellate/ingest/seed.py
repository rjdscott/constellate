"""`make seed` entrypoint: raw download → canonical parquet → MANIFEST.json.

Idempotent: each step is skipped when its outputs already exist, so the
second run is a fast no-op. Delete data/canonical/ to rebuild. The manifest
(committed) records file hashes + row counts — two machines that disagree on
a hash are not running the same experiment.
"""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from constellate.config import load_config
from constellate.ingest import CANONICAL_DIR, RAW_DIR
from constellate.ingest.canonical import build_canonical
from constellate.ingest.download import download_ml25m
from constellate.ingest.edges import build_edges
from constellate.ingest.embeddings import build_item_vectors, build_user_vectors
from constellate.ingest.probes import build_probes


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _step(name: str, outputs: list[Path]) -> bool:
    """True when the step must run (any output missing)."""
    if all(p.is_file() for p in outputs):
        print(f"seed: {name} up to date")
        return False
    print(f"seed: building {name}")
    return True


def seed_all(raw_dir: Path = RAW_DIR, out: Path = CANONICAL_DIR, platform: str = "lyra") -> None:
    cfg = load_config(platform)
    raw = download_ml25m(raw_dir)

    if _step(
        "canonical", [out / f for f in ("items.parquet", "interactions.parquet", "users.parquet")]
    ):
        cutoff = build_canonical(raw, out, cfg.data)
        print(f"seed: split cutoff ts={cutoff}")
    if _step("item_vectors", [out / "item_vectors.parquet"]):
        build_item_vectors(raw, out, cfg.data)
    if _step("user_vectors", [out / "user_vectors.parquet"]):
        build_user_vectors(out)
    if _step("edges", [out / "edges.parquet"]):
        build_edges(raw, out)
    if _step("probes", [out / "probes.parquet"]):
        build_probes(out, cfg.data.random_seed)

    files = {
        p.name: {"sha256": _sha256(p), "rows": pq.read_metadata(p).num_rows}
        for p in sorted(out.glob("*.parquet"))
    }
    manifest = {
        "dataset": "ml-25m",
        "random_seed": cfg.data.random_seed,
        "split_cutoff_quantile": cfg.data.split_cutoff_quantile,
        "config_fingerprint": cfg.fingerprint(),
        "files": files,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"seed: manifest written ({len(files)} files)")


if __name__ == "__main__":
    seed_all()
