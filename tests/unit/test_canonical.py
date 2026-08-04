"""Determinism: the whole ingest pipeline, run twice on the same raw data,
must produce byte-identical parquet. This is the property MANIFEST.json
asserts for the real dataset."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from constellate.config import DataConfig
from constellate.ingest.canonical import build_canonical
from constellate.ingest.edges import build_edges
from constellate.ingest.embeddings import build_item_vectors, build_user_vectors
from constellate.ingest.probes import build_probes

GENRES = ["Comedy", "Drama", "Horror", "Sci-Fi", "(no genres listed)"]


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Tiny synthetic ml-25m lookalike: 30 movies, 40 users, 12 genome tags."""
    raw = tmp_path_factory.mktemp("raw")
    rng = np.random.default_rng(7)
    movies = pd.DataFrame(
        {
            "movieId": range(1, 31),
            "title": [f"Movie {i} ({1980 + i})" for i in range(1, 31)],
            "genres": [
                "|".join(sorted(rng.choice(GENRES[:4], rng.integers(1, 3), replace=False)))
                if i % 7
                else GENRES[4]
                for i in range(1, 31)
            ],
        }
    )
    movies.to_csv(raw / "movies.csv", index=False)
    n = 600
    ratings = pd.DataFrame(
        {
            "userId": rng.integers(1, 41, n),
            "movieId": rng.integers(1, 31, n),
            "rating": rng.choice([2.0, 3.0, 4.0, 4.5, 5.0], n),
            "timestamp": rng.integers(1_000_000_000, 1_500_000_000, n),
        }
    ).drop_duplicates(["userId", "movieId"])
    ratings.to_csv(raw / "ratings.csv", index=False)
    genome = pd.DataFrame(
        [
            {"movieId": m, "tagId": t, "relevance": round(float(rng.random()), 4)}
            for m in range(1, 21)
            for t in range(1, 13)
        ]
    )
    genome.to_csv(raw / "genome-scores.csv", index=False)
    return raw


def _run(raw: Path, out: Path) -> dict[str, str]:
    cfg = DataConfig(embedding_dim=8, random_seed=42)
    build_canonical(raw, out, cfg)
    build_item_vectors(raw, out, cfg)
    build_user_vectors(out)
    build_edges(raw, out)
    build_probes(out, cfg.random_seed)
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*.parquet"))
    }


def test_determinism(raw_dir: Path, tmp_path: Path) -> None:
    first = _run(raw_dir, tmp_path / "a")
    second = _run(raw_dir, tmp_path / "b")
    assert first.keys() == second.keys()
    assert len(first) == 7  # items users interactions item/user_vectors edges probes
    assert first == second
