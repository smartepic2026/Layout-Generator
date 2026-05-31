"""룰 13 — 차압 cascade (Differential Pressure).

한 줄 요약:
    Room 청정등급에 따라 기본 차압(Pa)을 부여하고, AirLock은 양쪽 인접 Room
    중 더 낮은 등급 쪽보다 +5 Pa 만큼 더 높게 설정한다.

왜 필요한가:
    Excel "Layout 설계 원리 §13" / EU GMP Annex 1: 청정등급이 다른 Room 간
    최소 10~15 Pa 차이 권장. 등급이 높을수록 더 높은 차압. 외부 대기압 0 Pa
    기준의 절대값.

기본 차압 (Pa):
    B = 45, C = 30, D = 15, CNC = 5, NC = 0, A = 60 (참고)

같은 등급 Room 간 차이:
    기본은 0 Pa 차이. 단, Virus filtration 전후의 정제실1·2는 v2 이후 룰
    추가 (v1 prototype에서는 다루지 않음).

무엇을 안 하는가:
    HVAC 시스템 설계 안 함. AL의 connects_higher/lower 매핑은 인접 그래프에
    의존하므로 derive/adjacency 미구현 단계에서는 None 유지.
"""
from __future__ import annotations

import dataclasses

from ..models import AirLock, CleanGrade, Flag, Rationale, Room, RuleEngineInput


# 등급별 기본 차압 (Pa). EU GMP Annex 1 권장치 기반.
_GRADE_TO_PRESSURE: dict[CleanGrade, float] = {
    "A": 60.0,
    "B": 45.0,
    "C": 30.0,
    "D": 15.0,
    "CNC": 5.0,
    "NC": 0.0,
}

# AL이 자신의 등급에서 얼마나 낮은 차압을 갖는지 (cascade인 경우).
_AL_DELTA_BELOW_GRADE = 5.0


def apply(
    rooms: list[Room],
    airlocks: list[AirLock],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> tuple[list[Room], list[AirLock]]:
    """Room·AL 차압 derive."""
    # Room 차압.
    updated_rooms: list[Room] = []
    for room in rooms:
        flags: list[Flag] = []
        base = _GRADE_TO_PRESSURE.get(room.clean_grade)
        if base is None:
            flags.append(Flag(
                rule_id="rule_13_pressure",
                severity="warning",
                note=f"등급 {room.clean_grade!r} 매핑 없음 — DP=0 Pa로 fallback",
            ))
            base = 0.0
        new_room = dataclasses.replace(room, differential_pressure_Pa=base)
        updated_rooms.append(new_room)

        rationale.append(Rationale(
            rule_id="rule_13_pressure",
            target_id=room.room_id,
            decision=f"DP={base} Pa",
            input_facts={
                "clean_grade": room.clean_grade,
            },
            applied_logic=f"Grade {room.clean_grade} 기본 차압.",
            source_reference="Excel: Layout 설계 원리 §13 + EU GMP Annex 1",
            flags=flags,
        ))

    # AL 차압.
    updated_als: list[AirLock] = []
    for al in airlocks:
        base = _GRADE_TO_PRESSURE.get(al.clean_grade, 0.0)
        # AL은 자신의 등급보다 살짝 낮게 (cascade) 또는 둘러싼 차압 따라.
        if al.flow_type == "cascade":
            al_dp = max(0.0, base - _AL_DELTA_BELOW_GRADE)
            logic = f"cascade — Grade {al.clean_grade} 기본({base}) - {_AL_DELTA_BELOW_GRADE} Pa"
        elif al.flow_type == "sink":
            al_dp = max(0.0, base - 10.0)
            logic = f"sink — 양쪽 Room보다 -10 Pa (negative AL)"
        elif al.flow_type == "bubble":
            al_dp = base + 5.0
            logic = f"bubble — 양쪽 Room보다 +5 Pa (positive AL)"
        else:
            al_dp = base
            logic = f"unknown flow_type — fallback to Grade base"

        new_al = dataclasses.replace(al, differential_pressure_Pa=al_dp)
        updated_als.append(new_al)

        rationale.append(Rationale(
            rule_id="rule_13_pressure",
            target_id=al.al_id,
            decision=f"DP={al_dp} Pa",
            input_facts={
                "al_grade": al.clean_grade,
                "flow_type": al.flow_type,
            },
            applied_logic=logic,
            source_reference="Excel: Layout 설계 원리 §13 + EU GMP Annex 1",
            flags=[],
        ))

    return updated_rooms, updated_als
