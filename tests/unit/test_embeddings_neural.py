"""Neural-arm ingest pieces that don't touch fastembed (ADR 0006): the text
corpus builder and the arm → filename resolver. No model import, no network."""

from pathlib import Path

import pandas as pd
import pytest

from constellate.ingest import vector_files
from constellate.ingest.embeddings import build_text_corpus


def _write_items(out: Path, rows: list[dict[str, object]]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out / "items.parquet", index=False)


def _write_genome(
    raw: Path, tags: list[dict[str, object]], scores: list[dict[str, object]]
) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(tags, columns=["tagId", "tag"]).to_csv(raw / "genome-tags.csv", index=False)
    pd.DataFrame(scores, columns=["movieId", "tagId", "relevance"]).to_csv(
        raw / "genome-scores.csv", index=False
    )


def test_build_text_corpus_template_and_omission(tmp_path: Path) -> None:
    raw, out = tmp_path / "raw", tmp_path / "out"
    _write_items(
        out,
        [
            {"item_id": 1, "title": "Alpha (1990)", "genres": ["Comedy", "Drama"]},
            {"item_id": 2, "title": "Beta (1991)", "genres": []},  # no genome, empty genres too
        ],
    )
    _write_genome(
        raw,
        tags=[{"tagId": 1, "tag": "funny"}, {"tagId": 2, "tag": "clever"}],
        scores=[
            {"movieId": 1, "tagId": 1, "relevance": 0.9},
            {"movieId": 1, "tagId": 2, "relevance": 0.5},
        ],
    )
    corpus = build_text_corpus(raw, out)

    row1 = corpus.loc[corpus["item_id"] == 1].iloc[0]
    assert row1["text"] == "Alpha (1990). Genres: Comedy, Drama. Tags: funny, clever."
    assert bool(row1["has_genome"]) is True

    row2 = corpus.loc[corpus["item_id"] == 2].iloc[0]
    assert row2["text"] == "Beta (1991)."  # both Genres and Tags segments omitted
    assert bool(row2["has_genome"]) is False


def test_build_text_corpus_top_n_tie_break_is_deterministic(tmp_path: Path) -> None:
    raw, out = tmp_path / "raw", tmp_path / "out"
    _write_items(out, [{"item_id": 1, "title": "Gamma (1992)", "genres": ["Horror"]}])
    # three tags tie at the same relevance; top_tags=2 must keep the two lowest tagIds
    _write_genome(
        raw,
        tags=[{"tagId": t, "tag": f"tag{t}"} for t in (3, 1, 2)],
        scores=[{"movieId": 1, "tagId": t, "relevance": 0.5} for t in (3, 1, 2)],
    )
    corpus = build_text_corpus(raw, out, top_tags=2)
    text = corpus.loc[corpus["item_id"] == 1, "text"].iloc[0]
    assert text == "Gamma (1992). Genres: Horror. Tags: tag1, tag2."


def test_build_text_corpus_ordered_by_item_id(tmp_path: Path) -> None:
    raw, out = tmp_path / "raw", tmp_path / "out"
    _write_items(
        out,
        [
            {"item_id": 3, "title": "C (2000)", "genres": []},
            {"item_id": 1, "title": "A (2000)", "genres": []},
            {"item_id": 2, "title": "B (2000)", "genres": []},
        ],
    )
    _write_genome(raw, tags=[], scores=[])
    corpus = build_text_corpus(raw, out)
    assert corpus["item_id"].to_list() == [1, 2, 3]
    assert (~corpus["has_genome"]).all()


@pytest.mark.parametrize(
    ("arm", "expected"),
    [
        ("svd", ("item_vectors.parquet", "user_vectors.parquet")),
        ("neural", ("item_vectors_neural.parquet", "user_vectors_neural.parquet")),
    ],
)
def test_vector_files(arm: str, expected: tuple[str, str]) -> None:
    assert vector_files(arm) == expected


def test_parquet_vector_dim_probes_row_zero(tmp_path: Path) -> None:
    from constellate.load import parquet_vector_dim

    path = tmp_path / "item_vectors.parquet"
    pd.DataFrame({"item_id": [1, 2], "vector": [[0.1] * 384, [0.2] * 384]}).to_parquet(path)
    assert parquet_vector_dim(path) == 384
