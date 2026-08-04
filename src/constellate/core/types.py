"""Core domain types. Engine-specific types must never appear here."""

from typing import Literal

from pydantic import BaseModel, Field

ItemId = int
UserId = int
Vector = list[float]

PlaneName = Literal["relational", "vector", "graph"]


class Candidate(BaseModel):
    """A scored item produced by one plane, before fusion."""

    item_id: ItemId
    score: float
    source: PlaneName
    path: list[str] | None = None  # graph traversal, e.g. ["u:5", "rated", "m:318"]
    hops: int | None = None


class Item(BaseModel):
    item_id: ItemId
    title: str
    year: int | None = None
    genres: list[str] = Field(default_factory=list)
    popularity: float = 0.0
    n_ratings: int = 0
    mean_rating: float | None = None


class UserContext(BaseModel):
    user_id: UserId
    n_ratings: int = 0
    region: str | None = None
    tier: str | None = None


class Edge(BaseModel):
    src: str
    dst: str
    edge_type: str
    weight: float = 1.0


class Recommendation(BaseModel):
    item_id: ItemId
    rank: int
    score: float
    sources: list[PlaneName]
    reason: str | None = None  # rendered from path when explain=True
    path: list[str] | None = None  # same path, unrendered — UIs draw it, humans read `reason`
    metadata: dict[str, object] = Field(default_factory=dict)


class RetrievalRequest(BaseModel):
    user_id: UserId | None = None
    seed_item_id: ItemId | None = None
    k: int = 20
    max_hops: int = 2
    policy: dict[str, object] = Field(default_factory=dict)  # hard eligibility gates
    explain: bool = False
    planes: list[PlaneName] | None = None  # None = all; subset for ablation


class StepTimings(BaseModel):
    relational_ms: float = 0.0
    vector_ms: float = 0.0
    graph_ms: float = 0.0
    fusion_ms: float = 0.0
    total_ms: float = 0.0


class RetrievalResponse(BaseModel):
    recommendations: list[Recommendation]
    timings: StepTimings
    config_fingerprint: str
