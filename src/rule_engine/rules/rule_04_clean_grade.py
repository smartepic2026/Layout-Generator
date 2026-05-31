"""룰 4 — 청정등급 (passthrough + color derive + flag checker).

한 줄 요약:
    URS의 사용자 명시 청정등급을 통과시키고, background_color와 transparency를
    derive한다. 룰 위반 의심은 Flag로 마킹만 한다.

왜 필요한가:
    보고서 v0.2 §4.1의 URS 우선 정책. Excel "Layout 설계 원리 §5"의 색상
    매핑을 그대로 따른다. 50% 투명을 적용해 장비가 잘 보이도록 한다.

무엇을 안 하는가:
    URS 값을 수정하지 않는다.
"""
from __future__ import annotations

import dataclasses

from ..models import CleanGrade, Flag, Rationale, Room, RuleEngineInput


_GRADE_TO_COLOR: dict[CleanGrade, str] = {
    "A": "Green-diagonal-black",
    "B": "Green",
    "C": "yellow",
    "D": "Blue",
    "CNC": "Gray-dotted-black",
    "NC": "Gray",
}

_TRANSPARENCY_PCT = 50


def apply(
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[Room]:
    """color/transparency derive + flag check.

    Args:
        rooms: Room 리스트.
        input_spec: closed_system_main_process 참조용.
        rationale: 룰 적용 추적용 리스트.

    Returns:
        background_color / transparency_pct 가 채워진 Room 리스트.
    """
    closed_system = input_spec.product.closed_system_main_process
    updated: list[Room] = []

    for room in rooms:
        color = _GRADE_TO_COLOR.get(room.clean_grade)
        flags: list[Flag] = []

        # 의심 위반 1: 주공정 Room이 Grade D인데 closed system이 아님.
        if (
            room.category == "process"
            and room.clean_grade == "D"
            and not closed_system
        ):
            flags.append(Flag(
                rule_id="rule_04_clean_grade",
                severity="suspected_violation",
                note=(
                    "주공정 Room이 Grade D인데 closed_system_main_process=False. "
                    "Excel §5에 따르면 폐쇄형 장비 미사용 시 Grade C 이상 권고."
                ),
            ))

        # 의심 위반 2: 매핑 테이블에 없는 등급.
        if color is None:
            flags.append(Flag(
                rule_id="rule_04_clean_grade",
                severity="warning",
                note=f"색상 매핑 없음 — clean_grade={room.clean_grade!r}",
            ))
            transparency = None
        else:
            transparency = _TRANSPARENCY_PCT

        new_room = dataclasses.replace(
            room,
            background_color=color,
            transparency_pct=transparency,
        )
        updated.append(new_room)

        rationale.append(Rationale(
            rule_id="rule_04_clean_grade",
            target_id=room.room_id,
            decision=f"grade={room.clean_grade}, color={color}",
            input_facts={
                "urs_clean_grade": room.clean_grade,
                "category": room.category,
                "closed_system_main_process": closed_system,
            },
            applied_logic=(
                f"URS Grade {room.clean_grade} 통과 + 색상 {color!r} + "
                f"50% 투명"
            ),
            source_reference="Excel: Layout 설계 원리 §5 (청정등급·색상)",
            flags=flags,
        ))
    return updated
