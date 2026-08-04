"""Platform configuration: config/<platform>.yaml → validated model + fingerprint."""

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from constellate.core.errors import ConfigError

Platform = Literal["lyra", "orion", "hydra", "eridanus"]

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class FusionConfig(BaseModel):
    rrf_k: int = 60
    weights: dict[str, float] = Field(default_factory=lambda: {"vector": 1.0, "graph": 1.0})


class RetrievalConfig(BaseModel):
    candidate_multiplier: int = 5  # fetch multiplier * k per plane before fusion
    graph_seeds: int = 10  # top vector candidates used as graph seeds when no item seed
    max_hops: int = 2


class DataConfig(BaseModel):
    split_cutoff_quantile: float = 0.95
    embedding_dim: int = 256
    random_seed: int = 42


class PlatformConfig(BaseModel):
    platform: Platform
    fusion: FusionConfig = Field(default_factory=FusionConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    engines: dict[str, dict[str, object]] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def load_config(platform: str, config_dir: Path = CONFIG_DIR) -> PlatformConfig:
    path = config_dir / f"{platform}.yaml"
    if not path.is_file():
        raise ConfigError(f"no config for platform {platform!r} at {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a mapping")
    return PlatformConfig.model_validate(raw)
