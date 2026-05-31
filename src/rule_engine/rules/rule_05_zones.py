"""룰 5 — Room 배열 (zone partitioning).

한 줄 요약:
    Room.category를 기준으로 process / auxiliary / NC 세 리스트로 그룹핑한다.

왜 필요한가:
    Excel "Layout 설계 원리 §6". 공정구역과 보조구역을 분리하는 것이 layout의
    가장 기본 골격이다. URS가 시트2의 "구분" 컬럼으로 이미 분류를 제공하므로
    룰 5는 그것을 Zones 객체로 묶기만 한다. 다만 GMP의 process zone 면적 비율
    (40~70%, 룰 3) 검증은 부수적으로 수행하여 위반 시 Flag로 마킹한다.

무엇을 안 하는가:
    URS의 category 값을 수정하지 않는다. NC 구역의 onsite 여부 조정은 룰 12에서.
"""
from __future__ import annotations

from ..models import Flag, Rationale, Room, Zones


_PROCESS_RATIO_MIN = 0.40
_PROCESS_RATIO_MAX = 0.70


def apply(rooms: list[Room], rationale: list[Rationale]) -> Zones:
    """Room category 기준으로 Zones 객체 빌드 + 비율 검증.

    Args:
        rooms: 현재까지 derive된 Room 리스트.
        rationale: 룰 적용 추적용 리스트.

    Returns:
        process_zone / auxiliary_zone / nc_zone 으로 분류된 Zones.
    """
    process_ids: list[str] = []
    auxiliary_ids: list[str] = []
    nc_ids: list[str] = []
    for room in rooms:
        if room.category == "process":
            process_ids.append(room.room_id)
        elif room.category == "auxiliary":
            auxiliary_ids.append(room.room_id)
        elif room.category == "NC":
            nc_ids.append(room.room_id)

    flags: list[Flag] = []
    areas_filled = all(r.area_m2 is not None for r in rooms)
    process_ratio: float | None = None
    if areas_filled and rooms:
        total = sum(r.area_m2 for r in rooms)
        process_total = sum(
            r.area_m2 for r in rooms if r.category == "process"
        )
        if total > 0:
            process_ratio = process_total / total
            if not (_PROCESS_RATIO_MIN <= process_ratio <= _PROCESS_RATIO_MAX):
                flags.append(Flag(
                    rule_id="rule_05_zones",
                    severity="suspected_violation",
                    note=(
                        f"process zone 비율 {process_ratio:.0%}이 권장 범위 "
                        f"{_PROCESS_RATIO_MIN:.0%}~{_PROCESS_RATIO_MAX:.0%} 밖"
                    ),
                ))

    rationale.append(Rationale(
        rule_id="rule_05_zones",
        target_id="LAYOUT",
        decision=(
            f"process={len(process_ids)}, auxiliary={len(auxiliary_ids)}, "
            f"NC={len(nc_ids)}"
        ),
        input_facts={
            "room_count": len(rooms),
            "process_zone_ratio": process_ratio,
        },
        applied_logic="Room.category 기준 분류 + process zone 면적 비율 검증.",
        source_reference="Excel: Layout 설계 원리 §6 (Room 배열) + §4 (비율)",
        flags=flags,
    ))
    return Zones(
        process_zone=process_ids,
        auxiliary_zone=auxiliary_ids,
        nc_zone=nc_ids,
    )
