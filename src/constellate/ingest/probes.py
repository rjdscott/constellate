"""Graph-necessary probe set — the phase-04 go/no-go hinges on these.

Each probe is (seed item → expected items) where the expectation is reachable
through graph structure but deliberately hostile to pure vector similarity:

  tag_bridge     items sharing a high-relevance genome tag but zero genres
  cold_start     seed has <10 train ratings (vector signal thin) but genome
                 tags; expected = strongest tag-overlap items
  cross_genre    CO_RATED neighbours whose genre sets are disjoint from seed
  path_required  items exactly two CO_RATED hops away (no direct edge)

Everything derives from canonical parquet only, sorted before sampling, and
sampled with the seeded rng — byte-stable across runs.
"""

from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from constellate.ingest.canonical import _write

PER_KIND = 50
MAX_EXPECTED = 10
MIN_EXPECTED = 3
BRIDGE_RELEVANCE = 0.8
COLD_MAX_RATINGS = 10


def _edges(out: Path, edge_type: str) -> pd.DataFrame:
    df: pd.DataFrame = pq.read_table(
        out / "edges.parquet", filters=[("edge_type", "=", edge_type)]
    ).to_pandas()
    return df.drop(columns=["edge_type"])


def _item_ids(s: pd.Series) -> pd.Series:
    return s.str.removeprefix("item:").astype("int32")


def _sample(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Deterministically pick up to PER_KIND probes: sort, then seeded choice."""
    df = df.sort_values("seed_item_id", ignore_index=True)
    if len(df) > PER_KIND:
        df = df.iloc[np.sort(rng.choice(len(df), PER_KIND, replace=False))]
    return df


def _probe_frame(kind: str, groups: pd.Series) -> pd.DataFrame:
    """groups: seed_item_id → sorted expected list; drop thin groups."""
    kept = groups[groups.map(len) >= MIN_EXPECTED].map(lambda e: e[:MAX_EXPECTED])
    return pd.DataFrame(
        {
            "kind": kind,
            "seed_item_id": kept.index.astype("int32"),
            "expected_items": kept.to_numpy(),
        }
    )


def build_probes(out: Path, seed: int) -> None:
    rng = np.random.default_rng(seed)
    items = pd.read_parquet(out / "items.parquet")
    genre_of = dict(zip(items["item_id"], items["genres"].map(frozenset), strict=True))

    has_tag = _edges(out, "HAS_TAG")
    has_tag["item"] = _item_ids(has_tag["src"])
    co = _edges(out, "CO_RATED")
    co["a"] = _item_ids(co["src"])
    co["b"] = _item_ids(co["dst"])

    frames: list[pd.DataFrame] = []

    # tag_bridge: high-relevance tag cohorts, expected = genre-disjoint co-members
    strong = has_tag[has_tag["weight"] >= BRIDGE_RELEVANCE]
    cohort = strong.groupby("dst")["item"].apply(lambda s: sorted(s))
    cohort = cohort[(cohort.map(len) >= 5) & (cohort.map(len) <= 200)]
    bridges: dict[int, list[int]] = {}
    for members in cohort:
        for a in members:
            if a in bridges:
                continue
            disjoint = [m for m in members if m != a and not (genre_of[a] & genre_of[m])]
            if len(disjoint) >= MIN_EXPECTED:
                bridges[a] = disjoint
    frames.append(_sample(_probe_frame("tag_bridge", pd.Series(bridges).sort_index()), rng))

    # cold_start: thin rating history, expected = strongest tag-overlap items
    inter = pq.read_table(out / "interactions.parquet", columns=["item_id", "split"]).to_pandas()
    n_train = inter[inter["split"] == "train"].groupby("item_id").size()
    # reindex over genome items: absent from train = 0 ratings = coldest of all
    n_train = n_train.reindex(sorted(set(has_tag["item"])), fill_value=0)
    cold = sorted(n_train[n_train < COLD_MAX_RATINGS].index.to_numpy())
    top_tags = (
        has_tag.sort_values(["item", "weight"], ascending=[True, False]).groupby("item").head(10)
    )
    tag_sets = top_tags.groupby("item")["dst"].apply(set)
    overlaps: dict[int, list[int]] = {}
    by_tag = top_tags[top_tags["item"].isin(set(has_tag["item"]))].groupby("dst")["item"]
    tag_members = {tag: set(members) for tag, members in by_tag}
    for c in cold:
        counts: dict[int, int] = {}
        for tag in tag_sets.get(c, set()):
            for m in tag_members.get(tag, set()):
                if m != c:
                    counts[m] = counts.get(m, 0) + 1
        ranked = sorted((i for i, n in counts.items() if n >= 3), key=lambda i: (-counts[i], i))
        if len(ranked) >= MIN_EXPECTED:
            overlaps[c] = ranked
    frames.append(_sample(_probe_frame("cold_start", pd.Series(overlaps).sort_index()), rng))

    # cross_genre: CO_RATED neighbours with disjoint genres
    mask = np.fromiter(
        (not (genre_of[a] & genre_of[b]) for a, b in zip(co["a"], co["b"], strict=True)),
        dtype=bool,
        count=len(co),
    )
    disj = co[mask].sort_values(["a", "weight"], ascending=[True, False])
    frames.append(_sample(_probe_frame("cross_genre", disj.groupby("a")["b"].apply(list)), rng))

    # path_required: exactly two CO_RATED hops, no direct edge
    adj = cast(
        dict[int, list[int]],
        co.sort_values(["a", "weight"], ascending=[True, False])
        .groupby("a")["b"]
        .apply(list)
        .to_dict(),
    )
    seeds = np.array(sorted(adj))
    seeds = seeds[np.sort(rng.choice(len(seeds), min(len(seeds), 400), replace=False))]
    two_hop: dict[int, list[int]] = {}
    for s in seeds:
        direct = set(adj[s])
        reached: dict[int, int] = {}
        for mid in adj[s]:
            for end in adj.get(mid, []):
                if end != s and end not in direct:
                    reached[end] = reached.get(end, 0) + 1
        ranked = sorted(reached, key=lambda i: (-reached[i], i))
        if len(ranked) >= MIN_EXPECTED:
            two_hop[int(s)] = ranked
    frames.append(_sample(_probe_frame("path_required", pd.Series(two_hop).sort_index()), rng))

    probes = pd.concat(frames, ignore_index=True)
    probes.insert(0, "probe_id", np.arange(len(probes), dtype="int32"))
    probes["expected_items"] = probes["expected_items"].map(lambda e: np.asarray(e, dtype="int32"))
    _write(probes, out / "probes.parquet")
