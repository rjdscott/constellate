"""Weighted edge list every graph plane ingests (prep §6.3, retained).

Node ids are prefixed strings ("item:1", "user:7", "genre:Comedy", "tag:742")
so one table holds a heterogeneous graph. Types:

  HAS_GENRE  item→genre   weight 1.0
  HAS_TAG    item→tag     genome relevance ≥ 0.5, weight = relevance
  RATED      user→item    train split only, weight = rating
  CO_RATED   item→item    top-20 cosine neighbours over binary "liked"
                          (rating ≥ 4) vectors, min co-support 50; users with
                          >1000 likes excluded (the popularity cap — whales
                          co-rate everything and only add noise)

Edge tables are streamed type-by-type through one ParquetWriter so the 24M-row
RATED set never sits in memory twice.
"""

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.sparse import csr_matrix

SCHEMA = pa.schema(
    [
        ("src", pa.string()),
        ("dst", pa.string()),
        ("edge_type", pa.string()),
        ("weight", pa.float32()),
    ]
)

MIN_SUPPORT = 50
TOP_K = 20
LIKE_THRESHOLD = 4.0
USER_LIKE_CAP = 1000
TAG_RELEVANCE_MIN = 0.5


def _table(src: pd.Series, dst: pd.Series, edge_type: str, weight: pd.Series) -> pa.Table:
    return pa.table(
        {
            "src": src.astype(str),
            "dst": dst.astype(str),
            "edge_type": pd.Series(edge_type, index=src.index),
            "weight": weight.astype("float32"),
        },
        schema=SCHEMA,
    )


def _co_rated(inter: pd.DataFrame) -> Iterator[pa.Table]:
    likes = inter[(inter["split"] == "train") & (inter["rating"] >= LIKE_THRESHOLD)]
    per_user = likes.groupby("user_id")["item_id"].transform("size")
    likes = likes[(per_user >= 2) & (per_user <= USER_LIKE_CAP)]

    item_ids = np.sort(likes["item_id"].unique())
    user_ids = np.sort(likes["user_id"].unique())
    b = csr_matrix(
        (
            np.ones(len(likes), dtype="float32"),
            (
                np.searchsorted(item_ids, likes["item_id"]),
                np.searchsorted(user_ids, likes["user_id"]),
            ),
        ),
        shape=(len(item_ids), len(user_ids)),
    )
    pop = np.asarray(b.sum(axis=1)).ravel()

    for start in range(0, len(item_ids), 4096):
        stop = min(start + 4096, len(item_ids))
        co = (b[start:stop] @ b.T).tocoo()
        keep = (co.data >= MIN_SUPPORT) & (co.row + start != co.col)
        row, col, count = co.row[keep] + start, co.col[keep], co.data[keep]
        cosine = count / np.sqrt(pop[row] * pop[col])
        df = pd.DataFrame({"row": row, "col": col, "w": cosine})
        top = df.sort_values(["row", "w"], ascending=[True, False]).groupby("row").head(TOP_K)
        if len(top):
            yield _table(
                "item:" + pd.Series(item_ids[top["row"]]).astype(str),
                "item:" + pd.Series(item_ids[top["col"]]).astype(str),
                "CO_RATED",
                pd.Series(top["w"].to_numpy()),
            )


def build_edges(raw: Path, out: Path) -> None:
    items = pd.read_parquet(out / "items.parquet")
    inter = pd.read_parquet(out / "interactions.parquet")

    def tables() -> Iterator[pa.Table]:
        g = items.explode("genres").dropna(subset=["genres"])
        yield _table(
            "item:" + g["item_id"].astype(str),
            "genre:" + g["genres"].astype(str),
            "HAS_GENRE",
            pd.Series(1.0, index=g.index),
        )
        genome = pd.read_csv(
            raw / "genome-scores.csv",
            dtype={"movieId": "int32", "tagId": "int32", "relevance": "float32"},
        )
        t = genome[genome["relevance"] >= TAG_RELEVANCE_MIN]
        yield _table(
            "item:" + t["movieId"].astype(str),
            "tag:" + t["tagId"].astype(str),
            "HAS_TAG",
            t["relevance"],
        )
        train = inter[inter["split"] == "train"]
        yield _table(
            "user:" + train["user_id"].astype(str),
            "item:" + train["item_id"].astype(str),
            "RATED",
            train["rating"],
        )
        yield from _co_rated(inter)

    with pq.ParquetWriter(out / "edges.parquet", SCHEMA, compression="zstd") as writer:
        for table in tables():
            writer.write_table(table)
