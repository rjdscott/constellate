"""hnswlib ANN — Lyra's deliberately contrasted second vector adapter
(ADR 0002). Single-threaded and seeded so builds are reproducible; the
recall/latency/filter deltas against FlatVector are the teaching artifact.
Exclusion is a per-candidate Python callback — the cost of that is part of
the lesson, not a bug.
"""

from collections.abc import Iterable
from pathlib import Path

import hnswlib
import numpy as np
import numpy.typing as npt

from constellate.core.types import Candidate, ItemId, Vector
from constellate.planes.vector.base import FloatMatrix, UserVectorStore

M = 16
EF_CONSTRUCTION = 200
EF_SEARCH = 200


class HnswVector(UserVectorStore):
    def __init__(self, dim: int, *, max_elements: int = 200_000, seed: int = 42) -> None:
        super().__init__()
        self._dim = dim
        self._index = hnswlib.Index(space="ip", dim=dim)
        self._index.init_index(
            max_elements=max_elements,
            M=M,
            ef_construction=EF_CONSTRUCTION,
            random_seed=seed,
            allow_replace_deleted=True,
        )
        self._index.set_num_threads(1)  # determinism over speed (ADR 0002)
        self._index.set_ef(EF_SEARCH)
        self._ids: set[ItemId] = set()

    def load_index(self, path: Path, max_elements: int) -> None:
        self._index.load_index(str(path), max_elements=max_elements, allow_replace_deleted=True)
        self._index.set_num_threads(1)
        self._index.set_ef(EF_SEARCH)
        self._ids = {int(i) for i in self._index.get_ids_list()}

    def save_index(self, path: Path) -> None:
        self._index.save_index(str(path))

    def load_item_vectors(self, ids: npt.NDArray[np.int64], matrix: FloatMatrix) -> None:
        self._index.add_items(matrix, ids, replace_deleted=True)
        self._ids.update(int(i) for i in ids)

    async def upsert(self, rows: Iterable[tuple[ItemId, Vector]]) -> None:
        pairs = list(rows)
        ids = np.array([i for i, _ in pairs], dtype="int64")
        vecs = np.array([v for _, v in pairs], dtype="float32")
        self._index.add_items(vecs, ids, replace_deleted=True)
        self._ids.update(int(i) for i in ids)

    async def search(self, vec: Vector, k: int, exclude: set[ItemId]) -> list[Candidate]:
        # hnswlib raises if the filter leaves fewer than k reachable results,
        # so k must be clamped to what the filter can actually return
        k = min(k, len(self._ids - exclude) if exclude else len(self._ids))
        if k == 0:
            return []
        q = np.asarray([vec], dtype="float32")
        labels, distances = self._index.knn_query(
            q,
            k=k,
            num_threads=1,
            filter=(lambda label: label not in exclude) if exclude else None,
        )
        # hnswlib "ip" distance = 1 - inner product; invert back to a score
        return [
            Candidate(item_id=int(label), score=float(1.0 - d), source="vector")
            for label, d in zip(labels[0], distances[0], strict=True)
        ]

    async def get_item_vector(self, item_id: ItemId) -> Vector | None:
        try:
            out: list[float] = self._index.get_items([item_id], return_type="numpy")[0].tolist()
        except RuntimeError:  # unknown id
            return None
        return out
