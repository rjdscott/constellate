"""Raw CSVs → items/users/interactions parquet with global temporal split.

Split methodology (ADR 0006 / research 05): one global cutoff at the
`split_cutoff_quantile` timestamp over all ratings — every platform trains on
the same past and is evaluated on the same future. Leakage-free and citable.
"""

from pathlib import Path

import pandas as pd

from constellate.config import DataConfig

PARQUET = {"engine": "pyarrow", "compression": "zstd", "index": False}


def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", compression="zstd", index=False)


def build_canonical(raw: Path, out: Path, cfg: DataConfig) -> int:
    """Write items/users/interactions parquet; return the split cutoff timestamp."""
    movies = pd.read_csv(raw / "movies.csv")
    items = pd.DataFrame(
        {
            "item_id": movies["movieId"].astype("int32"),
            "title": movies["title"],
            "year": movies["title"].str.extract(r"\((\d{4})\)\s*$")[0].astype("Int16"),
            "genres": movies["genres"]
            .str.split("|")
            .map(lambda g: [] if g == ["(no genres listed)"] else g),
        }
    ).sort_values("item_id", ignore_index=True)
    _write(items, out / "items.parquet")

    ratings = pd.read_csv(
        raw / "ratings.csv",
        dtype={"userId": "int32", "movieId": "int32", "rating": "float32", "timestamp": "int64"},
    )
    cutoff = int(ratings["timestamp"].quantile(cfg.split_cutoff_quantile))
    interactions = pd.DataFrame(
        {
            "user_id": ratings["userId"],
            "item_id": ratings["movieId"],
            "rating": ratings["rating"],
            "ts": ratings["timestamp"],
            "split": (ratings["timestamp"] > cutoff).map({False: "train", True: "test"}),
        }
    ).sort_values(["user_id", "ts", "item_id"], ignore_index=True)
    _write(interactions, out / "interactions.parquet")

    train = interactions[interactions["split"] == "train"]
    users = (
        train.groupby("user_id", as_index=False)
        .agg(n_train=("rating", "size"), mean_rating=("rating", "mean"))
        .astype({"n_train": "int32", "mean_rating": "float32"})
        .sort_values("user_id", ignore_index=True)
    )
    _write(users, out / "users.parquet")
    return cutoff
