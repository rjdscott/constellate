"""Dataset ingest: raw ml-25m → canonical parquet every platform loads from.

Layout (both gitignored except the manifest):
  data/raw/ml-25m/       extracted CSVs
  data/canonical/        items/users/interactions/vectors/edges/probes parquet
                         + MANIFEST.json (committed — hashes prove reproducibility)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CANONICAL_DIR = DATA_DIR / "canonical"


def vector_files(arm: str) -> tuple[str, str]:
    """(item_vectors filename, user_vectors filename) for an embedding arm
    (ADR 0006) — every consumer of the vector parquet goes through this so
    switching `data.embedding_arm` can never silently mix svd and neural
    files."""
    if arm == "neural":
        return "item_vectors_neural.parquet", "user_vectors_neural.parquet"
    return "item_vectors.parquet", "user_vectors.parquet"
