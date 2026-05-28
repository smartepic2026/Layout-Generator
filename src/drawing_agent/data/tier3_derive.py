"""Tier 3 — 기존 필드에서 derive 규칙으로 파생.

source 태그: "tier3_derive"

Phase A1 처리 필드:
  - sort_order   ← process_step ("P1-2" → 12) 정규식 파싱
  - bbox_m       ← (W_mm, D_mm) → [w_m, d_m]
  - connects_to  ← **same-room chain 만**. 같은 방 안에서 sort_order 가
                   다음인 장비를 후속 공정으로 가정. cross-room (방 경계
                   넘는 link) 은 Phase B 에서 P2 수식 만들 때 검증하며 채움
                   (CLAUDE.md "검수자 없는 추론값은 신중히").
"""
from __future__ import annotations

import re
from typing import Optional

from src.rule_engine.schemas import RuleEngineOutput

TIER_NAME = "tier3_derive"


# process_step 포맷: "P{phase}-{seq}" → sort_order = phase * 10 + seq
_STEP_RE = re.compile(r"P?(\d+)[\-_\.](\d+)")
_FALLBACK_INT = re.compile(r"\d+")


def parse_sort_order(process_step: Optional[str]) -> Optional[int]:
    """'P1-2' → 12, 'P10-3' → 103, 'USP-30' → 30, None/'' → None.

    phase * 10 + seq 가정. 현재 데이터 (P1~P7, 각 phase 5개 이하) 에 안전.
    한 phase 에 10개 이상 장비가 들어오면 sort_order 충돌 발생 가능 →
    그땐 phase * 100 + seq 로 폭 확장.
    """
    if not process_step:
        return None
    m = _STEP_RE.match(process_step)
    if m:
        phase, seq = int(m.group(1)), int(m.group(2))
        return phase * 10 + seq
    m2 = _FALLBACK_INT.search(process_step)
    return int(m2.group()) if m2 else None


def derive_bbox_m(w_mm: int, d_mm: int) -> list[float]:
    """W_mm/D_mm → [width_m, depth_m]. mm → m 환산."""
    return [round(w_mm / 1000.0, 3), round(d_mm / 1000.0, 3)]


def try_fill(spec: RuleEngineOutput, tracker, field_name: str) -> None:
    """tier1/2 가 못 채운 필드를 derive."""
    from src.drawing_agent.data.adapter import is_field_filled

    if field_name == "sort_order":
        _fill_sort_order(spec, tracker)
    elif field_name == "bbox_m":
        _fill_bbox_m(spec, tracker)
    elif field_name == "connects_to":
        _fill_connects_to_same_room(spec, tracker)
    # 그 외 필드는 tier3 가 다루지 않음 → tier4 로 위임


def _fill_sort_order(spec: RuleEngineOutput, tracker) -> None:
    from src.drawing_agent.data.adapter import is_field_filled
    for room in spec.rooms:
        for idx, eq in enumerate(room.equipment):
            if is_field_filled(eq, "sort_order"):
                continue  # tier1 이 이미 채움
            so = parse_sort_order(eq.process_step)
            if so is not None:
                eq.sort_order = so
                tracker.record(room.id, idx, "sort_order", TIER_NAME)


def _fill_bbox_m(spec: RuleEngineOutput, tracker) -> None:
    from src.drawing_agent.data.adapter import is_field_filled
    for room in spec.rooms:
        for idx, eq in enumerate(room.equipment):
            if is_field_filled(eq, "bbox_m"):
                continue
            eq.bbox_m = derive_bbox_m(eq.W_mm, eq.D_mm)
            tracker.record(room.id, idx, "bbox_m", TIER_NAME)


def _fill_connects_to_same_room(spec: RuleEngineOutput, tracker) -> None:
    """같은 방 내 sort_order 인접 chain. cross-room 은 의도적으로 안 함.

    전제: sort_order 가 이미 채워져 있어야 함 (호출 순서상 OK — fields
    리스트의 sort_order 가 connects_to 보다 앞).
    """
    from src.drawing_agent.data.adapter import is_field_filled
    for room in spec.rooms:
        sorted_eq_with_idx = sorted(
            [(idx, eq) for idx, eq in enumerate(room.equipment) if eq.sort_order is not None],
            key=lambda t: t[1].sort_order,
        )
        for k in range(len(sorted_eq_with_idx) - 1):
            idx, eq = sorted_eq_with_idx[k]
            _, next_eq = sorted_eq_with_idx[k + 1]
            if is_field_filled(eq, "connects_to"):
                continue
            eq.connects_to.append(next_eq.name)
            tracker.record(room.id, idx, "connects_to", TIER_NAME)
