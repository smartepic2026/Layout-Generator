"""Tier 1 — RuleEngineOutput (팀원 출력) 우선 사용 + 외부 계약 → 내부 모델 변환.

source 태그: "tier1_ruleengine"

이 모듈은 두 책임을 가진다:

1. **Anti-corruption layer** (D-003) — 팀원의 외부 JSON 계약을 우리 내부
   Pydantic 모델 (`RuleEngineOutput`) 형태로 변환. 팀원의 필드명이 또
   바뀌어도 이 한 파일만 고치면 됨. 진단 결과 (RuleEngine_Output_for_
   DocAgent.md 와 schemas.py 의 36건 mismatch) 를 일괄 흡수.

2. **try_fill()** — adapter 가 호출하는 tier1 hook. rule_engine 이
   sort_order 등 미래 필드를 채우기 시작하면 자동 우선 적용.

변환 규칙은 진단 시점(2026-05-29)의 팀원 출력 마크다운 기반. 팀원 JSON
실물이 들어오면 일부 매핑이 빗나갈 수 있고 그땐 이 파일만 고친다.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from src.rule_engine.schemas import RuleEngineOutput

TIER_NAME = "tier1_ruleengine"


# ══════════════════════════════════════════════════════════════════════
# Anti-corruption layer — 외부 계약 → 내부 모델 변환
# ══════════════════════════════════════════════════════════════════════

# Room 필드명 매핑 (팀원 출력 키 → 내 schemas.py 필드명).
# 마크다운 §1 의 컬럼 라벨을 JSON 키로 추정해 매핑. 실제 JSON 키가
# 다르면 이 매핑만 고치면 됨.
ROOM_KEY_MAP = {
    "room_id": "id",
    "cat": "category",
    "grade": "clean_grade",
    "DP": "differential_pressure_Pa",
    "ACPH": "air_changes_per_hour",
    "color": "background_color",
    "투명%": "transparency_pct",
    "투명도": "transparency_pct",
    "transparency": "transparency_pct",
}

# Airlock 필드명 매핑 (§2)
AL_KEY_MAP = {
    "al_id": "id",
    "kind": "type",
    "grade": "clean_grade",
    "DP": "differential_pressure_Pa",
    # higher_room / lower_room / area_m2 는 required 인데 팀원 출력에
    # "—" (null) 인 상태. 이번 fix 에선 매핑만, Optional 화는 팀원 확인 후.
}

# Adjacency 필드명 매핑 (§3)
ADJ_KEY_MAP = {
    "doors": "door_count",
    "door_size": "door_size_mm",
    # `swing` 은 의미가 다름 (Room id vs 방향 descriptor) — 그대로 받으면
    # 의미 오염. 팀원 확인 전엔 swing → notes 로 보존.
}

# Rationale 필드명 매핑 (§7)
RAT_KEY_MAP = {
    "target_id": "target",
}

# 이름 끝 trailing space 가 발견된 필드들 (마크다운 §1·§3·§7 에서 관찰).
# 변환 레이어에서만 strip — 원본 파일은 무수정.
NAME_FIELDS_TO_STRIP = ("id", "name_ko", "name_en", "name")


def _strip_keys(d: dict, mapping: dict) -> dict:
    """주어진 매핑대로 dict 의 키를 변경. 매핑에 없는 키는 그대로 둠
    (extra='ignore' 라 모르는 키는 어차피 무시됨)."""
    out = {}
    for k, v in d.items():
        new_key = mapping.get(k, k)
        # 같은 내부 키로 매핑된 두 외부 키가 충돌하면 (예: grade + clean_grade
        # 동시 존재) 매핑된 쪽 우선
        if new_key in out and new_key != k:
            continue
        out[new_key] = v
    return out


def _strip_name(s: Any) -> Any:
    """문자열이면 trailing/leading space 제거. 그 외는 그대로."""
    return s.strip() if isinstance(s, str) else s


_DIM_NUM_RE = re.compile(r"(\d[\d,]*)")
_DIM_SPLIT_RE = re.compile(r"[×xX\*]")


def parse_dimensions(s: Any) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """\"3500×3000×3000\" → (3500, 3000, 3000). 콤마 (\"2,000\") 도 처리.

    실패 시 (None, None, None). 값이 1~2개면 누락분 None.
    """
    if not isinstance(s, str):
        return (None, None, None)
    parts = [p for p in _DIM_SPLIT_RE.split(s) if p.strip()]
    nums: list[Optional[int]] = []
    for p in parts[:3]:
        m = _DIM_NUM_RE.search(p)
        if m:
            nums.append(int(m.group(1).replace(",", "")))
        else:
            nums.append(None)
    while len(nums) < 3:
        nums.append(None)
    return (nums[0], nums[1], nums[2])


def _adapt_equipment(eq: dict) -> dict:
    """Equipment dict 정규화: 합쳐진 W×D×H 문자열 파싱 + 이름 strip + 키 매핑."""
    eq = dict(eq)  # shallow copy

    # 1) 합쳐진 dimension 문자열 → W_mm/D_mm/H_mm. 가능한 키 모두 시도.
    for combined_key in ("W×D×H(mm)", "WxDxH(mm)", "WxDxH_mm", "dimensions",
                         "dim", "size", "WDH"):
        if combined_key in eq and not all(k in eq for k in ("W_mm", "D_mm", "H_mm")):
            w, d, h = parse_dimensions(eq[combined_key])
            if w is not None:
                eq.setdefault("W_mm", w)
            if d is not None:
                eq.setdefault("D_mm", d)
            if h is not None:
                eq.setdefault("H_mm", h)
            break

    # 2) weight / max_op 키 매핑 (마크다운 §1.1)
    if "weight" in eq and "weight_kg" not in eq:
        eq["weight_kg"] = eq["weight"]
    if "max_op" in eq and "max_op_weight_kg" not in eq:
        eq["max_op_weight_kg"] = eq["max_op"]

    # D-005: process_no 가 정식 필드명 (팀원 정식 계약). 별도 alias 변환 불필요.
    #   - schemas.Equipment.process_no 가 validation_alias 로 "process_step" 도 받음 → 구 JSON 호환은 schema 가 처리.
    #   - A1.5 에서 깔았던 process_no → process_step alias 는 D-005 에서 제거됨.

    # name trailing space strip
    if "name" in eq:
        eq["name"] = _strip_name(eq["name"])

    return eq


def _adapt_room(room: dict) -> dict:
    """Room dict 정규화."""
    room = _strip_keys(room, ROOM_KEY_MAP)

    # 이름 strip
    for k in NAME_FIELDS_TO_STRIP:
        if k in room:
            room[k] = _strip_name(room[k])

    # gowning (단일 문자열) → gowning_type (gowning_method 는 None 유지)
    if "gowning" in room and "gowning_type" not in room:
        room["gowning_type"] = _strip_name(room["gowning"])

    # equipment 도 재귀 정규화
    if "equipment" in room and isinstance(room["equipment"], list):
        room["equipment"] = [_adapt_equipment(eq) for eq in room["equipment"]]

    return room


def _adapt_airlock(al: dict) -> dict:
    """Airlock dict 정규화."""
    al = _strip_keys(al, AL_KEY_MAP)
    for k in NAME_FIELDS_TO_STRIP:
        if k in al:
            al[k] = _strip_name(al[k])
    return al


def _adapt_adjacency(adj: dict) -> dict:
    """Adjacency dict 정규화. swing 의 의미 차이는 notes 로 옮겨 보존."""
    adj = _strip_keys(adj, ADJ_KEY_MAP)
    # swing 값이 "high_pressure_side" / "low_pressure_side" 같은 descriptor 면
    # door_swing_to (Room id 기대) 와 의미가 다름 → notes 에 보존, door_swing_to 는 None.
    if "swing" in adj:
        sw = adj.pop("swing")
        if sw and sw != "—":
            existing = adj.get("notes", "")
            adj["notes"] = (existing + f" swing={sw}" if existing else f"swing={sw}").strip()

    for k in NAME_FIELDS_TO_STRIP:
        if k in adj:
            adj[k] = _strip_name(adj[k])
    return adj


def _adapt_rationale(rat: dict) -> dict:
    """Rationale dict 정규화. severity/note → decision/reason 합성."""
    rat = _strip_keys(rat, RAT_KEY_MAP)
    # severity + note → decision + reason 매핑.
    # 정보 손실 없이 보존: severity 는 decision 의 head, note 가 reason.
    sev = rat.pop("severity", None)
    note = rat.pop("note", None)
    if sev and "decision" not in rat:
        rat["decision"] = f"[{sev}]"
    if note and "reason" not in rat:
        rat["reason"] = note
    # 필수 필드 fallback (Rationale.decision/reason 은 required str)
    rat.setdefault("decision", "")
    rat.setdefault("reason", "")
    return rat


def adapt_external_dict(data: dict) -> dict:
    """팀원 출력 dict 를 내부 모델이 받을 수 있는 형태로 정규화. 비파괴.

    적용 순서: rooms → airlocks → adjacency → rationale.
    meta / 그 외 모르는 최상위 키는 extra='ignore' 가 알아서 흡수.
    """
    data = dict(data)
    if "rooms" in data and isinstance(data["rooms"], list):
        data["rooms"] = [_adapt_room(r) for r in data["rooms"]]
    if "airlocks" in data and isinstance(data["airlocks"], list):
        data["airlocks"] = [_adapt_airlock(a) for a in data["airlocks"]]
    if "adjacency" in data and isinstance(data["adjacency"], list):
        data["adjacency"] = [_adapt_adjacency(a) for a in data["adjacency"]]
    if "rationale" in data and isinstance(data["rationale"], list):
        data["rationale"] = [_adapt_rationale(r) for r in data["rationale"]]
    return data


def load_external_spec(json_str: str) -> RuleEngineOutput:
    """팀원 출력 JSON 문자열 → 정규화 → RuleEngineOutput.

    실패 케이스 (Airlock required 필드 NULL 등) 는 이번 phase 에서 처리 안 함
    (팀원 확인 대기). 일단 변환 레이어 통과만 보장.
    """
    data = json.loads(json_str)
    data = adapt_external_dict(data)
    return RuleEngineOutput.model_validate(data)


# ══════════════════════════════════════════════════════════════════════
# adapter hook (기존 책임)
# ══════════════════════════════════════════════════════════════════════
def try_fill(spec: RuleEngineOutput, tracker, field_name: str) -> None:
    """이미 값이 있는 장비에만 source 태그 기록. 값 변경은 없음.

    rule_engine 이 미래에 sort_order 등을 채워주면 그 값을 보존하면서
    출처만 기록. 이 함수는 값을 새로 채우지 않는다.
    """
    from src.drawing_agent.data.adapter import is_field_filled

    for room in spec.rooms:
        for idx, eq in enumerate(room.equipment):
            if is_field_filled(eq, field_name):
                if tracker.get(room.id, idx, field_name) is None:
                    tracker.record(room.id, idx, field_name, TIER_NAME)
