"""Exact flat search — Lyra's primary vector plane and every platform's
recall referee (ADR 0002). faiss.IndexFlatIP behind an IDMap2: recall 1.0,
exact exclusion via IDSelectorNotMember, no training, no parameters to tune.
"""

from collections.abc import Iterable

import faiss
import numpy as np
import numpy.typing as npt

from constellate.core.types import Candidate, ItemId, Vector
from constellate.planes.vector.base import FloatMatrix, UserVectorStore


class FlatVector(UserVectorStore):
    def __init__(self, dim: int) -> None:
        super().__init__()
        self._dim = dim
        self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(dim))

    def load_item_vectors(self, ids: npt.NDArray[np.int64], matrix: FloatMatrix) -> None:
        self._index.add_with_ids(np.ascontiguousarray(matrix), ids.astype("int64"))

    async def upsert(self, rows: Iterable[tuple[ItemId, Vector]]) -> None:
        pairs = list(rows)
        ids = np.array([i for i, _ in pairs], dtype="int64")
        vecs = np.array([v for _, v in pairs], dtype="float32")
        # replace-on-upsert; ids not present in the index are a no-op
        self._index.remove_ids(faiss.IDSelectorBatch(ids))
        self._index.add_with_ids(vecs, ids)

    async def search(self, vec: Vector, k: int, exclude: set[ItemId]) -> list[Candidate]:
        if self._index.ntotal == 0:
            return []
        params = None
        if exclude:
            batch = faiss.IDSelectorBatch(np.array(sorted(exclude), dtype="int64"))
            # the stub misses the kwarg ctor; runtime accepts it (swig kwargs)
            params = faiss.SearchParameters(sel=faiss.IDSelectorNot(batch))  # type: ignore[call-arg]
        q = np.asarray([vec], dtype="float32")
        scores, ids = self._index.search(q, k, params=params)
        return [
            Candidate(item_id=int(i), score=float(s), source="vector")
            for i, s in zip(ids[0], scores[0], strict=True)
            if i != -1
        ]

    async def get_item_vector(self, item_id: ItemId) -> Vector | None:
        try:
            out: list[float] = self._index.reconstruct(item_id).tolist()
        except RuntimeError:  # unknown id
            return None
        return out
