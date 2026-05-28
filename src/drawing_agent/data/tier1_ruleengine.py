"""Tier 1 — RuleEngineOutput 에 이미 있는 값 우선 사용.

source 태그: "tier1_ruleengine"

현재 (2026-05-29) rule_engine 출력의 Equipment 는 다음 필드를 가짐 (의미있는 값):
  name, W_mm, D_mm, H_mm, weight_kg, max_op_weight_kg, process_step,
  footprint_m2

다음 필드는 스키마 상 존재하지만 rule_engine 이 아직 채우지 않음 (None / 빈 리스트):
  sort_order, bbox_m, grade, rotatable, clearance_m, utilities,
  connects_to, incompatible_with, open_closed, contamination_class,
  needs, heat_kw, noise_dba, flammable

→ tier1 은 위 미채움 필드에 대해 항상 "skip" 한다.
   팀원이 향후 rule_engine 에서 sort_order 등을 채우기 시작하면 tier1 이
   자동 우선 적용 (이 파일 코드는 손댈 필요 없음).
"""
from __future__ import annotations

from src.rule_engine.schemas import RuleEngineOutput

TIER_NAME = "tier1_ruleengine"


def try_fill(spec: RuleEngineOutput, tracker, field_name: str) -> None:
    """이미 값이 있는 장비에만 source 태그 기록. 값 변경은 없음.

    구조: rule_engine 이 미래에 채워주면 그 값을 보존하면서 출처만 기록.
    이 함수는 값을 새로 채우지 않는다 (tier1 은 단순 confirm + tag).
    """
    from src.drawing_agent.data.adapter import is_field_filled

    for room in spec.rooms:
        for idx, eq in enumerate(room.equipment):
            if is_field_filled(eq, field_name):
                # 이미 있는 값 → 출처는 rule_engine.
                # 중복 호출(idempotent)이라 기존 태그 덮어쓰지 않음.
                if tracker.get(room.id, idx, field_name) is None:
                    tracker.record(room.id, idx, field_name, TIER_NAME)
