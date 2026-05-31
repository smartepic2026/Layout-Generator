"""L1 unit test — rule_09_doors."""
from __future__ import annotations

import dataclasses

from src.rule_engine.models import AdjacencyEdge, AirLock, Rationale, Room
from src.rule_engine.rules import rule_09_doors


def _edge(from_id, to_id, relationship="door"):
    return AdjacencyEdge(
        from_id=from_id, to_id=to_id, relationship=relationship,
        door_count=1 if relationship == "door" else 0,
        door_size_mm=None, door_swing_target=None,
        flow_direction="bidirectional", is_elevator_constraint=False,
    )


def _room(rid, dp):
    return Room(
        room_id=rid, name_ko=rid, name_en=rid, category="process",
        clean_grade="C", room_flow="Both-way", gowning_type="무진복",
        gowning_method=None, equipment=[], process_no=[],
        area_m2=100.0, width_mm=None, depth_mm=None,
        ceiling_height_mm=None, volume_m3=None,
        differential_pressure_Pa=dp, air_changes_per_hour=None,
        recovery_time_min=None, background_color=None,
        transparency_pct=None, well_type_ceiling=False,
    )


def _al(aid, kind="PAL_in"):
    return AirLock(
        al_id=aid, kind=kind, clean_grade="C", area_m2=12.0,
        flow_type="cascade", connects_higher_room=None,
        connects_lower_room=None,
        purpose="material" if "MAL" in kind else "personnel",
        differential_pressure_Pa=20.0,
    )


def test_default_door_size_1000(empty_input):
    edges = [_edge("R_A", "R_B")]
    rooms = [_room("R_A", 30.0), _room("R_B", 30.0)]
    rationale: list[Rationale] = []

    out = rule_09_doors.apply(edges, rooms, [], rationale)

    assert out[0].door_size_mm == 1000


def test_mal_door_size_1500(empty_input):
    edges = [_edge("AL_MAL_IN", "R_B")]
    rooms = [_room("R_B", 30.0)]
    airlocks = [_al("AL_MAL_IN", kind="MAL_in")]
    rationale: list[Rationale] = []

    out = rule_09_doors.apply(edges, rooms, airlocks, rationale)

    assert out[0].door_size_mm == 1500


def test_swing_low_pressure_side(empty_input):
    """from(45) > to(30)이면 swing target은 low_pressure_side."""
    edges = [_edge("R_HIGH", "R_LOW")]
    rooms = [_room("R_HIGH", 45.0), _room("R_LOW", 30.0)]
    rationale: list[Rationale] = []

    out = rule_09_doors.apply(edges, rooms, [], rationale)

    assert out[0].door_swing_target == "low_pressure_side"


def test_swing_high_pressure_side_when_from_lower(empty_input):
    """from(15) < to(30)이면 swing target은 high_pressure_side."""
    edges = [_edge("R_LOW", "R_HIGH")]
    rooms = [_room("R_LOW", 15.0), _room("R_HIGH", 30.0)]
    rationale: list[Rationale] = []

    out = rule_09_doors.apply(edges, rooms, [], rationale)

    assert out[0].door_swing_target == "high_pressure_side"


def test_swing_none_when_equal(empty_input):
    edges = [_edge("R_A", "R_B")]
    rooms = [_room("R_A", 30.0), _room("R_B", 30.0)]
    rationale: list[Rationale] = []

    out = rule_09_doors.apply(edges, rooms, [], rationale)

    assert out[0].door_swing_target is None


def test_passthrough_edge_untouched(empty_input):
    """relationship != door 인 엣지는 손대지 않음."""
    edges = [_edge("R_WASH", "R_PREP", relationship="passthrough_only")]
    rationale: list[Rationale] = []

    out = rule_09_doors.apply(edges, [], [], rationale)

    assert out[0].door_size_mm is None
    assert out[0].door_swing_target is None
