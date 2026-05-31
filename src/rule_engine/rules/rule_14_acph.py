"""룰 14 — 환기 횟수 ACPH (passthrough + flag checker).

한 줄 요약:
    URS의 사용자 명시 ACPH를 통과시키고, Excel "환기 횟수" 시트 권장 범위와
    비교해 의심 시 flag만 마킹한다. recovery_time도 grade에서 매핑.

왜 필요한가:
    보고서 v0.2 §4.1의 URS 우선 정책. URS 시트2의 "목표 환기횟수 (ACH)"
    값을 그대로 Room.air_changes_per_hour에 둔다. 검증은 Validation Agent에
    위임하지만, 명백한 범위 위반은 rationale에 미리 마킹.

무엇을 안 하는가:
    ACPH 자동 보정 안 함. URS 입력을 보존.
"""
from __future__ import annotations

import dataclasses

from ..models import CleanGrade, Flag, Rationale, Room, RuleEngineInput


# Excel "환기 횟수" 시트 — Grade별 권장 ACPH 범위 (min, max).
# Grade A는 단일방향류(풍속 기준)라 ACPH로 표현하지 않음.
_GRADE_TO_ACPH_RANGE: dict[CleanGrade, tuple[float, float]] = {
    "B": (40.0, 60.0),   # 최소 40~60+
    "C": (20.0, 40.0),
    "D": (6.0, 20.0),
}

# Recovery time (min, max 분).
_GRADE_TO_RECOVERY: dict[CleanGrade, tuple[float, float]] = {
    "B": (15.0, 20.0),
    "C": (15.0, 20.0),
}


def apply(
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[Room]:
    """ACPH passthrough + recovery_time derive + flag check."""
    updated: list[Room] = []
    for room in rooms:
        flags: list[Flag] = []
        acph = room.air_changes_per_hour
        rng = _GRADE_TO_ACPH_RANGE.get(room.clean_grade)

        # 범위 위반 검사 (URS에 ACPH 값이 있을 때만).
        if rng is not None and acph is not None:
            low, high = rng
            # max 범위는 "최소 40~60 이상"처럼 권장 상한이 절대값이 아니므로,
            # 하한만 엄격히 체크하고 상한 초과는 정보 flag.
            if acph < low:
                flags.append(Flag(
                    rule_id="rule_14_acph",
                    severity="suspected_violation",
                    note=(
                        f"ACPH={acph} 이 Grade {room.clean_grade} 권장 "
                        f"하한({low}) 미만"
                    ),
                ))

        # Recovery time 매핑.
        recovery = _GRADE_TO_RECOVERY.get(room.clean_grade)
        recovery_min = recovery[0] if recovery else None

        new_room = dataclasses.replace(room, recovery_time_min=recovery_min)
        updated.append(new_room)

        rationale.append(Rationale(
            rule_id="rule_14_acph",
            target_id=room.room_id,
            decision=f"acph={acph}, recovery_time={recovery_min}",
            input_facts={
                "urs_acph": acph,
                "clean_grade": room.clean_grade,
                "recommended_range": rng,
            },
            applied_logic=(
                f"URS ACPH 통과. Grade {room.clean_grade} 권장 범위 = {rng}."
            ),
            source_reference="Excel: 환기 횟수 시트",
            flags=flags,
        ))
    return updated
