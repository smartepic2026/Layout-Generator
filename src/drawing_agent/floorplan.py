"""Drawing Agent v1 entrypoint.

usage:
    from src.drawing_agent.floorplan import generate_floorplan
    # 명시 dim
    svg, layout = generate_floorplan(spec, building_w_mm=78500, building_h_mm=42500)
    # URS 의 building.width_mm / depth_mm 자동 적용 (D-010)
    svg, layout = generate_floorplan(spec, urs_path="examples/urs_mab_8000L.json")

파이프라인:
    1. data adapter (4-tier) 로 spec enrich  ← Phase A1
    2. building dim 해소 (4-tier, D-010)     ← Phase B1.5
    3. layout solver (현재 strip-band; Phase C 에서 CP-SAT 으로 교체)
    4. renderer
"""
from __future__ import annotations

from typing import Optional

from src.drawing_agent.data import (
    SourceTracker,
    enrich_spec,
    resolve_building_dims,
)
from src.drawing_agent.layout_solver import Layout, solve
from src.drawing_agent.renderer import render
from src.contract.schemas import RuleEngineOutput


def generate_floorplan(
    spec: RuleEngineOutput,
    building_w_mm: Optional[float] = None,
    building_h_mm: Optional[float] = None,
    urs_path: Optional[str] = None,
    return_tracker: bool = False,
    dynamic_rooms: bool = False,
    auto_canvas: bool = False,
    flow_mode: str = "full",
):
    """spec → (svg_text, layout[, tracker]).

    Phase A1: 솔버 호출 전에 4-tier 어댑터로 spec.equipment 의 sort_order/bbox_m/
    connects_to 를 in-place enrich. tier1 이 우선이라 rule_engine 이 향후 같은
    필드를 채우기 시작하면 자동 채택.

    [D-010] building_w_mm / building_h_mm 이 None 이면 `resolve_building_dims`
    (data/building.py) 가 4-tier (URS → 룰엔진 → manual default) 로 해소.
    명시값이 주어지면 그대로 사용 (CLI / 테스트 호환).

    return_tracker=True 면 SourceTracker 도 함께 반환 (감사/로깅용).
    """
    tracker = enrich_spec(spec, urs_path=urs_path)
    if building_w_mm is None or building_h_mm is None:
        w_resolved, h_resolved, _ = resolve_building_dims(spec, urs_path=urs_path)
        if building_w_mm is None:
            building_w_mm = w_resolved
        if building_h_mm is None:
            building_h_mm = h_resolved
    layout = solve(
        spec,
        building_w_mm=building_w_mm,
        building_h_mm=building_h_mm,
        dynamic_rooms=dynamic_rooms,
        auto_canvas=auto_canvas,
    )
    svg = render(spec, layout, flow_mode=flow_mode)
    if return_tracker:
        return svg, layout, tracker
    return svg, layout
