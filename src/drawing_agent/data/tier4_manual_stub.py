"""Tier 4 — drawing_agent/kb/ 의 수기 보충 파일.

source 태그: "tier4_manual_stub" (CLAUDE.md 명시: manual_stub 출처 필수)

Phase A1 에서는 빈 stub. 사용 시작 시점:
  - Phase B (P2 수식 만들 때): cross-room connects_to 를 검증하며 수기 채움
    → drawing_agent/kb/cross_room_links.json 같은 형태로 저장하고 여기서 로드
  - 2차 작업 (검수자 확보 후): open_closed, contamination_class 등

원칙 (CLAUDE.md):
  - rule_engine/ 와 0510.xlsx 는 절대 수정 금지
  - 검수자 없는 추론값은 confidence 태깅 + null 가드 (P3·P5·P8 보류 원칙)
  - manual_stub 으로 채운 값은 반드시 source 태그가 "tier4_manual_stub"
    이어야 함. 후속 audit/검수 시 분리 가능해야 함
"""
from __future__ import annotations

from pathlib import Path

from src.contract.schemas import RuleEngineOutput

TIER_NAME = "tier4_manual_stub"
KB_DIR = Path("src/drawing_agent/kb")


def try_fill(spec: RuleEngineOutput, tracker, field_name: str) -> None:
    """현재는 stub. Phase B 에서 cross_room_links.json 로드 추가 예정."""
    return  # no-op
