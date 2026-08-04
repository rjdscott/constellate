"""Regenerate the probe set from canonical parquet (logic lives in
constellate.ingest.probes so it is typed and unit-tested; this is the CLI).

    uv run python bench/probes.py
"""

from constellate.config import load_config
from constellate.ingest import CANONICAL_DIR
from constellate.ingest.probes import build_probes

if __name__ == "__main__":
    build_probes(CANONICAL_DIR, load_config("lyra").data.random_seed)
    print(f"probes written to {CANONICAL_DIR / 'probes.parquet'}")
