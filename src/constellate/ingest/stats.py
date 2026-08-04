"""`python -m constellate.ingest.stats` — canonical dataset at a glance."""

import pandas as pd
import pyarrow.parquet as pq

from constellate.ingest import CANONICAL_DIR


def main() -> None:
    for p in sorted(CANONICAL_DIR.glob("*.parquet")):
        print(f"{p.name}: {pq.read_metadata(p).num_rows:,} rows")

    inter = pq.read_table(CANONICAL_DIR / "interactions.parquet", columns=["split", "ts"])
    split = inter.to_pandas().groupby("split")["ts"].agg(["size", "max"])
    print(f"split: {split['size'].to_dict()} (last train ts {split.at['train', 'max']})")

    iv = pd.read_parquet(CANONICAL_DIR / "item_vectors.parquet", columns=["has_genome"])
    print(f"items with genome vectors: {int(iv['has_genome'].sum()):,} / {len(iv):,}")

    edges = pq.read_table(CANONICAL_DIR / "edges.parquet", columns=["edge_type"])
    print(f"edges: {edges.to_pandas()['edge_type'].value_counts().to_dict()}")

    probes = pd.read_parquet(CANONICAL_DIR / "probes.parquet", columns=["kind"])
    print(f"probes: {probes['kind'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
