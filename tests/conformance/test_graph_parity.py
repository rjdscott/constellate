"""CteGraph vs MemgraphGraph on identical random graphs — the parity evidence.

memgraph.py's docstring claims its unrolled, split-MATCH chains reproduce
cte.py's unrestricted-walk semantics *exactly*, and that claim is the reason
those clauses are split at all. This is the check that keeps the claim honest:
8 seeded random graphs, every (hops x seed-count x type-filter) combination,
compared field by field — item order, hops, score and path, not just the id set.

Needs both stacks live (orion postgres for the TEMP-table CTE adapter, hydra
memgraph for the scratch-label one), so it skips when either is absent.
"""

import random

import pytest
from conftest import HAS_HYDRA, HAS_ORION, _cte, _memgraph, _teardown

from constellate.core.protocol import GraphPlane
from constellate.core.types import Candidate, Edge

pytestmark = pytest.mark.skipif(
    not (HAS_ORION and HAS_HYDRA), reason="differential test needs both orion and hydra"
)

GRAPHS = 8
EDGES = 80
LIMIT = 20
# ~30 nodes over the conformance prefixes; only m: nodes are expansion results
NODES = (
    [f"m:{i}" for i in range(1, 13)]
    + [f"t:{i}" for i in range(1, 11)]
    + [f"g:{i}" for i in range(1, 9)]
)
ITEMS = [int(k.removeprefix("m:")) for k in NODES if k.startswith("m:")]
EDGE_TYPES = ("HAS_TAG", "HAS_GENRE", "RATED_BY")
TYPE_FILTERS: tuple[list[str] | None, ...] = (None, ["HAS_TAG"], ["HAS_TAG", "HAS_GENRE"])


def _random_edges(rng: random.Random) -> list[Edge]:
    """Deduped on (unordered pair, type): adapters double edges at write time,
    so two rows for the same undirected pair would race each other's weight.
    Weights are continuous — ties in the weight product would make the
    strongest-path tie-break arbitrary, and arbitrary is not comparable."""
    picked: dict[tuple[str, str, str], Edge] = {}
    while len(picked) < EDGES:
        src, dst = rng.sample(NODES, 2)
        edge_type = rng.choice(EDGE_TYPES)
        lo, hi = sorted((src, dst))
        picked.setdefault(
            (lo, hi, edge_type),
            Edge(src=src, dst=dst, edge_type=edge_type, weight=rng.uniform(0.1, 1.0)),
        )
    return list(picked.values())


def _shape(candidates: list[Candidate]) -> list[tuple[int, int | None, float, list[str] | None]]:
    return [(c.item_id, c.hops, round(c.score, 6), c.path) for c in candidates]


@pytest.mark.parametrize("graph_seed", range(GRAPHS))
async def test_memgraph_expansion_matches_cte(graph_seed: int) -> None:
    rng = random.Random(graph_seed)
    edges = _random_edges(rng)
    cte: GraphPlane = await _cte()
    memgraph: GraphPlane = await _memgraph()
    try:
        await cte.upsert_edges(edges)
        await memgraph.upsert_edges(edges)

        nonempty = 0
        for hops in (1, 2, 3):
            for n_seeds in (1, 3):
                seeds = rng.sample(ITEMS, n_seeds)
                for types in TYPE_FILTERS:
                    a = await cte.expand(seeds, hops, LIMIT, types)
                    b = await memgraph.expand(seeds, hops, LIMIT, types)
                    assert _shape(a) == _shape(b), (
                        f"expand mismatch: hops={hops} seeds={seeds} types={types}"
                    )
                    nonempty += bool(a)
        # two empty lists are equal; a graph this dense must return candidates
        # or the whole comparison above proved nothing
        assert nonempty >= 12

        # duplicate seeds are a set on both sides: memgraph's UNWIND would
        # otherwise walk the repeat twice and inflate support
        dup, single = [ITEMS[0], ITEMS[0]], [ITEMS[0]]
        assert _shape(await memgraph.expand(dup, 2, LIMIT)) == _shape(
            await memgraph.expand(single, 2, LIMIT)
        )
        assert _shape(await cte.expand(dup, 2, LIMIT)) == _shape(
            await memgraph.expand(dup, 2, LIMIT)
        )

        for a_id, b_id in zip(ITEMS[:4], ITEMS[4:8], strict=True):
            assert await cte.path_between(a_id, b_id, 3) == await memgraph.path_between(
                a_id, b_id, 3
            ), f"path_between mismatch: {a_id} -> {b_id}"
    finally:
        await _teardown(cte)
        await _teardown(memgraph)
