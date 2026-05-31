"""L1 unit test — rule_03_room_size."""
from __future__ import annotations

import dataclasses

from src.rule_engine.models import Equipment, Rationale
from src.rule_engine.rules import rule_03_room_size


def test_kb_legend_lookup(minimal_rooms, empty_input):
    """name_en이 KB에 있으면 KB 값 사용 (Inoculation=40)."""
    target = dataclasses.replace(
        minimal_rooms[0], name_en="Inoculation", clean_grade="B", area_m2=None
    )
    rationale: list[Rationale] = []

    result = rule_03_room_size.apply([target], empty_input, rationale)

    assert result[0].area_m2 == 40.0
    assert result[0].ceiling_height_mm == 3000  # Grade B
    assert result[0].volume_m3 == 40.0 * 3000 / 1000
    assert rationale[0].input_facts["source"] == "kb_legend"
    assert not rationale[0].flags


def test_override_takes_precedence(minimal_rooms, empty_input):
    """area_overrides가 KB보다 우선."""
    overrides = dataclasses.replace(
        empty_input.overrides, area_overrides={"Inoculation": 50.0}
    )
    inp = dataclasses.replace(empty_input, overrides=overrides)
    target = dataclasses.replace(
        minimal_rooms[0], name_en="Inoculation", clean_grade="B", area_m2=None
    )
    rationale: list[Rationale] = []

    result = rule_03_room_size.apply([target], inp, rationale)

    assert result[0].area_m2 == 50.0
    assert rationale[0].input_facts["source"] == "override"


def test_preset_area_kept(minimal_rooms, empty_input):
    """Room.area_m2가 이미 채워져 있으면 그대로 사용."""
    target = dataclasses.replace(
        minimal_rooms[0], name_en="Inoculation", area_m2=99.9
    )
    rationale: list[Rationale] = []

    result = rule_03_room_size.apply([target], empty_input, rationale)

    assert result[0].area_m2 == 99.9
    assert rationale[0].input_facts["source"] == "preset"


def test_unknown_room_with_equipment_uses_algorithm_b(minimal_rooms, empty_input):
    """KB에 없는 Room + 장비 있음 → Algorithm B 산출 + info flag."""
    eq = Equipment(
        instance_id="X", name="Tank", width_mm=3000, depth_mm=2500,
        height_mm=4000, weight_kg=None, max_operating_weight_kg=None,
        process_no=[],
    )
    target = dataclasses.replace(
        minimal_rooms[0],
        name_en="Custom Room",
        clean_grade="C",
        area_m2=None,
        equipment=[eq],
    )
    rationale: list[Rationale] = []

    result = rule_03_room_size.apply([target], empty_input, rationale)

    assert result[0].area_m2 is not None
    assert result[0].area_m2 > 0
    assert rationale[0].input_facts["source"] == "algorithm_B"
    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "info"


def test_unknown_room_no_equipment_flags_violation(minimal_rooms, empty_input):
    """KB에 없고 장비도 없으면 suspected_violation flag + area=None."""
    target = dataclasses.replace(
        minimal_rooms[0], name_en="Mystery Room", area_m2=None, equipment=[]
    )
    rationale: list[Rationale] = []

    result = rule_03_room_size.apply([target], empty_input, rationale)

    assert result[0].area_m2 is None
    flags = rationale[0].flags
    assert any(f.severity == "suspected_violation" for f in flags)


def test_purification1_lookup_300(minimal_rooms, empty_input):
    """정제실1 → 300 m² (정제실1 prototype 결과와 일치)."""
    target = dataclasses.replace(
        minimal_rooms[0],
        name_en="Purification 1",
        clean_grade="C",
        area_m2=None,
    )
    rationale: list[Rationale] = []

    result = rule_03_room_size.apply([target], empty_input, rationale)

    assert result[0].area_m2 == 300.0
    assert result[0].volume_m3 == 300.0 * 2700 / 1000


def test_grade_to_ceiling_mapping(minimal_rooms, empty_input):
    """Grade B → 3000mm, Grade C/D → 2700mm."""
    rooms = [
        dataclasses.replace(minimal_rooms[0], name_en="Inoculation",
                            clean_grade="B", area_m2=None),
        dataclasses.replace(minimal_rooms[1], name_en="Cell Culture",
                            clean_grade="C", area_m2=None),
        dataclasses.replace(minimal_rooms[2], name_en="Material storage",
                            clean_grade="D", area_m2=None),
    ]
    rationale: list[Rationale] = []

    result = rule_03_room_size.apply(rooms, empty_input, rationale)

    assert result[0].ceiling_height_mm == 3000
    assert result[1].ceiling_height_mm == 2700
    assert result[2].ceiling_height_mm == 2700
