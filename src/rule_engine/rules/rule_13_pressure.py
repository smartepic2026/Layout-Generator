"""Rule 13 — 차압(DP) 부여 (Pressure Cascade).

근거: GMP Layout Logic_0510 §13 + EU GMP Annex 1
- Pa 단위, 외부 대기압 = 0
- 청정등급이 다른 Room 간 ≥ 10~15 Pa 차이 (HARD C5)
- 높은 등급 > 낮은 등급 (B > C > D > CNC > NC) (HARD C6)
- 동일 등급은 차압 불필요. 단, Virus filtration 전/후의 정제실1/정제실2는 같은 등급이라도
  정제2가 ≥ 0.5 Pa 더 높게 (중요도 차이)

ACPH/recovery_time/gowning도 여기서 한 번에 attach (등급 기반 KB lookup).
"""
from __future__ import annotations

from ..kb_loader import acph_kb, gowning_kb, rooms_kb
from ..working_state import WorkingState

# 외부 대기 = 0 기준, 등급별 권장 차압 (Pa). EU GMP §13 + Layout Logic 조합.
GRADE_DP = {
    "A":   45.0,   # barrier 내부
    "B":   30.0,
    "C":   15.0,
    "D":    5.0,
    "CNC":  0.0,
    "NC":   0.0,
}
# 인접 등급 간 최소 차압
MIN_INTER_GRADE_DP = 10.0


def apply(state: WorkingState) -> None:
    modality = state.urs.product.modality
    acph_data = acph_kb()["grades"]
    gowning_data = gowning_kb()["grades"]
    rooms_kb_data = rooms_kb(modality)["rooms"]
    rooms_by_id = {r["id"]: r for r in rooms_kb_data}

    # 1. 등급별 기본 DP 부여
    for rid, room in state.rooms.items():
        room.differential_pressure_Pa = GRADE_DP.get(room.clean_grade, 0.0)

    # 2. 정제2 > 정제1 보정 (같은 등급일 때)
    p1, p2 = state.rooms.get("R_PURIFICATION_1"), state.rooms.get("R_PURIFICATION_2")
    if p1 and p2 and p1.clean_grade == p2.clean_grade:
        offset = rooms_by_id.get("R_PURIFICATION_2", {}).get("pressure_offset_pa_vs_p1", 0.5)
        p2.differential_pressure_Pa = p1.differential_pressure_Pa + offset
        state.log(
            rule_id="rule_13_pressure",
            target="R_PURIFICATION_2",
            decision=f"DP={p2.differential_pressure_Pa} Pa (P1 + {offset})",
            reason="Virus Removal 후 공정 중요도 ↑ → 정제2가 정제1보다 +0.5 Pa.",
            source="GMP Layout Logic_0510 §13",
        )

    # 3. 인접 등급 간 ≥ 10 Pa 검증 (constraints에 기록)
    state.constraints.pressure_differential_min_pa = MIN_INTER_GRADE_DP
    state.constraints.pressure_grade_order = ["A", "B", "C", "D", "CNC", "NC"]

    # 4. AL의 DP는 인접 두 Room 사이값
    for al in state.airlocks.values():
        higher_id = al.connects_higher
        lower_id = al.connects_lower
        p_high = state.rooms[higher_id].differential_pressure_Pa if higher_id in state.rooms else None
        p_low = state.rooms[lower_id].differential_pressure_Pa if lower_id in state.rooms else None

        if al.flow_type == "cascade":
            if p_high is not None and p_low is not None:
                al.differential_pressure_Pa = round((p_high + p_low) / 2.0, 1)
        elif al.flow_type == "sink":
            # sink: 양쪽보다 낮음
            base = min(filter(lambda x: x is not None, [p_high, p_low]), default=0.0)
            al.differential_pressure_Pa = max(0.0, base - 5.0)
        elif al.flow_type == "bubble":
            base = max(filter(lambda x: x is not None, [p_high, p_low]), default=0.0)
            al.differential_pressure_Pa = base + 5.0

    # 5. ACPH + gowning 부여 (등급 기반)
    for rid, room in state.rooms.items():
        a = acph_data.get(room.clean_grade, {})
        if a.get("acph_max"):
            room.air_changes_per_hour = a["acph_max"]
        if a.get("recovery_time_min"):
            room.recovery_time_min = a["recovery_time_min"][1] if isinstance(a["recovery_time_min"], list) else a["recovery_time_min"]
        g = gowning_data.get(room.clean_grade, {})
        room.gowning_type = g.get("gowning_type")
        room.gowning_method = g.get("gowning_method")

    state.log(
        rule_id="rule_13_pressure",
        target="all_rooms",
        decision=f"등급별 DP: A={GRADE_DP['A']}, B={GRADE_DP['B']}, C={GRADE_DP['C']}, D={GRADE_DP['D']}, CNC=0, NC=0. AL DP는 flow_type에 따라.",
        reason=(
            f"인접 등급 간 ≥ {MIN_INTER_GRADE_DP} Pa (HARD C5), 등급 순서 B>C>D>CNC>NC (HARD C6). "
            "ACPH + gowning_type/method 도 KB 등급 매핑으로 일괄 attach."
        ),
        source="GMP Layout Logic_0510 §13 + EU GMP Annex 1",
    )
