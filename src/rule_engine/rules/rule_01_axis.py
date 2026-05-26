"""Rule 1 — 전체 배열 컨셉 (Layout Axis).

근거: GMP Layout Logic_0510 §1
- 원자재 반입구 → 공정 시작 → 폐기물 반출구 → 공정 종료
- 다층일 경우 엘리베이터 위치 고려
- 보조구역은 입구에 가까운 쪽

산출: state.axis = {
    "material_inlet_clock": int,
    "waste_outlet_clock": int,
    "personnel_entry_clock": int,
    "process_start_side": str,          # "near_material_inlet"
    "process_end_side": str,            # "near_waste_outlet"
    "support_zone_anchor_clock": int,   # 보조구역 앵커
    "needs_elevator": bool,
    "elevator_position_clock": int|None,
}
"""
from __future__ import annotations

from ..working_state import WorkingState


def apply(state: WorkingState) -> None:
    b = state.urs.building

    state.axis = {
        "material_inlet_clock": b.material_inlet_clock,
        "waste_outlet_clock": b.waste_outlet_clock,
        "personnel_entry_clock": b.personnel_entry_clock,
        "elevator_position_clock": b.elevator_position_clock,
        "process_start_side": "near_material_inlet",
        "process_end_side": "near_waste_outlet",
        "support_zone_anchor_clock": _resolve_support_anchor(state),
        "needs_elevator": b.floor_level >= 2,
    }

    state.log(
        rule_id="rule_1_axis",
        target="building",
        decision=(
            f"공정 시작=material({b.material_inlet_clock}시), "
            f"공정 종료=waste({b.waste_outlet_clock}시), "
            f"인원 출입={b.personnel_entry_clock}시"
        ),
        reason=(
            "원자재 반입구 근방에서 공정 시작 → 폐기물 반출구 근방에서 공정 완료. "
            "불필요한 물질 동선 최소화."
        ),
        source="GMP Layout Logic_0510 §1 전체적 배열 컨셉",
    )

    if state.axis["needs_elevator"]:
        if b.elevator_position_clock is None:
            state.log(
                rule_id="rule_1_axis",
                target="building",
                decision="WARNING: 다층 layout인데 엘리베이터 좌표 미지정",
                reason=f"floor_level={b.floor_level} 이지만 elevator_position_clock=None. 층간 동선 그래프 미정.",
            )
        else:
            state.log(
                rule_id="rule_1_axis",
                target="building",
                decision=f"엘리베이터 위치 = {b.elevator_position_clock}시",
                reason="다층 layout에서 층간 사람/물품 이동 경로 확보.",
            )


def _resolve_support_anchor(state: WorkingState) -> int:
    """보조구역 앵커: 사용자 preference + 입구 정보로 결정."""
    pref = state.urs.building.support_area_position_preference
    if pref == "near_material_inlet":
        return state.urs.building.material_inlet_clock
    if pref == "near_personnel_entry":
        return state.urs.building.personnel_entry_clock
    return state.urs.building.material_inlet_clock
