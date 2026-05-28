"""Drawing Agent v1 entrypoint.

usage:
    from src.drawing_agent.floorplan import generate_floorplan
    svg, layout = generate_floorplan(spec, building_w_mm=78500, building_h_mm=42500)

파이프라인:
    1. data adapter (4-tier) 로 spec enrich  ← Phase A1
    2. layout solver (현재 strip-band; Phase C 에서 CP-SAT 으로 교체)
    3. renderer
"""
from __future__ import annotations

from typing import Optional

from src.drawing_agent.data import SourceTracker, enrich_spec
from src.drawing_agent.layout_solver import Layout, solve
from src.drawing_agent.renderer import render
from src.rule_engine.schemas import RuleEngineOutput


def generate_floorplan(
    spec: RuleEngineOutput,
    building_w_mm: float = 78500,
    building_h_mm: float = 42500,
    urs_path: Optional[str] = None,
    return_tracker: bool = False,
):
    """spec → (svg_text, layout[, tracker]).

    Phase A1 추가: 솔버 호출 전에 4-tier 어댑터로 spec.equipment 의
    sort_order/bbox_m/connects_to 를 in-place enrich. tier1 이 우선이라
    rule_engine 이 향후 같은 필드를 채우기 시작하면 자동 채택.

    return_tracker=True 면 SourceTracker 도 함께 반환 (감사/로깅용).
    """
    tracker = enrich_spec(spec, urs_path=urs_path)
    layout = solve(spec, building_w_mm=building_w_mm, building_h_mm=building_h_mm)
    svg = render(spec, layout)
    if return_tracker:
        return svg, layout, tracker
    return svg, layout
