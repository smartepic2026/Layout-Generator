"""Drawing Agent v1 smoke tests."""
from __future__ import annotations

import re

from src.drawing_agent.floorplan import generate_floorplan
from src.rule_engine.engine import run_rule_engine
from src.rule_engine.schemas import URSInput


def test_floorplan_generation_smoke():
    spec = run_rule_engine(URSInput(), strict=True)
    svg, layout = generate_floorplan(spec)

    # SVG가 정상 형식인지
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")

    # 모든 Room이 layout에 배치됨
    assert len(layout.rooms) == len(spec.rooms)
    # AL도 배치
    assert len(layout.airlocks) == len(spec.airlocks)
    # 도어가 생성
    assert len(layout.doors) > 30


def test_svg_contains_grade_colors():
    spec = run_rule_engine(URSInput(), strict=True)
    svg, _ = generate_floorplan(spec)
    # DESIGN.md 팔레트의 핵심 색이 SVG에 등장
    assert "#FCD34D" in svg  # Grade C amber-300
    assert "#93C5FD" in svg  # Grade D blue-300


def test_svg_contains_room_labels():
    spec = run_rule_engine(URSInput(), strict=True)
    svg, _ = generate_floorplan(spec)
    # 주요 Room 영문명이 모두 등장
    for n in ["Media preparation", "Cell Culture", "Purification 1", "Purification 2", "Supply corridor"]:
        assert n in svg, f"missing label: {n}"


def test_svg_contains_legend_and_titleblock():
    spec = run_rule_engine(URSInput(), strict=True)
    svg, _ = generate_floorplan(spec)
    assert "LEGEND" in svg
    assert "PROJECT" in svg
    assert "MODALITY" in svg


def test_no_room_overflow_after_clip():
    """clipPath가 정의되어 있는지 확인."""
    spec = run_rule_engine(URSInput(), strict=True)
    svg, _ = generate_floorplan(spec)
    # 각 Room id마다 clipPath가 있어야 함
    clips = re.findall(r'clipPath id="clip_(R_[A-Z_0-9]+)"', svg)
    assert len(clips) == len(spec.rooms)
