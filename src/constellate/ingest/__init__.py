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
