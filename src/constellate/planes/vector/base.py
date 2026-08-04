"""Shared bits for Lyra's two vector adapters (ADR 0002).

Item vectors are assumed L2-normalized (the ingest guarantees it), so inner
product == cosine. User vectors live outside the index — they are queries,
never search results.
"""

import numpy as np
import numpy.typing as npt

from constellate.core.types import UserId, Vector

FloatMatrix = npt.NDArray[np.float32]


class UserVectorStore:
    """id → row lookup over a (possibly mmap-backed) matrix; rows materialize
    per query instead of exploding the whole store into Python lists."""

    def __init__(self) -> None:
        self._user_matrix: FloatMatrix | None = None
        self._user_rows: dict[UserId, int] = {}

    def load_user_vectors(self, ids: npt.NDArray[np.int64], matrix: FloatMatrix) -> None:
        self._user_matrix = matrix
        self._user_rows = {int(u): row for row, u in enumerate(ids)}

    async def get_user_vector(self, user_id: UserId) -> Vector | None:
        row = self._user_rows.get(user_id)
        if row is None or self._user_matrix is None:
            return None
        out: Vector = self._user_matrix[row].tolist()
        return out
