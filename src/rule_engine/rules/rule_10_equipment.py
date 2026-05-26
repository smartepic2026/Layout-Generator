"""Rule 10 — 제조 장비 배치 (Equipment Placement Constraints).

근거: GMP Layout Logic_0510 §10
- 공정 순서대로 배치 (제조 flow 우선)
- 장비 ↔ 장비: ≥ 1000mm (작업·청소)
- 장비 ↔ 벽: 600 ~ 1200mm (전기·유틸리티 + 청소)
- 천정형 유틸리티면 Room 중앙 배치 허용

이 룰은 좌표를 직접 정하지 않는다 (Drawing Agent 책임).
Rule Engine은 constraints에 정량 룰만 등록 + 각 Room이 장비를 process_step 순서로 가지도록 확인.
"""
from __future__ import annotations

from ..kb_loader import flow_policy_kb
from ..working_state import WorkingState


def apply(state: WorkingState) -> None:
    fp = flow_policy_kb(state.urs.product.modality)
    sp = fp["equipment_spacing_mm"]

    state.constraints.equipment_clearance_mm = {
        "between_equipment": sp["between_equipment"],
        "equipment_to_wall_min": sp["equipment_to_wall_min"],
        "equipment_to_wall_max": sp["equipment_to_wall_max"],
    }
    state.constraints.airlock_size_mm = {
        "preferred_w_d": fp["airlock_size_mm"]["preferred_w_d"],
        "min_passable_w_d": fp["airlock_size_mm"]["min_passable_w_d"],
    }
    state.constraints.ceiling_height_mm = {
        "default": fp["ceiling_height_mm"]["default"],
        "min": fp["ceiling_height_mm"]["min"],
        "well_ceiling_threshold_equipment_h_mm": fp["ceiling_height_mm"]["well_ceiling_threshold_equipment_h_mm"],
        "room_shape_allowed": state.constraints.ceiling_height_mm.get(
            "room_shape_allowed", ["rectangle", "rectilinear_union"]
        ),
    }

    # 장비를 process_step 순서로 정렬 (이미 KB에서 step 순서대로 들어옴)
    for rid, room in state.rooms.items():
        if not room.equipment:
            continue
        room.equipment.sort(key=lambda e: (e.process_step or "ZZZ", e.name))

    n_with_equipment = sum(1 for r in state.rooms.values() if r.equipment)
    total_equipment = sum(len(r.equipment) for r in state.rooms.values())

    state.log(
        rule_id="rule_10_equipment",
        target="all_process_rooms",
        decision=(
            f"장비 간격 ≥{sp['between_equipment']}mm, 장비-벽 "
            f"{sp['equipment_to_wall_min']}~{sp['equipment_to_wall_max']}mm. "
            f"{n_with_equipment} Room / {total_equipment} 장비, process_step 정렬."
        ),
        reason=(
            "작업/청소 간섭 방지 + 유틸리티 공급 공간 확보. "
            "Drawing Agent가 이 constraint를 hard check."
        ),
        source="GMP Layout Logic_0510 §10 제조 장비의 배치",
    )
