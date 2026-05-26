"""Rule 9 — 도어 위치 / 크기 / Swing 방향.

근거: GMP Layout Logic_0510 §9
- 도어 swing 방향 = Room 간 차압이 흐르는 방향
  · 자연스럽게 견고히 닫히도록 (passive fail-safe)
- 기본 폭 1000mm
- MAL은 더 큰 폭 (큰 물품 통과)
- 도어 위치는 자재/사람 동선 최단

이 룰은 adjacency_builder 다음에 실행되며, 차압이 결정된 후(rule 13)에 한 번 더 보정된다.
여기서는:
- door_size_mm 검증/세팅
- swing_to는 룰 13 이후에 계산되므로 일단 None (룰 13 끝나고 보정)
"""
from __future__ import annotations

from ..working_state import WorkingState


def apply(state: WorkingState) -> None:
    n_mal_upgrades = 0
    for adj in state.adjacency:
        if adj.relationship != "door":
            continue

        # MAL 도어는 1500~2000mm 강제
        from_is_mal = adj.from_id.startswith("AL_") and any(
            al.id == adj.from_id and "MAL" in al.type for al in state.airlocks.values()
        )
        to_is_mal = adj.to_id.startswith("AL_") and any(
            al.id == adj.to_id and "MAL" in al.type for al in state.airlocks.values()
        )
        if (from_is_mal or to_is_mal) and adj.door_size_mm < 1500:
            adj.door_size_mm = 1800
            n_mal_upgrades += 1

    state.log(
        rule_id="rule_9_door",
        target="adjacency",
        decision=(
            f"도어 default=1000mm, MAL door≥1500mm. "
            f"swing 방향은 룰 13(차압) 후 보정. MAL 폭 상향 {n_mal_upgrades}건."
        ),
        reason="MAL은 큰 물품 통과 → 1500~2000mm. swing은 차압 cascade에 따라 자연 폐쇄 방향.",
        source="GMP Layout Logic_0510 §9 도어의 위치",
    )


def post_pressure_swing_fix(state: WorkingState) -> None:
    """룰 13 이후 호출: 차압이 낮은 쪽으로 swing_to 설정."""
    for adj in state.adjacency:
        if adj.relationship != "door":
            continue
        p_from = _pressure(state, adj.from_id)
        p_to = _pressure(state, adj.to_id)
        if p_from is None or p_to is None:
            continue
        if p_from > p_to:
            adj.door_swing_to = adj.to_id  # 낮은 쪽으로 열림
        elif p_to > p_from:
            adj.door_swing_to = adj.from_id
        # 같으면 None (양방향)


def _pressure(state: WorkingState, node_id: str) -> float | None:
    if node_id in state.rooms:
        return state.rooms[node_id].differential_pressure_Pa
    if node_id in state.airlocks:
        return state.airlocks[node_id].differential_pressure_Pa
    return None
