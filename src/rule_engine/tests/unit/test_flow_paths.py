"""L1 unit test — derive/flow_paths."""
from __future__ import annotations

import dataclasses

from src.rule_engine.derive import derive_flow_paths
from src.rule_engine.derive.adjacency import ELEVATOR_MATERIAL_NODE, ELEVATOR_WASTE_NODE
from src.rule_engine.models import Rationale, Room


def _room(rid, name_en, category="process", process_no=None) -> Room:
    return Room(
        room_id=rid, name_ko=name_en, name_en=name_en, category=category,
        clean_grade="C", room_flow="One-way", gowning_type="무진복",
        gowning_method=None, equipment=[], process_no=process_no or [],
        area_m2=100.0, width_mm=None, depth_mm=None,
        ceiling_height_mm=None, volume_m3=None,
        differential_pressure_Pa=None, air_changes_per_hour=None,
        recovery_time_min=None, background_color=None,
        transparency_pct=None, well_type_ceiling=False,
    )


def test_product_order_sorted_by_process_no(empty_input):
    """process Room들이 P 번호 오름차순으로 정렬."""
    rooms = [
        _room("R_HARVEST", "Harvest", process_no=["P5-1"]),
        _room("R_MEDIA", "Media preparation", process_no=["P1-1"]),
        _room("R_CC", "Cell Culture", process_no=["P4-1"]),
    ]
    rationale: list[Rationale] = []

    paths = derive_flow_paths(rooms, [], empty_input, rationale)

    assert paths.product_process_order == ["R_MEDIA", "R_CC", "R_HARVEST"]


def test_personnel_entry_lobby_to_first_process(empty_input):
    """Lobby → Gowning → Supply → 첫 process."""
    rooms = [
        _room("R_LOBBY", "Lobby", category="NC", process_no=[]),
        _room("R_GOW", "Gowning", category="process", process_no=[]),
        _room("R_SUPPLY", "Supply corridor", process_no=[]),
        _room("R_MEDIA", "Media preparation", process_no=["P1-1"]),
    ]
    rationale: list[Rationale] = []

    paths = derive_flow_paths(rooms, [], empty_input, rationale)

    assert paths.personnel_entry == ["R_LOBBY", "R_GOW", "R_SUPPLY", "R_MEDIA"]


def test_material_entry_starts_with_elevator(empty_input):
    """material_entry는 ELEVATOR_MATERIAL_IN으로 시작."""
    rooms = [
        _room("R_MATIN", "Mateial-in", category="auxiliary", process_no=[]),
        _room("R_SUPPLY", "Supply corridor", process_no=[]),
        _room("R_MEDIA", "Media preparation", process_no=["P1-1"]),
    ]
    rationale: list[Rationale] = []

    paths = derive_flow_paths(rooms, [], empty_input, rationale)

    assert paths.material_entry[0] == ELEVATOR_MATERIAL_NODE
    assert "R_MATIN" in paths.material_entry
    assert paths.material_entry[-1] == "R_MEDIA"


def test_waste_exit_ends_with_elevator(empty_input):
    """waste_exit는 ELEVATOR_WASTE_OUT으로 종료."""
    rooms = [
        _room("R_MEDIA", "Media preparation", process_no=["P1-1"]),
        _room("R_RETURN", "Return corridor", process_no=[]),
        _room("R_WASTE", "Waste-out", category="auxiliary", process_no=[]),
    ]
    rationale: list[Rationale] = []

    paths = derive_flow_paths(rooms, [], empty_input, rationale)

    assert paths.waste_exit[-1] == ELEVATOR_WASTE_NODE
    assert "R_WASTE" in paths.waste_exit
    assert "R_RETURN" in paths.waste_exit


def test_no_elevator_skips_anchors(empty_input):
    """엘리베이터 None이면 가상 노드 빠짐."""
    bld = dataclasses.replace(
        empty_input.building,
        elevator_for_material_in=None,
        elevator_for_waste_out=None,
    )
    inp = dataclasses.replace(empty_input, building=bld)
    rooms = [
        _room("R_MEDIA", "Media preparation", process_no=["P1-1"]),
        _room("R_WASTE", "Waste-out", category="auxiliary", process_no=[]),
    ]
    rationale: list[Rationale] = []

    paths = derive_flow_paths(rooms, [], inp, rationale)

    assert ELEVATOR_MATERIAL_NODE not in paths.material_entry
    assert ELEVATOR_WASTE_NODE not in paths.waste_exit


def test_personnel_exit_reverse(empty_input):
    """personnel_exit은 마지막 process → Return → Gowning → Lobby."""
    rooms = [
        _room("R_LOBBY", "Lobby", category="NC", process_no=[]),
        _room("R_GOW", "Gowning", category="process", process_no=[]),
        _room("R_RETURN", "Return corridor", process_no=[]),
        _room("R_MEDIA", "Media preparation", process_no=["P1-1"]),
        _room("R_HARVEST", "Harvest", process_no=["P5-1"]),
    ]
    rationale: list[Rationale] = []

    paths = derive_flow_paths(rooms, [], empty_input, rationale)

    assert paths.personnel_exit == ["R_HARVEST", "R_RETURN", "R_GOW", "R_LOBBY"]
