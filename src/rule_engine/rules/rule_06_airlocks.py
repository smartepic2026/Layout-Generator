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

area_m2 산출 (Doc Agent #1, 2026-06-02; kind별 차등 2026-06-02 결정):
    전실 면적은 URS Room 시트에 입력되지 않아 None 이었다. KB 권장 전실
    footprint 를 기본값으로 부여하되, 전실 종류에 따라 차등한다:
      - PAL(인원)·CAL(공용): 3.0m × 3.0m = 9.0 m²
        (constraints.airlock_size_mm.preferred = 3000×3000).
      - MAL(자재): 3.0m × 4.0m = 12.0 m² — 자재 도어(1500mm)·카트/대형물 통과를
        위해 더 큰 footprint 권장.
    URS Room 에 면적이 별도 derive 되어 있으면(현재는 없음) 그 값을 우선한다.

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

# KB 권장 전실 footprint 기본 면적 (m²) — kind별 차등 (#1, 2026-06-02 결정).
# PAL/CAL: preferred 3000×3000 = 9.0 m² (engine._bundle_constraints 와 동기화).
# MAL(자재): 자재 도어·카트 통과 위해 3000×4000 = 12.0 m².
_PREFERRED_AIRLOCK_AREA_M2 = 9.0          # PAL / CAL
_MATERIAL_AIRLOCK_AREA_M2 = 12.0          # MAL


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


def _default_area_for_purpose(purpose: str) -> float:
    """전실 purpose 에 따른 KB 권장 기본 면적 (m²)."""
    return (
        _MATERIAL_AIRLOCK_AREA_M2 if purpose == "material"
        else _PREFERRED_AIRLOCK_AREA_M2
    )


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

        # 전실 면적: URS Room 에 derive 된 값이 있으면 우선, 없으면 kind별 KB
        # 권장 footprint (MAL 12.0 / PAL·CAL 9.0) (Doc Agent #1).
        area_m2 = (
            room.area_m2 if room.area_m2 is not None
            else _default_area_for_purpose(purpose)
        )

        airlocks.append(AirLock(
            al_id=room.room_id.replace("R_", "AL_"),
            kind=kind,
            clean_grade=room.clean_grade,
            area_m2=area_m2,
            flow_type="cascade",  # 룰 7에서 재결정
            connects_higher_room=None,
            connects_lower_room=None,
            purpose=purpose,
            differential_pressure_Pa=None,
        ))

        rationale.append(Rationale(
            rule_id="rule_06_airlocks",
            target_id=room.room_id,
            decision=(
                f"kind={kind}, purpose={purpose}, area={area_m2} m², "
                f"target={target!r}"
            ),
            input_facts={
                "al_room_name_en": room.name_en,
                "al_room_grade": room.clean_grade,
                "area_source": (
                    "urs_room_area" if room.area_m2 is not None
                    else (
                        "kb_material_footprint_12m2" if purpose == "material"
                        else "kb_preferred_footprint_9m2"
                    )
                ),
            },
            applied_logic=(
                "PAL|MAL|CAL + in/out 정규식 매칭으로 kind 추론. 면적은 URS "
                "derive 값 우선, 없으면 kind별 KB footprint (MAL 12.0 / 그 외 9.0)."
            ),
            source_reference="Excel: Layout 설계 원리 §7 (전실 배열)",
            flags=flags,
        ))
    return airlocks
