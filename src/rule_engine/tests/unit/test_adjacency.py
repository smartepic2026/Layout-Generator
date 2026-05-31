"""L1 unit test — derive/adjacency."""
from __future__ import annotations

import dataclasses

from src.rule_engine.derive import build_adjacency
from src.rule_engine.derive.adjacency import ELEVATOR_MATERIAL_NODE, ELEVATOR_WASTE_NODE
from src.rule_engine.models import AirLock, Rationale, Room


def _room(rid, name_en, category="process", grade="C", process_no=None) -> Room:
    return Room(
        room_id=rid, name_ko=name_en, name_en=name_en, category=category,
        clean_grade=grade, room_flow="One-way", gowning_type="무진복",
        gowning_method=None, equipment=[], process_no=process_no or [],
        area_m2=100.0, width_mm=None, depth_mm=None,
        ceiling_height_mm=None, volume_m3=None,
        differential_pressure_Pa=None, air_changes_per_hour=None,
        recovery_time_min=None, background_color=None,
        transparency_pct=None, well_type_ceiling=False,
    )


def _al(rid, kind="PAL_in", purpose="personnel") -> AirLock:
    return AirLock(
        al_id=rid.replace("R_", "AL_"), kind=kind, clean_grade="C",
        area_m2=12.0, flow_type="cascade",
        connects_higher_room=None, connects_lower_room=None,
        purpose=purpose, differential_pressure_Pa=None,
    )


def test_process_flow_adjacency(empty_input):
    """3개 process Room이 process_no 순서로 chain 인접."""
    rooms = [
        _room("R_HARVEST", "Harvest", process_no=["P5-1"]),
        _room("R_MEDIA", "Media preparation", process_no=["P1-1"]),
        _room("R_CC", "Cell Culture", process_no=["P4-1"]),
    ]
    rationale: list[Rationale] = []

    edges = build_adjacency(rooms, [], empty_input, rationale)

    # P1 → P4 → P5 순서, 2개 인접 엣지 생성.
    process_edges = [e for e in edges if not e.is_elevator_constraint]
    assert len(process_edges) == 2
    assert process_edges[0].from_id == "R_MEDIA"
    assert process_edges[0].to_id == "R_CC"
    assert process_edges[0].flow_direction == "bidirectional"


def test_al_in_adjacency(empty_input):
    """PAL_in 은 AL → Room 방향(one_way_in)."""
    rooms = [
        _room("R_CC", "Cell Culture", process_no=["P4-1"]),
        _room("R_PAL_IN_CC", "PAL-in Cell Culture", process_no=[]),
    ]
    airlocks = [_al("R_PAL_IN_CC", kind="PAL_in")]
    rationale: list[Rationale] = []

    edges = build_adjacency(rooms, airlocks, empty_input, rationale)

    al_edges = [e for e in edges if e.from_id.startswith("AL_") or e.to_id.startswith("AL_")]
    assert len(al_edges) == 1
    assert al_edges[0].from_id == "AL_PAL_IN_CC"
    assert al_edges[0].to_id == "R_CC"
    assert al_edges[0].flow_direction == "one_way_in"


def test_al_out_reversed_direction(empty_input):
    """PAL_out 은 Room → AL 방향(one_way_out)."""
    rooms = [
        _room("R_CC", "Cell Culture", process_no=["P4-1"]),
        _room("R_PAL_OUT_CC", "PAL-out Cell Culture", process_no=[]),
    ]
    airlocks = [_al("R_PAL_OUT_CC", kind="PAL_out")]
    rationale: list[Rationale] = []

    edges = build_adjacency(rooms, airlocks, empty_input, rationale)

    al_edges = [e for e in edges if e.to_id.startswith("AL_")]
    assert len(al_edges) == 1
    assert al_edges[0].from_id == "R_CC"
    assert al_edges[0].flow_direction == "one_way_out"


def test_elevator_material_node(empty_input):
    """엘리베이터(material) 가상 노드 → Material-in Room."""
    # Material-in (URS 오타 'Mateial-in') Room이 보조 구역에 있는 시나리오.
    rooms = [
        _room("R_MATERIAL_IN", "Mateial-in", category="auxiliary", grade="CNC"),
    ]
    rationale: list[Rationale] = []

    edges = build_adjacency(rooms, [], empty_input, rationale)

    elev_edges = [e for e in edges if e.is_elevator_constraint]
    assert len(elev_edges) == 1
    assert elev_edges[0].from_id == ELEVATOR_MATERIAL_NODE
    assert elev_edges[0].to_id == "R_MATERIAL_IN"
    assert elev_edges[0].flow_direction == "one_way_in"


def test_elevator_waste_node(empty_input):
    """엘리베이터(waste) 가상 노드 ← Waste-out Room."""
    rooms = [
        _room("R_WASTE_OUT", "Waste-out", category="auxiliary", grade="CNC"),
    ]
    rationale: list[Rationale] = []

    edges = build_adjacency(rooms, [], empty_input, rationale)

    elev_edges = [e for e in edges if e.is_elevator_constraint]
    assert len(elev_edges) == 1
    assert elev_edges[0].from_id == "R_WASTE_OUT"
    assert elev_edges[0].to_id == ELEVATOR_WASTE_NODE


def test_no_elevator_when_unset(empty_input):
    """building.elevator_*가 None이면 가상 노드 엣지 없음."""
    bld = dataclasses.replace(
        empty_input.building,
        elevator_for_material_in=None,
        elevator_for_waste_out=None,
    )
    inp = dataclasses.replace(empty_input, building=bld)
    rooms = [
        _room("R_MATERIAL_IN", "Mateial-in", category="auxiliary"),
        _room("R_WASTE_OUT", "Waste-out", category="auxiliary"),
    ]
    rationale: list[Rationale] = []

    edges = build_adjacency(rooms, [], inp, rationale)

    assert not any(e.is_elevator_constraint for e in edges)


def test_rationale_emitted_once(empty_input):
    """build_adjacency는 rationale 한 줄만 추가."""
    rooms = [_room("R_X", "Cell Culture", process_no=["P4-1"])]
    rationale: list[Rationale] = []

    build_adjacency(rooms, [], empty_input, rationale)

    assert len(rationale) == 1
    assert rationale[0].rule_id == "adjacency"
