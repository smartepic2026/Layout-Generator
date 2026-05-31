"""L1 unit test — rule_13_pressure."""
from __future__ import annotations

import dataclasses

import pytest

from src.rule_engine.models import AirLock, Rationale
from src.rule_engine.rules import rule_13_pressure


def _make_al(al_id: str, grade: str, flow_type: str = "cascade") -> AirLock:
    return AirLock(
        al_id=al_id, kind="PAL_in", clean_grade=grade,
        area_m2=12.0, flow_type=flow_type,
        connects_higher_room=None, connects_lower_room=None,
        purpose="personnel", differential_pressure_Pa=None,
    )


@pytest.mark.parametrize(
    "grade,expected_dp",
    [
        ("A", 60.0),
        ("B", 45.0),
        ("C", 30.0),
        ("D", 15.0),
        ("CNC", 5.0),
        ("NC", 0.0),
    ],
)
def test_grade_to_pressure(minimal_rooms, empty_input, grade, expected_dp):
    """6개 등급별 기본 차압 매핑."""
    target = dataclasses.replace(minimal_rooms[0], clean_grade=grade)
    rationale: list[Rationale] = []

    rooms, _ = rule_13_pressure.apply([target], [], empty_input, rationale)

    assert rooms[0].differential_pressure_Pa == expected_dp


def test_cascade_above_room(minimal_rooms, empty_input):
    """cascade AL은 자기 grade 기본 - 5 Pa."""
    als = [_make_al("AL_C", "C", "cascade")]
    rationale: list[Rationale] = []

    _, al_out = rule_13_pressure.apply([], als, empty_input, rationale)

    # Grade C 기본 30 Pa - 5 = 25.
    assert al_out[0].differential_pressure_Pa == 25.0


def test_sink_lower(minimal_rooms, empty_input):
    """sink AL은 grade 기본 - 10 Pa."""
    als = [_make_al("AL_C", "C", "sink")]
    rationale: list[Rationale] = []

    _, al_out = rule_13_pressure.apply([], als, empty_input, rationale)

    assert al_out[0].differential_pressure_Pa == 20.0


def test_bubble_higher(minimal_rooms, empty_input):
    """bubble AL은 grade 기본 + 5 Pa."""
    als = [_make_al("AL_C", "C", "bubble")]
    rationale: list[Rationale] = []

    _, al_out = rule_13_pressure.apply([], als, empty_input, rationale)

    assert al_out[0].differential_pressure_Pa == 35.0


def test_cascade_floor_at_zero(minimal_rooms, empty_input):
    """NC 등급 cascade AL의 DP는 음수가 되지 않고 0으로 clamp."""
    als = [_make_al("AL_NC", "NC", "cascade")]
    rationale: list[Rationale] = []

    _, al_out = rule_13_pressure.apply([], als, empty_input, rationale)

    assert al_out[0].differential_pressure_Pa == 0.0


def test_pressure_cascade_relationship(minimal_rooms, empty_input):
    """B(45) > C(30) > D(15) > CNC(5) > NC(0) 순서 보장."""
    rooms = [
        dataclasses.replace(minimal_rooms[0], clean_grade="B"),
        dataclasses.replace(minimal_rooms[1], clean_grade="C"),
        dataclasses.replace(minimal_rooms[2], clean_grade="D"),
        dataclasses.replace(minimal_rooms[3], clean_grade="NC"),
    ]
    rationale: list[Rationale] = []

    out, _ = rule_13_pressure.apply(rooms, [], empty_input, rationale)

    dps = [r.differential_pressure_Pa for r in out]
    assert dps[0] > dps[1] > dps[2] > dps[3]


def test_rationale_per_room_and_al(minimal_rooms, empty_input):
    """Room 1개 + AL 1개 → rationale 2줄."""
    rooms = [dataclasses.replace(minimal_rooms[0], clean_grade="C")]
    als = [_make_al("AL_1", "C")]
    rationale: list[Rationale] = []

    rule_13_pressure.apply(rooms, als, empty_input, rationale)

    assert len(rationale) == 2
    assert all(r.rule_id == "rule_13_pressure" for r in rationale)
