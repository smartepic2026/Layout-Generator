"""룰 10 — 제조 장비 배치 (정렬 + 간격 룰 부착).

한 줄 요약:
    각 Room의 장비를 세부 공정 No. 순서대로 정렬한다. 간격 정량 룰은 별도
    Constraints 블록으로 전달됨.

왜 필요한가:
    Excel "Layout 설계 원리 §10". 제조 장비는 공정 순서대로 배치해야 한다.
    Room 안의 Equipment 리스트가 URS 입력에서 어떤 순서로 들어왔든, 공정 No.
    오름차순으로 재정렬해야 Documentation Agent가 그대로 좌표 배치하면 된다.

무엇을 안 하는가:
    좌표 배치는 안 한다. 천정형 유틸리티 케이스(중앙 배치)는 v2 이후.
"""
from __future__ import annotations

import dataclasses

from ..models import Equipment, Flag, Rationale, Room, RuleEngineInput


def _sort_key(eq: Equipment) -> tuple:
    """process_no의 첫 번째 항목으로 정렬 (예: 'P1-1' < 'P1-2' < 'P2-1')."""
    if not eq.process_no:
        return ("ZZ", 999, 999, eq.name)  # 공정 매핑 없는 장비는 뒤로
    first = eq.process_no[0]
    # "P1-1." 또는 "P1-1. 배지 원료 칭량" 형태에서 1, 1 추출.
    try:
        head = first.split(".")[0]  # "P1-1"
        major = int(head[1])
        minor = int(head[3]) if len(head) > 3 else 0
        return ("PP", major, minor, eq.name)
    except (ValueError, IndexError):
        return ("PP", 999, 999, eq.name)


def apply(
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[Room]:
    """Equipment 리스트를 process_no 기준으로 정렬."""
    updated: list[Room] = []
    for room in rooms:
        flags: list[Flag] = []
        sorted_eq = sorted(room.equipment, key=_sort_key)

        # 의심: 일부 장비에 process_no가 없으면 작업장 동선 분석이 어려워짐.
        unmapped = [eq.name for eq in sorted_eq if not eq.process_no]
        if unmapped and room.category == "process":
            flags.append(Flag(
                rule_id="rule_10_equipment",
                severity="info",
                note=(
                    f"공정 Room '{room.name_en}'에 process_no 없는 장비: "
                    f"{unmapped}"
                ),
            ))

        new_room = dataclasses.replace(room, equipment=sorted_eq)
        updated.append(new_room)

        rationale.append(Rationale(
            rule_id="rule_10_equipment",
            target_id=room.room_id,
            decision=f"sorted {len(sorted_eq)} equipment by process_no",
            input_facts={
                "equipment_count": len(sorted_eq),
                "unmapped_count": len(unmapped),
            },
            applied_logic="process_no의 (major, minor) 숫자 오름차순.",
            source_reference="Excel: Layout 설계 원리 §10 (장비 배치)",
            flags=flags,
        ))
    return updated
