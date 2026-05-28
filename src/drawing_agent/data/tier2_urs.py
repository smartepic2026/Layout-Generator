"""Tier 2 — examples/urs_*.json 시나리오 JSON 의 보충값 사용.

source 태그: "tier2_urs"

현재 (Phase A1) URS 스키마(URSInput)는 product/building/flow_policy/
organization/overrides 의 정책 레벨만 담음. 장비 단위 (process_step,
sort_order 등) 데이터는 URS 가 표현할 차원이 아님 → tier2 는 실질적으로
빈 stub.

향후 URS 에 시나리오별 장비 override (예: 특정 장비를 추가/교체) 같은
필드가 들어오면 이 파일을 확장. 그 시점에 tier1 보다 우선순위가 낮으니
rule_engine 출력이 같은 필드를 가졌으면 자동으로 그쪽이 채택됨.
"""
from __future__ import annotations

from src.rule_engine.schemas import RuleEngineOutput

TIER_NAME = "tier2_urs"


def try_fill(
    spec: RuleEngineOutput,
    tracker,
    field_name: str,
    urs_path: str,
) -> None:
    """현재는 stub. URS 가 장비-level override 를 표현할 수 있게 되면 구현.

    구조만 만들어둠 — 인터페이스는 tier1/3/4 와 동일.
    """
    return  # no-op (이번 phase 에선 시나리오 JSON 에 보충 데이터 없음)
