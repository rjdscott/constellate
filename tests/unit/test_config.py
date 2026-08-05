from pathlib import Path

import pytest

from constellate.config import CONFIG_DIR, load_config
from constellate.core.errors import ConfigError


@pytest.mark.parametrize("platform", ["lyra", "orion", "hydra"])
def test_all_platform_configs_load(platform: str) -> None:
    cfg = load_config(platform)
    assert cfg.platform == platform
    assert cfg.fusion.rrf_k == 60


def test_fingerprint_is_stable_and_sensitive() -> None:
    a, b = load_config("lyra"), load_config("lyra")
    assert a.fingerprint() == b.fingerprint()
    b.fusion.rrf_k = 61
    assert a.fingerprint() != b.fingerprint()


def test_embedding_arm_defaults_svd_and_changes_fingerprint() -> None:
    a, b = load_config("lyra"), load_config("lyra")
    assert a.data.embedding_arm == "svd"
    assert a.fingerprint() == b.fingerprint()
    b.data.embedding_arm = "neural"
    assert a.fingerprint() != b.fingerprint()


def test_unknown_platform_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config("vega", config_dir=tmp_path)


def test_config_dir_exists() -> None:
    assert CONFIG_DIR.is_dir()
