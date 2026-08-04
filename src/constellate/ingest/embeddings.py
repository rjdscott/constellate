"""Genome-SVD item vectors + rating-weighted user vectors (ADR 0006).

Items with tag-genome rows get TruncatedSVD(dim) of the item-by-tag relevance
matrix. Long-tail items (no genome) fall back to the mean of their genres'
mean vectors — weaker on purpose, and flagged via `has_genome` so the effect
is measurable. User vectors are the mean-centred, rating-weighted mean of
train item vectors. Everything L2-normalized, float32, seeded.
"""

from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

from constellate.config import DataConfig
from constellate.ingest.canonical import _write

FloatArray = npt.NDArray[np.float32]


def _l2(m: FloatArray) -> FloatArray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return (m / np.where(norms == 0, 1.0, norms)).astype("float32")


def build_item_vectors(raw: Path, out: Path, cfg: DataConfig) -> None:
    genome = pd.read_csv(
        raw / "genome-scores.csv",
        dtype={"movieId": "int32", "tagId": "int32", "relevance": "float32"},
    )
    g_items = np.sort(genome["movieId"].unique())
    tags = np.sort(genome["tagId"].unique())
    mat = csr_matrix(
        (
            genome["relevance"],
            (
                np.searchsorted(g_items, genome["movieId"]),
                np.searchsorted(tags, genome["tagId"]),
            ),
        ),
        shape=(len(g_items), len(tags)),
    )
    dim = min(cfg.embedding_dim, len(tags) - 1, len(g_items) - 1)
    svd = TruncatedSVD(n_components=dim, random_state=cfg.random_seed)
    genome_vecs = _l2(svd.fit_transform(mat).astype("float32"))

    items = pd.read_parquet(out / "items.parquet")
    has_genome = items["item_id"].isin(g_items).to_numpy()
    vecs = np.zeros((len(items), dim), dtype="float32")
    vecs[has_genome] = genome_vecs[np.searchsorted(g_items, items.loc[has_genome, "item_id"])]

    # fallback: mean of per-genre mean vectors, computed from genome items only
    genre_of = items.explode("genres").rename(columns={"genres": "genre"}).dropna(subset=["genre"])
    genre_mean: dict[str, FloatArray] = {}
    with_vec = genre_of[genre_of["item_id"].isin(g_items)]
    for genre, grp in with_vec.groupby("genre"):
        genre_mean[str(genre)] = genome_vecs[np.searchsorted(g_items, grp["item_id"])].mean(axis=0)
    genre_lists: list[list[str]] = items["genres"].to_list()
    for i in np.flatnonzero(~has_genome):
        means = [genre_mean[g] for g in genre_lists[i] if g in genre_mean]
        if means:
            vecs[i] = np.mean(means, axis=0)
    vecs = _l2(vecs)

    _write(
        pd.DataFrame({"item_id": items["item_id"], "vector": list(vecs), "has_genome": has_genome}),
        out / "item_vectors.parquet",
    )


def build_user_vectors(out: Path) -> None:
    iv = pd.read_parquet(out / "item_vectors.parquet")
    item_ids = iv["item_id"].to_numpy()
    vecs = np.stack(iv["vector"].to_list()).astype("float32")

    inter = pd.read_parquet(out / "interactions.parquet")
    train = inter[inter["split"] == "train"]
    users = pd.read_parquet(out / "users.parquet")
    train = train.merge(users[["user_id", "mean_rating"]], on="user_id")
    # mean-centred weights: liked-above-own-average pulls toward, below pushes away
    weight = (train["rating"] - train["mean_rating"]).to_numpy(dtype="float32")

    u_ids = np.sort(train["user_id"].unique())
    w = csr_matrix(
        (
            weight,
            (
                np.searchsorted(u_ids, train["user_id"]),
                np.searchsorted(item_ids, train["item_id"]),
            ),
        ),
        shape=(len(u_ids), len(item_ids)),
    )
    user_vecs = _l2(np.asarray(w @ vecs, dtype="float32"))
    _write(
        pd.DataFrame({"user_id": u_ids.astype("int32"), "vector": list(user_vecs)}),
        out / "user_vectors.parquet",
    )
