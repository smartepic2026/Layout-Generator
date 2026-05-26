"""RL env import-only test (gymnasium 미설치 시 skip)."""
from __future__ import annotations

import pytest

from src.rl.env import HAS_GYM, EnvConfig, LayoutEnv


@pytest.mark.skipif(not HAS_GYM, reason="gymnasium not installed")
def test_env_basic_step():
    """gymnasium 환경에서 1-step rollout이 터지지 않는지."""
    env = LayoutEnv(EnvConfig(spec_path="examples/golden_spec.json"))
    obs, info = env.reset()
    assert obs.shape == (5,)
    import numpy as np

    action = np.array([0.5, 0.5, 0.0], dtype=np.float32)
    obs2, r, term, trunc, info = env.step(action)
    assert obs2.shape == (5,)
    assert isinstance(r, float)


def test_env_module_imports_without_gym():
    """gymnasium 없어도 모듈 import는 성공."""
    from src.rl import env as _env
    assert hasattr(_env, "LayoutEnv")
    assert hasattr(_env, "EnvConfig")
