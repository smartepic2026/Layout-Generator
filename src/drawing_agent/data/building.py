"""Building dimension 해소 (D-010 — drawing_agent 가 캔버스 책임).

CLAUDE.md "코드 경계" 원칙 + D-001 의 4-tier 어댑터 패턴을 따라, "건물 캔버스
치수" 라는 도면-배치 결정을 drawing_agent 영역으로 분리. rule_engine 의 출력
(`RuleEngineOutput`) 에는 building width/depth 필드가 없고, 룰엔진은 이를 의도적
으로 spec 에 흘리지 않는다 (URS → KB → spec 단방향). 캔버스 결정은 배치 단계의
일이므로 drawing_agent 가 해소한다.

장비 치수 (W_mm/D_mm) 는 반대로 도메인 결정 (공정 장비 선정) 이므로 절대로
drawing_agent 가 override 하지 않는다 — D-010 책임 분리.

해소 우선순위 (4-tier 와 일관):
  tier1_ruleengine : spec.constraints 에 building dim 필드가 있으면 (현재 없음)
  tier2_urs        : urs_path 의 URS.building.width_mm / depth_mm
  tier3_derive     : 파생 안 함 (epistemic honesty — 추정값으로 오염 금지)
  tier4_manual_stub: default 78500×42500 mm (기존 강제 default 유지)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.rule_engine.schemas import RuleEngineOutput, URSInput


DEFAULT_BUILDING_W_MM: float = 78500.0
DEFAULT_BUILDING_H_MM: float = 42500.0


def resolve_building_dims(
    spec: RuleEngineOutput,
    urs_path: Optional[str] = None,
) -> tuple[float, float, str]:
    """spec + 옵션 URS 로부터 캔버스 (w_mm, h_mm) 와 source tag 반환.

    Returns:
        (width_mm, depth_mm, source) — source ∈ {"tier1_ruleengine",
        "tier2_urs", "tier4_manual_stub_default"}.

    tier3 (derive) 는 일부러 비워 둠. spec.rooms 의 면적 합으로 캔버스를 역산할
    수 있으나, 그것은 "추정값" 이므로 P3·P5·P8 보류 원칙과 같은 줄기로 거부.
    명시적 입력 (URS) 이 없으면 manual default 로 fallback 한다.
    """
    # tier1 — 룰엔진이 채웠을 경우 (스키마 확장 시 활성). 현재 RuleEngineOutput
    # 에는 building dim 필드 없음 → 항상 skip.
    if hasattr(spec, "building") and getattr(spec, "building", None) is not None:  # 방어
        b = getattr(spec, "building")
        w = getattr(b, "width_mm", None)
        h = getattr(b, "depth_mm", None)
        if w and h:
            return float(w), float(h), "tier1_ruleengine"

    # tier2 — URS JSON 경로가 주어지면 building.width_mm / depth_mm 사용.
    if urs_path:
        try:
            data = json.loads(Path(urs_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if data is not None:
            try:
                urs = URSInput.model_validate(data)
                return (
                    float(urs.building.width_mm),
                    float(urs.building.depth_mm),
                    "tier2_urs",
                )
            except Exception:
                # URS 파싱 실패 시 fallback 으로 내려간다 — 외부 계약 변동 흡수
                # (D-003 anti-corruption layer 원칙).
                pass

    # tier4 — manual stub default. drawing_agent 가 단독으로 캔버스 추정 안 함.
    return DEFAULT_BUILDING_W_MM, DEFAULT_BUILDING_H_MM, "tier4_manual_stub_default"
