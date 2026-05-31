"""룰 15 — 출입복장 (passthrough + flag checker).

한 줄 요약:
    URS의 사용자 명시 복장(무균복/무진복/스크럽/일상복)을 통과시키고, gowning_method
    (over gowning / degowning and gowning / regular)를 grade에서 derive한다.

왜 필요한가:
    보고서 v0.2 §4.1의 URS 우선 정책. URS의 "착용 복장" 컬럼을 Room.gowning_type에
    그대로 두고, Excel "출입복장 규정" 시트의 매핑으로 gowning_method를 채운다.

무엇을 안 하는가:
    복장 자동 보정 안 함. URS와 등급 매핑이 불일치하면 Flag로 마킹만 한다.
"""
from __future__ import annotations

import dataclasses

from ..models import CleanGrade, Flag, GowningMethod, GowningType, Rationale, Room, RuleEngineInput


_GRADE_TO_GOWNING: dict[CleanGrade, tuple[GowningType, GowningMethod]] = {
    "B": ("무균복", "over gowning"),
    "C": ("무진복", "over gowning"),
    "D": ("스크럽", "degowning and gowning"),
    "CNC": ("스크럽", "degowning and gowning"),
    "NC": ("일상복", "regular"),
}


def apply(
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[Room]:
    """gowning passthrough + method derive + flag check.

    Args:
        rooms: Room 리스트.
        input_spec: 일관된 시그니처 유지 (사용 안 함).
        rationale: 룰 적용 추적용 리스트.

    Returns:
        gowning_method가 derive된 Room 리스트.
    """
    updated: list[Room] = []
    for room in rooms:
        expected = _GRADE_TO_GOWNING.get(room.clean_grade)
        flags: list[Flag] = []

        if expected is None:
            method: GowningMethod | None = None
            flags.append(Flag(
                rule_id="rule_15_gowning",
                severity="warning",
                note=f"Grade {room.clean_grade}는 출입복장 표에 없음 — gowning_method 미정",
            ))
            expected_type_for_log = "N/A"
            method_for_log = "N/A"
        else:
            expected_type, method = expected
            expected_type_for_log = expected_type
            method_for_log = method
            if room.gowning_type != expected_type:
                flags.append(Flag(
                    rule_id="rule_15_gowning",
                    severity="suspected_violation",
                    note=(
                        f"URS gowning_type={room.gowning_type!r} vs 등급 "
                        f"{room.clean_grade}의 기대치 {expected_type!r} 불일치"
                    ),
                ))

        new_room = dataclasses.replace(room, gowning_method=method)
        updated.append(new_room)

        rationale.append(Rationale(
            rule_id="rule_15_gowning",
            target_id=room.room_id,
            decision=f"gowning_method={method}",
            input_facts={
                "clean_grade": room.clean_grade,
                "urs_gowning_type": room.gowning_type,
            },
            applied_logic=(
                f"Grade {room.clean_grade} → 표준 복장 "
                f"{expected_type_for_log} + method {method_for_log}"
            ),
            source_reference="Excel: 출입복장 규정 시트",
            flags=flags,
        ))
    return updated
