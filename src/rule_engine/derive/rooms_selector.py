"""rooms_selector — URS의 Room 명세를 Room 객체로 변환 (passthrough).

한 줄 요약:
    URS Parser가 채운 input_spec.urs_rooms (raw dict 리스트)를 Room 객체로
    1:1 변환한다.

왜 필요한가:
    URS 우선 정책(보고서 v0.2 §4.1)에 따라, 어떤 Room이 들어갈지는 사용자가
    URS에 명시한 그대로 따른다. 룰 엔진의 "from-scratch designer" 역할이
    아닌 "URS expander" 역할이므로(보고서 §4.2), 이 함수는 룰을 거의 적용하지
    않고 단순 변환이다.

무엇을 안 하는가:
    Room 추가·제거를 알아서 하지 않는다. overrides.force_include /
    force_exclude만 적용. derive 필드(area, DP 등)는 후속 룰이 채운다.

입력 dict 스키마 (URS Parser 출력):
    {
        "name_ko": str,
        "name_en": str,
        "category": "주공정 구역" | "보조 구역" | "NC 구역",
        "clean_grade": "A"|"B"|"C"|"D"|"CNC"|"NC",
        "room_flow": "One-way"|"Both-way",
        "gowning_type": str,
        "process_no": list[str],  # 선택
        "air_changes_per_hour": float | None,  # 선택
    }

    Equipment dict (input_spec.urs_equipment):
    {
        "room_en": str,        # 매핑 키
        "instance_id": str,    # 예: "Mixing Tank-1"
        "name": str,           # 장비 종류
        "W": int, "D": int, "H": int,
        "weight_kg": float | None,
        "max_operating_weight_kg": float | None,
        "process_no": list[str],
    }
"""
from __future__ import annotations

import re

from ..models import (
    CleanGrade,
    Equipment,
    Flag,
    Rationale,
    Room,
    RoomCategory,
    RoomFlow,
    RuleEngineInput,
)


# URS 한글 카테고리 → 영문 enum 매핑.
_CATEGORY_MAP: dict[str, RoomCategory] = {
    "주공정 구역": "process",
    "보조 구역": "auxiliary",
    "NC 구역": "NC",
    # 이미 영문이 들어와도 통과.
    "process": "process",
    "auxiliary": "auxiliary",
    "NC": "NC",
}


def _slugify(name_en: str) -> str:
    """영문명을 R_UPPER_UNDERSCORED 형식의 room_id로 변환."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name_en.strip()).strip("_")
    return f"R_{cleaned.upper()}"


def _build_equipment_list(
    room_en: str,
    urs_equipment: list[dict],
) -> list[Equipment]:
    """urs_equipment에서 해당 Room 소속 장비를 Equipment 객체로 변환."""
    out: list[Equipment] = []
    for eq in urs_equipment:
        if eq.get("room_en") != room_en:
            continue
        out.append(Equipment(
            instance_id=eq.get("instance_id", eq.get("name", "")),
            name=eq.get("name", ""),
            width_mm=int(eq.get("W", 0)),
            depth_mm=int(eq.get("D", 0)),
            height_mm=int(eq.get("H", 0)),
            weight_kg=eq.get("weight_kg"),
            max_operating_weight_kg=eq.get("max_operating_weight_kg"),
            process_no=list(eq.get("process_no", [])),
        ))
    return out


def select_required_rooms(
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[Room]:
    """URS Room dict들을 Room 객체로 변환.

    Args:
        input_spec: URS Parser가 urs_rooms / urs_equipment를 채워 넣은 컨테이너.
        rationale: 룰 적용 추적용 리스트.

    Returns:
        Room 객체 리스트 (derive 필드는 None인 상태).
    """
    excluded = set(input_spec.overrides.force_exclude_rooms)
    forced_include = set(input_spec.overrides.force_include_rooms)
    flags: list[Flag] = []

    rooms: list[Room] = []
    seen_names: set[str] = set()

    for raw in input_spec.urs_rooms:
        name_en = raw.get("name_en", "")
        if not name_en:
            flags.append(Flag(
                rule_id="rooms_selector",
                severity="warning",
                note=f"URS Room에 영문명 없음 — skip: {raw!r}",
            ))
            continue
        if name_en in excluded:
            continue
        seen_names.add(name_en)

        category_raw = raw.get("category", "")
        category = _CATEGORY_MAP.get(category_raw)
        if category is None:
            flags.append(Flag(
                rule_id="rooms_selector",
                severity="warning",
                note=f"알 수 없는 category {category_raw!r} — '{name_en}' skip",
            ))
            continue

        clean_grade: CleanGrade = raw.get("clean_grade", "D")
        room_flow: RoomFlow = raw.get("room_flow", "Both-way")
        gowning_type = raw.get("gowning_type", "일상복")
        process_no = list(raw.get("process_no", []))
        acph = raw.get("air_changes_per_hour")
        # 회의 안건 #5 (2026-05-26): URS의 "면적 비율 (%)" 컬럼.
        area_ratio_pct_raw = raw.get("area_ratio_pct")

        equipment = _build_equipment_list(name_en, input_spec.urs_equipment)

        rooms.append(Room(
            room_id=_slugify(name_en),
            name_ko=raw.get("name_ko", name_en),
            name_en=name_en,
            category=category,
            clean_grade=clean_grade,
            room_flow=room_flow,
            gowning_type=gowning_type,
            gowning_method=None,
            equipment=equipment,
            process_no=process_no,
            area_m2=None,
            width_mm=None,
            depth_mm=None,
            ceiling_height_mm=None,
            volume_m3=None,
            differential_pressure_Pa=None,
            air_changes_per_hour=float(acph) if acph is not None else None,
            recovery_time_min=None,
            background_color=None,
            transparency_pct=None,
            well_type_ceiling=False,
            area_ratio_pct=(
                float(area_ratio_pct_raw)
                if area_ratio_pct_raw is not None
                else None
            ),
        ))

    # force_include로 명시되었지만 URS에 없는 Room은 경고만.
    for forced in forced_include:
        if forced not in seen_names:
            flags.append(Flag(
                rule_id="rooms_selector",
                severity="warning",
                note=f"force_include={forced!r} 이지만 URS에 없음",
            ))

    rationale.append(Rationale(
        rule_id="rooms_selector",
        target_id="LAYOUT",
        decision=f"selected {len(rooms)} rooms (excluded {len(excluded)})",
        input_facts={
            "urs_room_count": len(input_spec.urs_rooms),
            "urs_equipment_count": len(input_spec.urs_equipment),
            "force_exclude": list(excluded),
            "force_include": list(forced_include),
        },
        applied_logic="URS Room dict → Room 객체 1:1 변환 + overrides 적용.",
        source_reference="보고서 v0.2 §4.2 (Rule Engine = URS expander)",
        flags=flags,
    ))
    return rooms
