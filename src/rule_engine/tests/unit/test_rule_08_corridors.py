"""L1 unit test — rule_08_corridors."""
from __future__ import annotations

import dataclasses

from src.rule_engine.models import AdjacencyEdge, Rationale, Room
from src.rule_engine.rules import rule_08_corridors


def _edge(from_id, to_id):
    return AdjacencyEdge(
        from_id=from_id, to_id=to_id, relationship="door",
        door_count=1, door_size_mm=None, door_swing_target=None,
        flow_direction="bidirectional", is_elevator_constraint=False,
    )


def _room(rid, name_en):
    return Room(
        room_id=rid, name_ko=name_en, name_en=name_en,
        category="process", clean_grade="C", room_flow="Both-way",
        gowning_type="무진복", gowning_method=None, equipment=[],
        process_no=[], area_m2=100.0, width_mm=None, depth_mm=None,
        ceiling_height_mm=None, volume_m3=None,
        differential_pressure_Pa=None, air_changes_per_hour=None,
        recovery_time_min=None, background_color=None,
        transparency_pct=None, well_type_ceiling=False,
    )


def test_direct_supply_return_flagged(empty_input):
    """Supply ↔ Return 직결 → suspected_violation flag 1개."""
    rooms = [
        _room("R_SUPPLY", "Supply corridor"),
        _room("R_RETURN", "Return corridor"),
    ]
    edges = [_edge("R_SUPPLY", "R_RETURN")]
    rationale: list[Rationale] = []

    rule_08_corridors.apply(edges, rooms, empty_input, rationale)

    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "suspected_violation"
    assert rationale[0].input_facts["violations"] == 1


def test_no_violation_when_separated(empty_input):
    """공급/리턴이 process Room을 거쳐 연결 → flag 없음."""
    rooms = [
        _room("R_SUPPLY", "Supply corridor"),
        _room("R_RETURN", "Return corridor"),
        _room("R_CC", "Cell Culture"),
    ]
    edges = [
        _edge("R_SUPPLY", "R_CC"),
        _edge("R_CC", "R_RETURN"),
    ]
    rationale: list[Rationale] = []

    rule_08_corridors.apply(edges, rooms, empty_input, rationale)

    assert not rationale[0].flags


def test_skipped_when_policy_off(empty_input):
    """flow_policy.supply_return_corridor_separate=False → 검사 skip."""
    fp = dataclasses.replace(
        empty_input.flow_policy, supply_return_corridor_separate=False
    )
    inp = dataclasses.replace(empty_input, flow_policy=fp)
    rooms = [
        _room("R_SUPPLY", "Supply corridor"),
        _room("R_RETURN", "Return corridor"),
    ]
    edges = [_edge("R_SUPPLY", "R_RETURN")]
    rationale: list[Rationale] = []

    rule_08_corridors.apply(edges, rooms, inp, rationale)

    assert not rationale[0].flags
    assert "skipped" in rationale[0].decision
