"""Drawing Agent v1 entrypoint.

usage:
    from src.drawing_agent.floorplan import generate_floorplan
    svg = generate_floorplan(spec, building_w_mm=78500, building_h_mm=42500)
"""
from __future__ import annotations

from src.drawing_agent.layout_solver import Layout, solve
from src.drawing_agent.renderer import render
from src.rule_engine.schemas import RuleEngineOutput


def generate_floorplan(
    spec: RuleEngineOutput,
    building_w_mm: float = 78500,
    building_h_mm: float = 42500,
) -> tuple[str, Layout]:
    """spec → (svg_text, layout). layout은 RL/Reward에서 사용 가능."""
    layout = solve(spec, building_w_mm=building_w_mm, building_h_mm=building_h_mm)
    svg = render(spec, layout)
    return svg, layout
