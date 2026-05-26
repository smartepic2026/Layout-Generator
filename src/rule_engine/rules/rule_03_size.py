"""Rule 3 — Room 크기 (Room Sizing).

근거: GMP Layout Logic_0510 §3
- Room 크기는 내부 장비 규격 및 배열로 결정
- 주공정 Room 총합 ∈ [40%, 70%] × TOTAL_AREA (overlap/다품목 → 더 높게)
- 복도 폭: 2000~3000mm, 최소 1500mm
- 전실: 권장 3000×3000mm, 최소 사람·물품 통과 크기
- 천정 높이: 2700~3000mm + 장비 높이 고려, 큰 장비는 well type ceiling

이 룰은 KB의 recommended_area_m2를 base로 사용하고,
- 장비 footprint 합 + 작업/청소 공간을 가산해 Area_min을 계산
- max(Area_min, recommended) 를 최종 area로 채택
- URS overrides.area_overrides_m2가 있으면 그 값 우선
- 천정고는 장비 H 최댓값으로 well ceiling 여부 결정
"""
from __future__ import annotations

from typing import Optional

from ..kb_loader import equipment_kb, flow_policy_kb, rooms_kb
from ..schemas import Equipment, Room
from ..working_state import WorkingState

# 권장 작업·청소 마진 (룰 3 + 룰 10 일관)
EQUIP_TO_EQUIP_MM = 1000
EQUIP_TO_WALL_MM = 800  # 600~1200 중간값


def apply(state: WorkingState) -> None:
    modality = state.urs.product.modality
    rooms_data = rooms_kb(modality)["rooms"]
    equip_data = equipment_kb()["by_room"]
    fp = flow_policy_kb(modality)
    well_threshold = fp["ceiling_height_mm"]["well_ceiling_threshold_equipment_h_mm"]
    default_h = fp["ceiling_height_mm"]["default"]

    rooms_by_id = {r["id"]: r for r in rooms_data}

    for rid, room in state.rooms.items():
        kb_room = rooms_by_id.get(rid)
        if not kb_room:
            continue

        # 1) 장비 부착 (룰 10에서 정밀 배치, 여기선 footprint 합산용)
        equip_list = _equipment_for_room(kb_room, equip_data)
        room.equipment = equip_list

        # 2) Area 계산
        area_override = state.urs.overrides.area_overrides_m2.get(rid)
        recommended = kb_room.get("recommended_area_m2", 30)
        area_min = _required_floor_area_m2(equip_list)

        if area_override is not None:
            room.area_m2 = float(area_override)
            reason = f"URS overrides.area_overrides_m2[{rid}]={area_override}"
        else:
            chosen = max(area_min, recommended)
            room.area_m2 = float(chosen)
            if area_min > recommended:
                reason = (
                    f"장비 기반 Area_min={area_min:.1f} > 권장={recommended} → Area_min 채택. "
                    f"장비 {len(equip_list)}대, 간격 1000mm/벽 600~1200mm 반영."
                )
            else:
                reason = (
                    f"권장 면적 {recommended} m² ≥ 장비 기반 Area_min={area_min:.1f} → 권장 채택."
                )

        # 3) 천정고 & well ceiling
        tallest = max((e.H_mm for e in equip_list), default=0)
        if tallest > well_threshold:
            room.has_well_ceiling = True
            room.ceiling_height_mm = max(default_h, tallest + 500)
        else:
            room.has_well_ceiling = kb_room.get("well_ceiling_recommended", False)
            room.ceiling_height_mm = max(
                kb_room.get("recommended_ceiling_h_mm", default_h), default_h
            )

        room.volume_m3 = round(room.area_m2 * (room.ceiling_height_mm / 1000.0), 2)

        state.log(
            rule_id="rule_3_size",
            target=rid,
            decision=(
                f"area={room.area_m2:.1f} m², ceiling={room.ceiling_height_mm} mm"
                + (" (well-type)" if room.has_well_ceiling else "")
                + f", volume={room.volume_m3} m³"
            ),
            reason=reason,
            source="GMP Layout Logic_0510 §3 Room 크기",
        )

    # 주공정 Room 총합 비율 검증
    _check_process_area_ratio(state, fp)


def _equipment_for_room(kb_room: dict, equip_data: dict) -> list[Equipment]:
    key = kb_room.get("equipment_room_key")
    if not key:
        return []
    items = equip_data.get(key, [])
    out: list[Equipment] = []
    for it in items:
        out.append(
            Equipment(
                name=it["name"],
                W_mm=it["W"],
                D_mm=it["D"],
                H_mm=it["H"],
                weight_kg=it.get("weight", 0),
                max_op_weight_kg=it.get("max_op_weight", 0),
                process_step=it.get("step"),
                footprint_m2=round((it["W"] * it["D"]) / 1_000_000, 2),
            )
        )
    return out


def _required_floor_area_m2(equip: list[Equipment]) -> float:
    """장비 풋프린트 + 간격 마진을 합산. 단순 합산이지만 안전 마진 포함."""
    if not equip:
        return 0.0
    # 각 장비를 W+gap, D+gap 의 사각형으로 본 면적 합산 → 30% 통행 마진 추가
    total = 0.0
    for e in equip:
        w_eff = (e.W_mm + EQUIP_TO_EQUIP_MM) / 1000.0
        d_eff = (e.D_mm + EQUIP_TO_EQUIP_MM) / 1000.0
        total += w_eff * d_eff
    # 통행/청소 추가 마진 30%
    return round(total * 1.30, 1)


def _check_process_area_ratio(state: WorkingState, fp: dict) -> None:
    ratio_cfg = fp["process_room_area_ratio"]
    ratio_min, ratio_max = ratio_cfg["min"], ratio_cfg["max"]
    total = state.urs.building.total_floor_area_m2

    process_sum = sum(
        r.area_m2 for r in state.rooms.values() if r.category == "process" and not r.is_corridor
    )
    ratio = process_sum / total if total > 0 else 0.0

    state.constraints.process_zone_area_ratio = {
        "min": ratio_min,
        "max": ratio_max,
        "current": round(ratio, 3),
    }

    if not (ratio_min <= ratio <= ratio_max):
        state.log(
            rule_id="rule_3_size",
            target="process_zone_total",
            decision=f"WARNING: 주공정 Room 비율 {ratio:.1%} ∉ [{ratio_min:.0%}, {ratio_max:.0%}]",
            reason=(
                f"주공정 합계 {process_sum:.1f} m² / 전체 {total:.0f} m². "
                "면적 재조정 또는 URS override 권장."
            ),
        )
    else:
        state.log(
            rule_id="rule_3_size",
            target="process_zone_total",
            decision=f"OK: 주공정 비율 {ratio:.1%} ∈ [{ratio_min:.0%}, {ratio_max:.0%}]",
            reason=f"주공정 합계 {process_sum:.1f} m² / 전체 {total:.0f} m².",
        )
