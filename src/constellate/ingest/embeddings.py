"""Two embedding arms, compared as a first-class ablation (ADR 0006).

svd (deterministic default): items with tag-genome rows get TruncatedSVD(dim)
of the item-by-tag relevance matrix. Long-tail items (no genome) fall back to
the mean of their genres' mean vectors — weaker on purpose, and flagged via
`has_genome` so the effect is measurable.

neural: bge-small-en-v1.5 via fastembed (ONNX, CPU) over a text corpus built
from title + genres + top genome tags, covering all items (not just the
~13.8k with genome rows). fastembed is imported lazily — it is an optional
`neural` extra, not a core dependency, so CI stays ML-free. Documented
alternative per ADR 0006: Qwen3-Embedding-0.6B, via `--model` on the seed CLI.

User vectors (either arm) are the mean-centred, rating-weighted mean of train
item vectors. Everything L2-normalized, float32, seeded where randomness
applies.
"""

from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

from constellate.config import DataConfig
from constellate.ingest import vector_files
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
        out / vector_files("svd")[0],
    )


def build_text_corpus(raw: Path, out: Path, top_tags: int = 15) -> pd.DataFrame:
    """Per-item text for the neural arm — pure and testable, no model.

    "{title}. Genres: {genres comma-joined}. Tags: {top-N genome tags
    comma-joined}", omitting an empty Genres or Tags segment entirely. Tags
    are the top `top_tags` genome-scores rows per item by relevance, ties
    broken by tagId for determinism. Returns item_id, text, has_genome
    (whether the item has any genome rows at all — independent of the top-N
    cut), ordered by item_id.
    """
    items = pd.read_parquet(out / "items.parquet").sort_values("item_id", ignore_index=True)

    tag_names = pd.read_csv(raw / "genome-tags.csv", dtype={"tagId": "int32", "tag": "string"})
    scores = pd.read_csv(
        raw / "genome-scores.csv",
        dtype={"movieId": "int32", "tagId": "int32", "relevance": "float32"},
    ).merge(tag_names, on="tagId", how="left")
    scores = scores.sort_values(
        ["movieId", "relevance", "tagId"], ascending=[True, False, True], ignore_index=True
    )
    top_tags_by_item = (
        scores.groupby("movieId", sort=False).head(top_tags).groupby("movieId")["tag"].apply(list)
    )
    genome_items = set(scores["movieId"].unique())

    def _text(item_id: int, title: str, genres: list[str]) -> str:
        segments = [f"{title}."]
        if len(genres):  # genres round-trips from parquet as a numpy array, not a list
            segments.append(f"Genres: {', '.join(genres)}.")
        item_tags = top_tags_by_item.get(item_id, [])
        if item_tags:
            segments.append(f"Tags: {', '.join(item_tags)}.")
        return " ".join(segments)

    text = [
        _text(item_id, title, genres)
        for item_id, title, genres in zip(
            items["item_id"], items["title"], items["genres"], strict=True
        )
    ]
    has_genome = items["item_id"].isin(genome_items).to_numpy()
    return pd.DataFrame({"item_id": items["item_id"], "text": text, "has_genome": has_genome})


def build_item_vectors_neural(
    raw: Path, out: Path, cfg: DataConfig, model: str = "BAAI/bge-small-en-v1.5"
) -> None:
    """Text-embed the corpus with fastembed — native model dim (384 for
    bge-small), not truncated to cfg.embedding_dim: that field is the SVD
    arm's dimension, the neural arm's dim is the model's."""
    from fastembed import TextEmbedding  # lazy: optional `neural` extra, no CI dep

    corpus = build_text_corpus(raw, out, top_tags=15)
    embedder = TextEmbedding(model_name=model)
    vecs = _l2(np.array(list(embedder.embed(corpus["text"].to_list(), batch_size=256)), "float32"))
    _write(
        pd.DataFrame(
            {"item_id": corpus["item_id"], "vector": list(vecs), "has_genome": corpus["has_genome"]}
        ),
        out / vector_files("neural")[0],
    )


def build_user_vectors(out: Path, arm: str = "svd") -> None:
    item_file, user_file = vector_files(arm)
    iv = pd.read_parquet(out / item_file)
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
        out / user_file,
    )
