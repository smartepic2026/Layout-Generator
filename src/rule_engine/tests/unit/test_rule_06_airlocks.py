"""L1 unit test — rule_06_airlocks."""
from __future__ import annotations

import dataclasses

import pytest

from src.rule_engine.models import Rationale, Room
from src.rule_engine.rules import rule_06_airlocks


def _make_al_room(name_en: str, grade: str = "C") -> Room:
    return Room(
        room_id="R_" + name_en.upper().replace(" ", "_").replace("(", "").replace(")", ""),
        name_ko=name_en, name_en=name_en, category="process",
        clean_grade=grade, room_flow="One-way", gowning_type="무진복",
        gowning_method=None, equipment=[], process_no=[],
        area_m2=12.0, width_mm=None, depth_mm=None,
        ceiling_height_mm=None, volume_m3=None,
        differential_pressure_Pa=None, air_changes_per_hour=None,
        recovery_time_min=None, background_color=None,
        transparency_pct=None, well_type_ceiling=False,
    )


@pytest.mark.parametrize(
    "name_en,expected_kind,expected_purpose",
    [
        ("PAL-in Cell Culture", "PAL_in", "personnel"),
        ("PAL-out Cell Culture", "PAL_out", "personnel"),
        ("MAL-in Cell Culture", "MAL_in", "material"),
        ("MAL-out Cell Culture", "MAL_out", "material"),
        ("CAL-in Inoculation", "CAL_in", "common"),
        ("CAL-out Inoculation", "CAL_out", "common"),
    ],
)
def test_kind_detection(empty_input, name_en, expected_kind, expected_purpose):
    """이름 패턴으로 kind와 purpose가 정확히 추론."""
    rooms = [_make_al_room(name_en)]
    rationale: list[Rationale] = []

    als = rule_06_airlocks.apply(rooms, empty_input, rationale)

    assert len(als) == 1
    assert als[0].kind == expected_kind
    assert als[0].purpose == expected_purpose


def test_only_al_rooms_become_airlocks(empty_input):
    """일반 Room은 AL 생성에서 제외."""
    rooms = [
        Room(  # Non-AL 일반 공정실
            room_id="R_CC", name_ko="배양실", name_en="Cell Culture",
            category="process", clean_grade="C", room_flow="One-way",
            gowning_type="무진복", gowning_method=None, equipment=[],
            process_no=[], area_m2=150.0, width_mm=None, depth_mm=None,
            ceiling_height_mm=None, volume_m3=None,
            differential_pressure_Pa=None, air_changes_per_hour=None,
            recovery_time_min=None, background_color=None,
            transparency_pct=None, well_type_ceiling=False,
        ),
        _make_al_room("PAL-in Cell Culture"),
        _make_al_room("MAL-out Cell Culture"),
    ]
    rationale: list[Rationale] = []

    als = rule_06_airlocks.apply(rooms, empty_input, rationale)

    assert len(als) == 2
    assert all("AL" in al.al_id for al in als)


def test_no_al_rooms_returns_empty(empty_input):
    """AL Room이 없으면 빈 리스트."""
    rooms = [
        Room(
            room_id="R_OFFICE", name_ko="사무실", name_en="Office",
            category="NC", clean_grade="NC", room_flow="Both-way",
            gowning_type="일상복", gowning_method=None, equipment=[],
            process_no=[], area_m2=100.0, width_mm=None, depth_mm=None,
            ceiling_height_mm=None, volume_m3=None,
            differential_pressure_Pa=None, air_changes_per_hour=None,
            recovery_time_min=None, background_color=None,
            transparency_pct=None, well_type_ceiling=False,
        ),
    ]
    rationale: list[Rationale] = []

    als = rule_06_airlocks.apply(rooms, empty_input, rationale)

    assert als == []


def test_grade_and_area_propagated(empty_input):
    """AL의 grade·area_m2가 원본 Room에서 전달됨."""
    room = _make_al_room("PAL-in Cell Culture", grade="B")
    room = dataclasses.replace(room, area_m2=12.0)
    rationale: list[Rationale] = []

    als = rule_06_airlocks.apply([room], empty_input, rationale)

    assert als[0].clean_grade == "B"
    assert als[0].area_m2 == 12.0


def test_default_flow_type_is_cascade(empty_input):
    """룰 6 단계에서는 flow_type=cascade (룰 7에서 결정)."""
    rooms = [_make_al_room("PAL-in Cell Culture")]
    rationale: list[Rationale] = []

    als = rule_06_airlocks.apply(rooms, empty_input, rationale)

    assert als[0].flow_type == "cascade"
    assert als[0].differential_pressure_Pa is None  # 룰 13에서 결정
    assert als[0].connects_higher_room is None       # 룰 13에서 결정
