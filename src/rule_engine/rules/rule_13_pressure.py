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

같은 등급 Room 간 차이 — 정제실 바이러스 분리 (v2, 2026-06-02, #6):
    v1 에서는 같은 등급 Room 간 차이를 0 Pa 로 두어 정제실1·2 가 동일 차압
    이었다(의도적 미구현). v2 는 Virus filtration 전후 분리를 반영한다:
    product.virus_filtration_required=True 이면 정제실(Purification N)을 공정
    순서대로 정렬해, 하류(post-viral) 정제실일수록 _VIRAL_SEGREGATION_DELTA_PA
    만큼 차압을 높인다. 바이러스 제거 후 제품을 상류(pre-viral) 측 오염으로부터
    보호하기 위해 청정 측(하류)을 더 높은 양압으로 유지하는 cascade 다.
    예) 정제실1(C, 30 Pa) → 정제실2(C, 30+5=35 Pa).

    전실까지 반영 (2026-06-02 결정): 하류 정제실로 들어가는 전실(AL)에도 같은
    보정값을 더해 차압 분리가 Room↔전실 양쪽에서 일관되게 유지된다.
    예) AL-in Purification 2 (cascade C, 25 Pa) → 25+5 = 30 Pa.

무엇을 안 하는가:
    HVAC 시스템 설계 안 함. AL의 connects_higher/lower 매핑은 인접 그래프에
    의존하므로 derive/adjacency 미구현 단계에서는 None 유지.
"""
from __future__ import annotations

import dataclasses
import re

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

# 정제실 바이러스 분리 차등 차압 (Pa/step) — v2 (#6).
# 하류 정제실 1개당 이만큼 차압을 더 높여 post-viral 측을 보호한다.
_VIRAL_SEGREGATION_DELTA_PA = 5.0

# 전실 판정용 (정제실 탐지에서 AL Room 제외).
_AL_PATTERN = re.compile(r"\b(PAL|MAL|CAL)\b", re.IGNORECASE)


def _trailing_number(text: str) -> str | None:
    """문자열 끝쪽 숫자 토큰 추출. 'Purification 2'/'AL_PAL_IN_PURIFICATION_2' → '2'."""
    digits = re.findall(r"\d+", text)
    return digits[-1] if digits else None


def _purification_order_key(room: Room) -> tuple[int, str]:
    """정제실 정렬 키 — 이름 끝 숫자(있으면) → 이름 순."""
    tok = _trailing_number(room.name_en)
    num = int(tok) if tok is not None else 999
    return (num, room.name_en)


def _viral_segregation_offsets(
    rooms: list[Room],
    input_spec: RuleEngineInput,
) -> tuple[dict[str, float], dict[str, float]]:
    """정제실 차압 보정값 — (room_id별, 정제실번호토큰별) 두 매핑 반환.

    product.virus_filtration_required=True 이고 정제실이 2개 이상일 때만 동작.
    공정 순서대로 정렬해 i 번째(0-base) 정제실에 i*_VIRAL_SEGREGATION_DELTA_PA.
    첫 정제실은 0 → 변화 없음. 보정값이 0보다 큰 항목만 담는다.

    Returns:
        (room_offsets, token_offsets):
            room_offsets[room_id]  — 정제 Room 차압 보정 (Room 적용).
            token_offsets[number]  — 정제실 번호 토큰별 보정 (전실 매칭에 사용).
    """
    if not input_spec.product.virus_filtration_required:
        return {}, {}

    purif = [
        r for r in rooms
        if r.category == "process"
        and not _AL_PATTERN.search(r.name_en)
        and "purification" in r.name_en.lower()
    ]
    if len(purif) < 2:
        return {}, {}

    purif_sorted = sorted(purif, key=_purification_order_key)
    room_offsets: dict[str, float] = {}
    token_offsets: dict[str, float] = {}
    for i, r in enumerate(purif_sorted):
        delta = i * _VIRAL_SEGREGATION_DELTA_PA
        if delta > 0:
            room_offsets[r.room_id] = delta
            tok = _trailing_number(r.name_en)
            if tok is not None:
                token_offsets[tok] = delta
    return room_offsets, token_offsets


def _airlock_viral_offset(al: AirLock, token_offsets: dict[str, float]) -> float:
    """전실이 하류 정제실로 향하면 해당 보정값, 아니면 0.

    al_id 에 'PURIFICATION' 이 들어있고 끝 숫자 토큰이 token_offsets 에 있으면
    그 보정값을 적용한다. (예: AL_PAL_IN_PURIFICATION_2 → token '2'.)
    """
    if "PURIFICATION" not in al.al_id.upper():
        return 0.0
    tok = _trailing_number(al.al_id)
    if tok is None:
        return 0.0
    return token_offsets.get(tok, 0.0)


def apply(
    rooms: list[Room],
    airlocks: list[AirLock],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> tuple[list[Room], list[AirLock]]:
    """Room·AL 차압 derive."""
    # 정제실 바이러스 분리 보정값 (v2) — Room·전실 양쪽 적용.
    room_offsets, token_offsets = _viral_segregation_offsets(rooms, input_spec)

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

        offset = room_offsets.get(room.room_id, 0.0)
        dp = base + offset
        new_room = dataclasses.replace(room, differential_pressure_Pa=dp)
        updated_rooms.append(new_room)

        if offset > 0:
            logic = (
                f"Grade {room.clean_grade} 기본({base}) + 바이러스 분리 보정"
                f"(+{offset}) — post-viral 정제실 보호 cascade (v2)."
            )
        else:
            logic = f"Grade {room.clean_grade} 기본 차압."

        rationale.append(Rationale(
            rule_id="rule_13_pressure",
            target_id=room.room_id,
            decision=f"DP={dp} Pa",
            input_facts={
                "clean_grade": room.clean_grade,
                "viral_segregation_offset_Pa": offset,
            },
            applied_logic=logic,
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

        # 하류 정제실 전실이면 바이러스 분리 보정 적용 (#6, 2026-06-02).
        al_offset = _airlock_viral_offset(al, token_offsets)
        if al_offset > 0:
            al_dp = al_dp + al_offset
            logic = (
                f"{logic} + 바이러스 분리 보정(+{al_offset}) — "
                f"하류 정제실 전실 차압 분리 (v2)."
            )

        new_al = dataclasses.replace(al, differential_pressure_Pa=al_dp)
        updated_als.append(new_al)

        rationale.append(Rationale(
            rule_id="rule_13_pressure",
            target_id=al.al_id,
            decision=f"DP={al_dp} Pa",
            input_facts={
                "al_grade": al.clean_grade,
                "flow_type": al.flow_type,
                "viral_segregation_offset_Pa": al_offset,
            },
            applied_logic=logic,
            source_reference="Excel: Layout 설계 원리 §13 + EU GMP Annex 1",
            flags=[],
        ))

    return updated_rooms, updated_als
