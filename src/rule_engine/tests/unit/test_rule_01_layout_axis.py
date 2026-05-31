"""L1 unit test — rule_01_layout_axis.

검증 포인트:
    1. axis 벡터가 시계방향 입력에서 정확히 derive되는가
    2. material_inlet == waste_outlet 케이스에서 flag가 발생하는가
    3. rationale에 정확히 1개 항목이 append되는가
"""
from __future__ import annotations

import dataclasses

import pytest

from src.rule_engine.models import Rationale
from src.rule_engine.rules import rule_01_layout_axis


def test_axis_vector_12_to_9(empty_input):
    """12시 자재 반입, 9시 폐기물 반출 — axis = (-1, -1)."""
    rationale: list[Rationale] = []
    rule_01_layout_axis.apply(empty_input, rationale)

    assert len(rationale) == 1
    entry = rationale[0]
    assert entry.rule_id == "rule_01_layout_axis"
    assert "axis_vector=(-1, -1)" in entry.decision
    assert entry.input_facts["material_vector"] == (0, 1)
    assert entry.input_facts["waste_vector"] == (-1, 0)
    assert not entry.flags  # 정상 케이스: flag 없음


@pytest.mark.parametrize(
    "material,waste,expected_dx,expected_dy",
    [
        ("12", "9", -1, -1),  # 북 → 서
        ("12", "6", 0, -2),   # 북 → 남 (반대)
        ("3", "9", -2, 0),    # 동 → 서 (반대)
        ("12", "3", 1, -1),   # 북 → 동
    ],
)
def test_axis_parametrize(empty_input, material, waste, expected_dx, expected_dy):
    """여러 방향 조합에 대해 axis 벡터 검증."""
    # building을 수정하기 위해 dataclasses.replace.
    building = dataclasses.replace(
        empty_input.building, material_inlet=material, waste_outlet=waste
    )
    inp = dataclasses.replace(empty_input, building=building)
    rationale: list[Rationale] = []

    rule_01_layout_axis.apply(inp, rationale)

    assert rationale[0].decision == f"axis_vector=({expected_dx}, {expected_dy})"


def test_flag_when_material_equals_waste(empty_input):
    """material_inlet과 waste_outlet이 같은 시간이면 suspected_violation flag."""
    building = dataclasses.replace(
        empty_input.building, material_inlet="12", waste_outlet="12"
    )
    inp = dataclasses.replace(empty_input, building=building)
    rationale: list[Rationale] = []

    rule_01_layout_axis.apply(inp, rationale)

    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "suspected_violation"
    assert "동선 분리 불가" in flags[0].note
