"""L1 unit test — rule_15_gowning.

검증 포인트:
    1. 등급별 gowning_method가 출입복장 시트 매핑대로 정확한가
    2. URS gowning_type이 등급과 불일치하면 suspected_violation flag
    3. 정상 케이스에서는 flag 없음
    4. URS의 gowning_type 값은 보존(수정되지 않음)
"""
from __future__ import annotations

import dataclasses

import pytest

from src.rule_engine.models import Rationale
from src.rule_engine.rules import rule_15_gowning


@pytest.mark.parametrize(
    "grade,expected_method",
    [
        ("B", "over gowning"),
        ("C", "over gowning"),
        ("D", "degowning and gowning"),
        ("CNC", "degowning and gowning"),
        ("NC", "regular"),
    ],
)
def test_method_mapping(minimal_rooms, empty_input, grade, expected_method):
    """등급별 gowning_method 매핑."""
    # 매칭되는 gowning_type을 함께 설정.
    type_map = {
        "B": "무균복", "C": "무진복",
        "D": "스크럽", "CNC": "스크럽", "NC": "일상복",
    }
    target = dataclasses.replace(
        minimal_rooms[0],
        clean_grade=grade,
        gowning_type=type_map[grade],
    )
    rationale: list[Rationale] = []

    result = rule_15_gowning.apply([target], empty_input, rationale)

    assert result[0].gowning_method == expected_method
    assert not rationale[0].flags  # 매칭 케이스는 flag 없음


def test_flag_when_gowning_type_mismatch(minimal_rooms, empty_input):
    """Grade B Room에 '스크럽' 복장이 명시되면 flag."""
    target = dataclasses.replace(
        minimal_rooms[0],
        clean_grade="B",
        gowning_type="스크럽",  # B는 '무균복'이어야 함
    )
    rationale: list[Rationale] = []

    rule_15_gowning.apply([target], empty_input, rationale)

    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "suspected_violation"
    assert "불일치" in flags[0].note


def test_urs_passthrough(minimal_rooms, empty_input):
    """원본 Room의 clean_grade·gowning_type은 수정되지 않는다."""
    rationale: list[Rationale] = []

    result = rule_15_gowning.apply(minimal_rooms, empty_input, rationale)

    for orig, new in zip(minimal_rooms, result):
        assert new.clean_grade == orig.clean_grade
        assert new.gowning_type == orig.gowning_type
        # gowning_method만 새로 채워졌어야 함.
        assert new.gowning_method is not None or orig.clean_grade not in (
            "B", "C", "D", "CNC", "NC"
        )


def test_grade_a_warning(minimal_rooms, empty_input):
    """Grade A Room이 들어오면 warning flag (표에 없음)."""
    target = dataclasses.replace(
        minimal_rooms[0], clean_grade="A", gowning_type="무균복"
    )
    rationale: list[Rationale] = []

    rule_15_gowning.apply([target], empty_input, rationale)

    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "warning"
