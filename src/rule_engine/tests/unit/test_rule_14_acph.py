"""L1 unit test — rule_14_acph."""
from __future__ import annotations

import dataclasses

import pytest

from src.rule_engine.models import Rationale
from src.rule_engine.rules import rule_14_acph


@pytest.mark.parametrize(
    "grade,acph,should_flag",
    [
        ("B", 50.0, False),   # 권장 40~60 안
        ("B", 30.0, True),    # 하한 미만
        ("C", 30.0, False),   # 권장 20~40 안
        ("C", 10.0, True),    # 하한 미만
        ("D", 15.0, False),   # 권장 6~20 안
        ("D", 3.0, True),     # 하한 미만
        ("NC", 5.0, False),   # 범위 없음 → flag 없음
    ],
)
def test_acph_range_flag(minimal_rooms, empty_input, grade, acph, should_flag):
    target = dataclasses.replace(
        minimal_rooms[0], clean_grade=grade, air_changes_per_hour=acph
    )
    rationale: list[Rationale] = []

    rule_14_acph.apply([target], empty_input, rationale)

    if should_flag:
        assert any(f.severity == "suspected_violation" for f in rationale[0].flags)
    else:
        assert not rationale[0].flags


def test_recovery_time_for_b_c(minimal_rooms, empty_input):
    """Grade B/C는 recovery_time_min=15분."""
    rooms = [
        dataclasses.replace(minimal_rooms[0], clean_grade="B", air_changes_per_hour=50),
        dataclasses.replace(minimal_rooms[1], clean_grade="C", air_changes_per_hour=30),
    ]
    rationale: list[Rationale] = []

    result = rule_14_acph.apply(rooms, empty_input, rationale)

    assert result[0].recovery_time_min == 15.0
    assert result[1].recovery_time_min == 15.0


def test_recovery_none_for_d_nc(minimal_rooms, empty_input):
    """Grade D/NC는 recovery_time_min=None."""
    rooms = [
        dataclasses.replace(minimal_rooms[2], clean_grade="D", air_changes_per_hour=10),
        dataclasses.replace(minimal_rooms[3], clean_grade="NC", air_changes_per_hour=None),
    ]
    rationale: list[Rationale] = []

    result = rule_14_acph.apply(rooms, empty_input, rationale)

    assert result[0].recovery_time_min is None
    assert result[1].recovery_time_min is None


def test_urs_acph_preserved(minimal_rooms, empty_input):
    """URS ACPH 값은 수정되지 않음."""
    target = dataclasses.replace(
        minimal_rooms[1], clean_grade="C", air_changes_per_hour=25.0
    )
    rationale: list[Rationale] = []

    result = rule_14_acph.apply([target], empty_input, rationale)

    assert result[0].air_changes_per_hour == 25.0


def test_no_acph_no_flag(minimal_rooms, empty_input):
    """ACPH가 None이면 flag 없음 (passthrough)."""
    target = dataclasses.replace(
        minimal_rooms[0], clean_grade="B", air_changes_per_hour=None
    )
    rationale: list[Rationale] = []

    rule_14_acph.apply([target], empty_input, rationale)

    assert not rationale[0].flags
