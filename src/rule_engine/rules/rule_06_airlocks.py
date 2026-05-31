"""룰 6 — 전실 배열 (URS Room → AirLock 객체 변환).

한 줄 요약:
    URS Room 시트의 AL 명을 AirLock 객체로 변환한다. AirLock의 kind는
    "PAL|MAL|CAL" 표기 + in/out 표기를 정규식으로 추출해 결정한다.

왜 필요한가:
    Excel "Layout 설계 원리 §7". 청정등급이 바뀌거나 공정 중요도 구분이 필요한
    두 Room 사이에 전실이 들어간다. URS의 AL Room이 그 자체로 청정도·gowning을
    명시하므로 룰 6은 단순 변환자다.

kind 추론 (정규식):
    "PAL-in Cell Culture" → PAL_in (대상: Cell Culture)
    "MAL-out Harvest"     → MAL_out (대상: Harvest)
    "CAL Inoculation"     → CAL

무엇을 안 하는가:
    flow_type 결정은 룰 7. 차압 계산은 룰 13. 인접 Room 매칭은 derive/adjacency.
"""
from __future__ import annotations

import re

from ..models import AirLock, ALKind, Flag, Rationale, Room, RuleEngineInput


# AL 토큰을 찾는 정규식: PAL/MAL/CAL + optional in/out.
# 단어 경계로 'Inoculation' 같은 단어 안의 'in' 매치 방지.
_AL_PATTERN = re.compile(
    r"\b(PAL|MAL|CAL)\b[-_ ]?(in|out)?\b",
    re.IGNORECASE,
)


def _detect_kind(name_en: str) -> tuple[ALKind | None, str]:
    """영문명에서 AL kind와 대상 Room 명 추출."""
    m = _AL_PATTERN.search(name_en)
    if not m:
        return None, name_en.strip()

    al_type = m.group(1).upper()
    direction = m.group(2)
    if direction:
        kind: ALKind = f"{al_type}_{direction.lower()}"  # type: ignore[assignment]
    else:
        kind = al_type  # type: ignore[assignment]

    # 대상 Room 추출 (AL 토큰과 괄호 제거).
    cleaned = _AL_PATTERN.sub("", name_en)
    cleaned = re.sub(r"[\(\)]", "", cleaned).strip()
    return kind, cleaned


def _is_airlock(room: Room) -> bool:
    """Room이 AL인지 판정."""
    return _AL_PATTERN.search(room.name_en) is not None


def apply(
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[AirLock]:
    """URS AL Room → AirLock 객체 리스트."""
    airlocks: list[AirLock] = []

    for room in rooms:
        if not _is_airlock(room):
            continue
        flags: list[Flag] = []
        kind, target = _detect_kind(room.name_en)
        if kind is None:
            flags.append(Flag(
                rule_id="rule_06_airlocks",
                severity="warning",
                note=f"AL kind 추론 실패: {room.name_en!r} — CAL fallback",
            ))
            kind = "CAL"

        if "PAL" in kind:
            purpose = "personnel"
        elif "MAL" in kind:
            purpose = "material"
        else:
            purpose = "common"

        airlocks.append(AirLock(
            al_id=room.room_id.replace("R_", "AL_"),
            kind=kind,
            clean_grade=room.clean_grade,
            area_m2=room.area_m2,
            flow_type="cascade",  # 룰 7에서 재결정
            connects_higher_room=None,
            connects_lower_room=None,
            purpose=purpose,
            differential_pressure_Pa=None,
        ))

        rationale.append(Rationale(
            rule_id="rule_06_airlocks",
            target_id=room.room_id,
            decision=f"kind={kind}, purpose={purpose}, target={target!r}",
            input_facts={
                "al_room_name_en": room.name_en,
                "al_room_grade": room.clean_grade,
            },
            applied_logic="PAL|MAL|CAL + in/out 정규식 매칭으로 kind 추론.",
            source_reference="Excel: Layout 설계 원리 §7 (전실 배열)",
            flags=flags,
        ))
    return airlocks
