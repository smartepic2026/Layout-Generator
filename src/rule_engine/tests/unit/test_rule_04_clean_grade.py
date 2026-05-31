"""L1 unit test — rule_04_clean_grade.

검증 포인트:
    1. 등급별 색상이 Excel §5 매핑대로 정확한가
    2. transparency_pct = 50 부착
    3. closed_system=False + 주공정 Grade D 케이스에서 flag 발생
    4. URS gowning_type 값은 보존(수정되지 않음)
    5. rationale 항목이 Room 수만큼 append
"""
from __future__ import annotations

import dataclasses

import pytest

from src.rule_engine.models import Rationale
from src.rule_engine.rules import rule_04_clean_grade


@pytest.mark.parametrize(
    "grade,expected_color",
    [
        ("A", "Green-diagonal-black"),
        ("B", "Green"),
        ("C", "yellow"),
        ("D", "Blue"),
        ("CNC", "Gray-dotted-black"),
        ("NC", "Gray"),
    ],
)
def test_color_mapping(minimal_rooms, empty_input, grade, expected_color):
    """6개 등급 각각이 정확한 색상으로 매핑되는가."""
    # 첫 번째 Room의 grade만 바꿔서 단일 케이스 검증.
    target = dataclasses.replace(minimal_rooms[0], clean_grade=grade)
    rationale: list[Rationale] = []

    result = rule_04_clean_grade.apply([target], empty_input, rationale)

    assert result[0].background_color == expected_color
    assert result[0].transparency_pct == 50


def test_all_rooms_get_rationale(minimal_rooms, empty_input):
    """4개 Room 입력 시 rationale도 4개 append."""
    rationale: list[Rationale] = []

    rule_04_clean_grade.apply(minimal_rooms, empty_input, rationale)

    assert len(rationale) == 4
    assert all(r.rule_id == "rule_04_clean_grade" for r in rationale)


def test_flag_grade_d_process_open_system(minimal_rooms, empty_input):
    """주공정 + Grade D + closed_system=False → suspected_violation."""
    # minimal_rooms[2] = Material storage (auxiliary, D) — flag 안 나야 함
    # category를 process로 바꿔서 검증.
    target = dataclasses.replace(
        minimal_rooms[2], category="process"
    )
    rationale: list[Rationale] = []

    rule_04_clean_grade.apply([target], empty_input, rationale)

    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "suspected_violation"
    assert "Grade D" in flags[0].note


def test_no_flag_when_closed_system(minimal_rooms, empty_input):
    """closed_system_main_process=True이면 주공정 Grade D OK — flag 없음."""
    target = dataclasses.replace(
        minimal_rooms[2], category="process"
    )
    product = dataclasses.replace(
        empty_input.product, closed_system_main_process=True
    )
    inp = dataclasses.replace(empty_input, product=product)
    rationale: list[Rationale] = []

    rule_04_clean_grade.apply([target], inp, rationale)

    assert not rationale[0].flags


def test_urs_passthrough(minimal_rooms, empty_input):
    """원본 Room의 grade·gowning_type 값은 수정되지 않는다."""
    rationale: list[Rationale] = []

    result = rule_04_clean_grade.apply(minimal_rooms, empty_input, rationale)

    for orig, new in zip(minimal_rooms, result):
        assert new.clean_grade == orig.clean_grade
        assert new.gowning_type == orig.gowning_type
