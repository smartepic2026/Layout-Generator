"""3-tier data adapter — drawing_agent 가 필요한 값을 출처별로 순차 조회.

CLAUDE.md 원칙:
- rule_engine/ 와 GMP Layout Logic 0510.xlsx 는 절대 수정 금지 (팀원 원천)
- drawing_agent 가 보충해야 하는 값은 examples/ 시나리오 JSON 이나
  drawing_agent/kb/ 에만 채운다
- 각 enrich 된 필드는 source 태그로 출처를 명시 (재현가능성·논문·특허)

어댑터 우선순위 (높은 → 낮은):
  tier1_ruleengine : RuleEngineOutput 에 이미 있는 값
  tier2_urs        : examples/urs_*.json 시나리오 JSON
  tier3_derive     : 기존 필드에서 파생 (예: process_step → sort_order)
  tier4_manual_stub: drawing_agent/kb/ 의 수기 보충 (마지막 수단)

팀원이 나중에 rule_engine 에 열을 추가하면 tier1 이 자동 우선 적용 →
drawing_agent 코드는 손대지 않아도 됨.
"""
from src.drawing_agent.data.adapter import (
    SourceTracker,
    enrich_spec,
)

__all__ = ["enrich_spec", "SourceTracker"]
