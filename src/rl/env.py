"""LayoutEnv — Layout 배치 최적화 RL 환경 (gymnasium 인터페이스).

문제 정식화:
  State : (1) building bbox  (2) 이미 배치된 Room 상태 grid  (3) 남은 Room queue
  Action: 다음 Room의 좌표 + rotation (continuous box 또는 discrete grid)
  Reward: src/reward/scorer.score(spec, layout) 의 incremental delta
  Done  : 모든 Room 배치 완료 OR hard violation 발생 OR max_steps

이 파일은 **스켈레톤**입니다. gymnasium/stable-baselines3 미설치 환경에서도
import 가능하도록 lazy guard를 사용. 실제 학습 시 `pip install gymnasium
stable-baselines3` 필요.

docs/rl_guide.md 참고.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.drawing_agent.layout_solver import Layout, PlacedRoom, Rect, solve as base_solve
from src.reward.scorer import score
from src.contract.schemas import Room, RuleEngineOutput

log = logging.getLogger(__name__)

# Lazy: gym/numpy 없어도 모듈 import는 성공해야 함
try:
    import gymnasium as gym
    from gymnasium import spaces
    import numpy as np
    HAS_GYM = True
except ImportError:  # pragma: no cover
    gym = None
    spaces = None
    np = None
    HAS_GYM = False


@dataclass
class EnvConfig:
    spec_path: str = "examples/golden_spec.json"
    building_w_mm: float = 78500
    building_h_mm: float = 42500
    grid_resolution_mm: int = 1000  # action grid 크기
    max_steps_per_episode: int = 0  # 0이면 len(rooms)
    seed: int = 0


class LayoutEnv:
    """Gym 환경. gymnasium 미설치 시 import는 되지만 reset/step은 불가."""

    metadata = {"render_modes": ["svg"]}

    def __init__(self, cfg: EnvConfig | None = None):
        if not HAS_GYM:
            raise RuntimeError(
                "gymnasium이 설치되지 않았습니다. `pip install gymnasium stable-baselines3` 후 사용하세요."
            )
        self.cfg = cfg or EnvConfig()
        self.spec: RuleEngineOutput = self._load_spec()
        self._init_spaces()
        self._reset_state()

    # ─── public API ───
    def reset(self, *, seed: Optional[int] = None, options: dict | None = None):
        if seed is not None:
            self.cfg.seed = seed
        self._reset_state()
        return self._obs(), {}

    def step(self, action: np.ndarray):
        rid = self.remaining_room_ids[self.step_idx]
        room = self._room_lookup[rid]

        # action: [x_norm, y_norm, rot_idx (0/1)]
        x = float(action[0]) * self.cfg.building_w_mm
        y = float(action[1]) * self.cfg.building_h_mm
        rotated = bool(round(float(action[2])))

        w_mm, h_mm = self._room_size_mm(room, rotated)
        # 건물 내부에 clip
        x = max(0, min(x, self.cfg.building_w_mm - w_mm))
        y = max(0, min(y, self.cfg.building_h_mm - h_mm))

        rect = Rect(x, y, w_mm, h_mm)
        self.layout.rooms[rid] = PlacedRoom(room=room, rect=rect)

        # incremental reward = 현재 score - 이전 score
        cur = score(self.spec, self.layout).total
        delta = cur - self.last_score
        self.last_score = cur

        self.step_idx += 1
        terminated = self.step_idx >= len(self.remaining_room_ids)
        truncated = self.step_idx >= self._max_steps()

        return self._obs(), float(delta), terminated, truncated, {"score": cur}

    def render(self) -> Optional[str]:
        if not self.layout.rooms:
            return None
        from src.drawing_agent.renderer import render
        return render(self.spec, self.layout)

    # ─── internal ───
    def _load_spec(self) -> RuleEngineOutput:
        p = Path(self.cfg.spec_path)
        return RuleEngineOutput.model_validate_json(p.read_text())

    def _init_spaces(self):
        # observation: 단순화 v1
        #   [step_idx_norm, remaining_count_norm, last_score_norm,
        #    next_room_w_norm, next_room_h_norm]
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(5,), dtype=np.float32)
        # action: [x, y, rot]
        self.action_space = spaces.Box(
            low=np.array([0.0, 0.0, 0.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )

    def _reset_state(self):
        self.layout = Layout(
            building_w_mm=self.cfg.building_w_mm,
            building_h_mm=self.cfg.building_h_mm,
        )
        # 배치 순서: process_order 우선, 그 다음 보조/NC
        self.remaining_room_ids = self._room_placement_order()
        self._room_lookup = {r.id: r for r in self.spec.rooms}
        self.step_idx = 0
        self.last_score = score(self.spec, self.layout).total

    def _room_placement_order(self) -> list[str]:
        order = list(self.spec.flow_paths.product_process_order)
        # Non-process는 뒤에
        for r in self.spec.rooms:
            if r.id not in order:
                order.append(r.id)
        return order

    def _room_size_mm(self, room: Room, rotated: bool) -> tuple[float, float]:
        # area_m2 → 정사각형 추정 (RL이 grid에서 조정)
        side = (room.area_m2 * 1_000_000) ** 0.5
        # rotate는 v1에서 단순화 (정사각형이라 동일)
        return side, side

    def _max_steps(self) -> int:
        if self.cfg.max_steps_per_episode > 0:
            return self.cfg.max_steps_per_episode
        return len(self.remaining_room_ids)

    def _obs(self) -> np.ndarray:
        n = len(self.remaining_room_ids)
        if self.step_idx < n:
            next_room = self._room_lookup[self.remaining_room_ids[self.step_idx]]
            nw = (next_room.area_m2 ** 0.5) / 200.0  # rough normalize
            nh = nw
        else:
            nw = nh = 0.0
        return np.array(
            [
                self.step_idx / max(n, 1),
                (n - self.step_idx) / max(n, 1),
                max(0.0, min(1.0, self.last_score / 200.0)),
                nw, nh,
            ],
            dtype=np.float32,
        )
