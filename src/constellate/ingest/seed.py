"""`make seed` entrypoint: raw download → canonical parquet → MANIFEST.json.

Idempotent: each step is skipped when its outputs already exist, so the
second run is a fast no-op. Delete data/canonical/ to rebuild. The manifest
(committed) records file hashes + row counts — two machines that disagree on
a hash are not running the same experiment.

`--arm svd|neural` picks the embedding arm (ADR 0006): svd is the
deterministic default; neural additionally requires the `neural` extra
(fastembed). Canonical/edges/probes are arm-independent and only ever built
once.
"""

import argparse
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from constellate.config import load_config
from constellate.ingest import CANONICAL_DIR, RAW_DIR, vector_files
from constellate.ingest.canonical import build_canonical
from constellate.ingest.download import download_ml25m
from constellate.ingest.edges import build_edges
from constellate.ingest.embeddings import (
    build_item_vectors,
    build_item_vectors_neural,
    build_user_vectors,
)
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


def seed_all(
    raw_dir: Path = RAW_DIR,
    out: Path = CANONICAL_DIR,
    platform: str = "lyra",
    arm: str = "svd",
    model: str = "BAAI/bge-small-en-v1.5",
) -> None:
    cfg = load_config(platform)
    raw = download_ml25m(raw_dir)
    item_file, user_file = vector_files(arm)

    if _step(
        "canonical", [out / f for f in ("items.parquet", "interactions.parquet", "users.parquet")]
    ):
        cutoff = build_canonical(raw, out, cfg.data)
        print(f"seed: split cutoff ts={cutoff}")
    if _step("item_vectors", [out / item_file]):
        if arm == "neural":
            build_item_vectors_neural(raw, out, cfg.data, model=model)
        else:
            build_item_vectors(raw, out, cfg.data)
    if _step("user_vectors", [out / user_file]):
        build_user_vectors(out, arm=arm)
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
    print(f"seed: {arm} arm — manifest written ({len(files)} files)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=["svd", "neural"], default="svd")
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5", help="neural arm model name")
    args = parser.parse_args()
    seed_all(arm=args.arm, model=args.model)


if __name__ == "__main__":
    main()
