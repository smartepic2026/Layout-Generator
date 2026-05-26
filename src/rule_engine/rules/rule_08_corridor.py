"""Rule 8 — 복도 배열 (Supply / Return separation).

근거: GMP Layout Logic_0510 §8
- Supply corridor : 인원 입실 + 자재 반입 (높은 청정등급)
- Return corridor : 인원 퇴실 + 폐기물 반출 (낮은 청정등급)
- Supply ↔ Return 직접 연결 금지 (HARD constraint C1)
- 폭: 2000~3000mm, 부족 시 1500mm 이상

여기서는:
- 복도 Room 존재 여부 검증
- constraints에 supply_return_no_direct_connection=True 기록 (이미 default)
- 복도 폭 정량 룰을 constraints.corridor_width_mm에 저장
"""
from __future__ import annotations

from ..kb_loader import flow_policy_kb
from ..schemas import RangeMM
from ..working_state import WorkingState


def apply(state: WorkingState) -> None:
    fp = flow_policy_kb(state.urs.product.modality)
    cfg = fp["corridor_width_mm"]
    pref_lo, pref_hi = cfg["preferred"]

    state.constraints.corridor_width_mm = RangeMM(
        min=cfg["min_allowed"],
        preferred_min=pref_lo,
        preferred_max=pref_hi,
        max=pref_hi,
    )
    state.constraints.supply_return_no_direct_connection = True

    has_supply = state.has_room("R_SUPPLY_CORRIDOR")
    has_return = state.has_room("R_RETURN_CORRIDOR")

    if has_supply and has_return:
        state.log(
            rule_id="rule_8_corridor",
            target="corridors",
            decision=f"supply + return 분리, 폭 {pref_lo}~{pref_hi}mm (최소 {cfg['min_allowed']}mm)",
            reason="공급↔리턴 직접 연결 금지 (교차오염 차단). HARD constraint C1.",
            source="GMP Layout Logic_0510 §8 복도 배열",
        )
    else:
        state.log(
            rule_id="rule_8_corridor",
            target="corridors",
            decision="WARNING: supply 또는 return 복도 누락",
            reason=f"R_SUPPLY_CORRIDOR={has_supply}, R_RETURN_CORRIDOR={has_return}",
        )
