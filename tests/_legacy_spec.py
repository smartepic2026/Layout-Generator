"""테스트용 기본 spec 생성 — 옛 pydantic 엔진 제거(2026-06-01 통합) 후 호환 shim.

기존 테스트들은 `run_rule_engine(URSInput(), strict=...)` 로 *기본 spec* 을 얻어
드로잉/스코어러/CP-SAT 기계장치를 검증했다. 옛 엔진은 소연 엔진(src/rule_engine,
dataclass)으로 교체됐고, 출력은 tier1 어댑터가 우리 pydantic 계약으로 변환한다.

이 shim 은 옛 시그니처를 받아(인자는 무시) **소연 엔진 + 어댑터**로 만든 기본
spec(pydantic RuleEngineOutput)을 돌려준다. 한 번 계산 후 캐시.

주의: 옛 엔진의 *특정 출력값*(방 개수/ID 등)을 단언하는 테스트는 소연 엔진
출력 기준으로 갱신이 필요하다(별도 follow-up). 이 shim 은 "valid spec 공급"
까지만 책임진다.
"""
from __future__ import annotations

import json
from functools import lru_cache

from src.contract.schemas import RuleEngineOutput

_URS_XLSX = "examples/teammate_urs_0516.xlsx"


@lru_cache(maxsize=1)
def _default_spec_json() -> str:
    from src.rule_engine import run_rule_engine as _soyeon_run
    from src.rule_engine.urs_parser import load_urs_as_input

    inp = load_urs_as_input(path=_URS_XLSX)
    return _soyeon_run(inp).to_json()


def run_rule_engine(urs=None, strict: bool = True) -> RuleEngineOutput:
    """옛 시그니처 호환 — 인자 무시, 소연 엔진 기반 기본 pydantic spec 반환."""
    from src.drawing_agent.data.tier1_ruleengine import adapt_external_dict

    her_dict = json.loads(_default_spec_json())
    return RuleEngineOutput.model_validate(adapt_external_dict(her_dict))
