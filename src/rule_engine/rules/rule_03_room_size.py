"""룰 3 — Room 크기 (area, ceiling, volume) + 회의 안건 #5 비율 lookup.

한 줄 요약:
    Room의 area_m2를 다음 우선순위로 채우고, ceiling_height·volume을 derive한다.

Lookup 우선순위 (회의 안건 #5, 2026-05-26 반영):
    1) overrides.area_overrides   — 사용자 명시 override
    2) preset Room.area_m2         — 이전 룰이 채워둔 값
    3) URS area_ratio_pct          — total_floor_area × pct / 100 (신규)
    4) KB room_legend              — 영문명 매칭
    5) Algorithm B fallback        — 장비 풋프린트 기반 휴리스틱
    6) None + flag

추가 검증 (회의 안건 #5):
    - 모든 Room의 area_ratio_pct 합이 100±0.5% 이내인지 검증 (LAYOUT-level rationale).

천정 높이 매핑 (Excel "Layout 설계 원리 §4"):
    Grade A / B  → 3000mm
    Grade C / D  → 2700mm
    CNC / NC     → 2700mm
"""
from __future__ import annotations

import dataclasses

from ..models import CleanGrade, Flag, Rationale, Room, RuleEngineInput


_ROOM_LEGEND_AREAS: dict[str, float] = {
    "Media preparation": 100.0,
    "Buffer preparation": 200.0,
    "Inoculation": 40.0,
    "Seed train": 150.0,
    "Cell Culture": 150.0,
    "Harvest": 60.0,
    "Purification 1": 300.0,
    "Purification 2": 100.0,
    "Preparation": 80.0,
    "Washing": 60.0,
    "Supply corridor": 150.0,
    "Return corridor": 250.0,
    "Gowning": 30.0,
    "CAL (Common Air Lock)": 16.0,
    "PAL (Personnel Air Lock)": 12.0,
    "MAL (Material Air Lock)": 16.0,
    "Material storage": 100.0,
    "Equipment storage": 100.0,
    "DS storage": 50.0,
    "IPC": 30.0,
    "Cell bank storage": 20.0,
    "CIP supply": 60.0,
    "Gowning Female": 50.0,
    "Gowning Male": 80.0,
    "Corridor": 20.0,
    "Office": 100.0,
    "Toilet (Female)": 20.0,
    "Toilet (Male)": 25.0,
    "Monitoring": 50.0,
    "Lobby": 50.0,
    "Lounge": 30.0,
    "Corridor visitor": 30.0,
    "Mateial-in": 30.0,
    "Waste-out": 30.0,
}

_GRADE_TO_CEILING: dict[CleanGrade, int] = {
    "A": 3000, "B": 3000,
    "C": 2700, "D": 2700,
    "CNC": 2700, "NC": 2700,
}

_GAP_BETWEEN_EQ_MM = 1000
_GAP_WALL_MM = 600
_AISLE_MM = 1500


def _algo_B_fallback(room: Room) -> float | None:
    """장비 W·D 기반 two-wall 면적 추정. 장비 없으면 None."""
    eqs = room.equipment
    if not eqs:
        return None
    n = len(eqs)
    total_w = sum(eq.width_mm for eq in eqs)
    max_d = max(eq.depth_mm for eq in eqs)
    n_long = (n + 1) // 2
    w_long_side = total_w * n_long / n
    length_mm = w_long_side + (n_long - 1) * _GAP_BETWEEN_EQ_MM + 2 * _GAP_WALL_MM
    depth_mm = 2 * max_d + _AISLE_MM + 2 * _GAP_WALL_MM
    return (length_mm * depth_mm) / 1_000_000


def apply(
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[Room]:
    """area·ceiling·volume derive (회의 안건 #5 비율 lookup 반영)."""
    overrides = input_spec.overrides.area_overrides
    total_floor_area = input_spec.building.total_floor_area_m2
    updated: list[Room] = []

    # 합 100% 검증 — 회의 안건 #5.
    ratios_present = [r.area_ratio_pct for r in rooms if r.area_ratio_pct is not None]
    ratio_sum = sum(ratios_present) if ratios_present else 0.0
    ratio_layout_flag: Flag | None = None
    if ratios_present and abs(ratio_sum - 100.0) > 0.5:
        ratio_layout_flag = Flag(
            rule_id="rule_03_room_size",
            severity="suspected_violation",
            note=(
                f"URS 면적 비율 합계 {ratio_sum:.2f}% (목표=100%). "
                "일부 Room의 비율 누락 또는 입력 오류 가능성."
            ),
        )

    for room in rooms:
        flags: list[Flag] = []
        source: str

        if room.name_en in overrides:
            area = overrides[room.name_en]
            source = "override"
        elif room.area_m2 is not None:
            area = room.area_m2
            source = "preset"
        elif room.area_ratio_pct is not None:
            # 회의 안건 #5 (2026-05-26): URS 면적 비율 (%) × 전체 면적.
            area = total_floor_area * room.area_ratio_pct / 100.0
            source = "urs_area_ratio_pct"
        elif room.name_en in _ROOM_LEGEND_AREAS:
            area = _ROOM_LEGEND_AREAS[room.name_en]
            source = "kb_legend"
        else:
            fallback = _algo_B_fallback(room)
            if fallback is not None:
                area = fallback
                source = "algorithm_B"
                flags.append(Flag(
                    rule_id="rule_03_room_size",
                    severity="info",
                    note=(
                        f"'{room.name_en}'이 KB에 없음 → Algorithm B fallback "
                        f"({area:.1f} m²)"
                    ),
                ))
            else:
                area = None
                source = "unknown"
                flags.append(Flag(
                    rule_id="rule_03_room_size",
                    severity="suspected_violation",
                    note=f"'{room.name_en}' 면적 추정 불가 — KB·장비·비율 모두 없음",
                ))

        ceiling = _GRADE_TO_CEILING.get(room.clean_grade, 2700)
        volume = (area * ceiling / 1000.0) if area is not None else None

        new_room = dataclasses.replace(
            room,
            area_m2=area,
            ceiling_height_mm=ceiling,
            volume_m3=volume,
        )
        updated.append(new_room)

        rationale.append(Rationale(
            rule_id="rule_03_room_size",
            target_id=room.room_id,
            decision=f"area={area}, ceiling={ceiling}, volume={volume}",
            input_facts={
                "name_en": room.name_en,
                "clean_grade": room.clean_grade,
                "source": source,
                "area_ratio_pct": room.area_ratio_pct,
                "equipment_count": len(room.equipment),
            },
            applied_logic=(
                f"area={source}, ceiling=Grade {room.clean_grade} 기본값, "
                f"volume = area * ceiling/1000"
            ),
            source_reference="Excel: Layout 설계 원리 §4 + Room 범례 + 회의 §5",
            flags=flags,
        ))

    # 합 100% layout-level 검증 (회의 안건 #5).
    if ratios_present:
        rationale.append(Rationale(
            rule_id="rule_03_room_size",
            target_id="LAYOUT",
            decision=f"area_ratio_pct sum = {ratio_sum:.2f}% (target=100%)",
            input_facts={
                "rooms_with_ratio": len(ratios_present),
                "rooms_without_ratio": len(rooms) - len(ratios_present),
                "ratio_sum": ratio_sum,
                "tolerance": 0.5,
            },
            applied_logic=(
                "회의 안건 #5 (2026-05-26): 모든 Room의 면적 비율 합 "
                "100±0.5% 이내여야 함."
            ),
            source_reference="회의 결정 2026-05-26",
            flags=[ratio_layout_flag] if ratio_layout_flag else [],
        ))
    return updated
