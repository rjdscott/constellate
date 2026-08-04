"""The retrieval pipeline: the six-step contract every platform serves identically.

1. relational: user context + exclusions
2. vector:     candidate generation (top-k ANN/exact)
3. graph:      expansion from seeds (concurrent with 2 when seeds are independent)
4. fusion:     weighted RRF
5. relational: hydrate survivors, apply hard policy gates
6. return:     ranked items + sources + paths + per-step timings

The pipeline never imports a concrete adapter; wiring happens in the factory.
"""

import asyncio
import time
from collections.abc import Sequence

from constellate.config import PlatformConfig
from constellate.core.errors import SeedResolutionError
from constellate.core.fusion import rrf
from constellate.core.protocol import GraphPlane, RelationalPlane, VectorPlane
from constellate.core.types import (
    Candidate,
    ItemId,
    PlaneName,
    Recommendation,
    RetrievalRequest,
    RetrievalResponse,
    StepTimings,
    UserContext,
)


def _render_reason(path: Sequence[str] | None) -> str | None:
    return " → ".join(path) if path else None


class Pipeline:
    def __init__(
        self,
        relational: RelationalPlane,
        vector: VectorPlane,
        graph: GraphPlane,
        config: PlatformConfig,
    ) -> None:
        self._relational = relational
        self._vector = vector
        self._graph = graph
        self._config = config

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        t0 = time.perf_counter()
        timings = StepTimings()
        planes = set(request.planes or ("relational", "vector", "graph"))

        # Step 1 — relational context
        step = time.perf_counter()
        ctx: UserContext | None = None
        exclude: set[ItemId] = set()
        if request.user_id is not None and "relational" in planes:
            ctx = await self._relational.get_user_context(request.user_id)
            exclude = await self._relational.exclusions(request.user_id)
        if request.seed_item_id is not None:
            exclude.add(request.seed_item_id)
        timings.relational_ms = (time.perf_counter() - step) * 1000

        # Steps 2 + 3 — vector and graph candidate generation.
        # Concurrent when the graph has its own seed; otherwise graph expands
        # from vector output and must wait.
        fetch = self._config.retrieval.candidate_multiplier * request.k
        vector_cands: list[Candidate] = []
        graph_cands: list[Candidate] = []
        if request.seed_item_id is not None:
            vector_task = (
                self._vector_candidates(request, exclude, fetch) if "vector" in planes else None
            )
            graph_task = (
                self._graph.expand([request.seed_item_id], request.max_hops, fetch)
                if "graph" in planes
                else None
            )
            step = time.perf_counter()
            results = await asyncio.gather(*(t for t in (vector_task, graph_task) if t is not None))
            wall = (time.perf_counter() - step) * 1000
            it = iter(results)
            if vector_task is not None:
                vector_cands = next(it)
                timings.vector_ms = wall  # concurrent wall time; per-plane split needs tracing
            if graph_task is not None:
                graph_cands = next(it)
                timings.graph_ms = wall
        else:
            if "vector" in planes:
                step = time.perf_counter()
                vector_cands = await self._vector_candidates(request, exclude, fetch)
                timings.vector_ms = (time.perf_counter() - step) * 1000
            if "graph" in planes and vector_cands:
                step = time.perf_counter()
                seeds = [c.item_id for c in vector_cands[: self._config.retrieval.graph_seeds]]
                graph_cands = await self._graph.expand(seeds, request.max_hops, fetch)
                timings.graph_ms = (time.perf_counter() - step) * 1000
        graph_cands = [c for c in graph_cands if c.item_id not in exclude]

        # Step 4 — fusion
        step = time.perf_counter()
        ranked: dict[PlaneName, list[Candidate]] = {}
        if vector_cands:
            ranked["vector"] = vector_cands
        if graph_cands:
            ranked["graph"] = graph_cands
        fused = rrf(
            ranked,
            k=self._config.fusion.rrf_k,
            weights=self._config.fusion.weights,
        )
        timings.fusion_ms = (time.perf_counter() - step) * 1000

        # Step 5 — policy gates (hard filter, never a score penalty)
        step = time.perf_counter()
        survivors = [f.item_id for f in fused]
        if "relational" in planes and survivors:
            allowed = set(await self._relational.apply_policy(survivors, ctx, request.policy))
            fused = [f for f in fused if f.item_id in allowed]
        timings.relational_ms += (time.perf_counter() - step) * 1000

        # Step 6 — assemble
        recommendations = [
            Recommendation(
                item_id=f.item_id,
                rank=rank,
                score=f.score,
                sources=f.sources,
                reason=_render_reason(f.path) if request.explain else None,
                path=f.path if request.explain else None,
            )
            for rank, f in enumerate(fused[: request.k], start=1)
        ]
        timings.total_ms = (time.perf_counter() - t0) * 1000
        return RetrievalResponse(
            recommendations=recommendations,
            timings=timings,
            config_fingerprint=self._config.fingerprint(),
        )

    async def _vector_candidates(
        self, request: RetrievalRequest, exclude: set[ItemId], k: int
    ) -> list[Candidate]:
        if request.seed_item_id is not None:
            vec = await self._vector.get_item_vector(request.seed_item_id)
        elif request.user_id is not None:
            vec = await self._vector.get_user_vector(request.user_id)
        else:
            raise SeedResolutionError("request needs user_id or seed_item_id")
        if vec is None:
            return []
        return await self._vector.search(vec, k, exclude)
