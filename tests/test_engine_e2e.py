"""End-to-end tests: URSInput → RuleEngineOutput, hard constraints, negative cases."""
from __future__ import annotations

import pytest

from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput
from src.contract.validators import (
    c1_supply_return_no_direct,
    c5_pressure_diff_min,
    validate_hard_constraints,
)
from src.contract.working_state import WorkingState
from src.contract.schemas import Adjacency


def test_default_run_passes_strict():
    """기본 URS는 strict 모드에서 통과해야 함."""
    out = run_rule_engine(URSInput(), strict=True)
    assert out.modality == "mAb"
    assert len(out.rooms) > 20
    assert len(out.airlocks) >= 10
    assert len(out.adjacency) > 30
    assert len(out.rationale) > 50


def test_one_way_rooms_have_in_and_out_als():
    out = run_rule_engine(URSInput(), strict=True)
    for r in out.rooms:
        if not r.one_way_flow:
            continue
        types = {a.type for a in out.airlocks if a.connects_higher == r.id}
        # in/out 각각 최소 하나 (PAL/MAL/CAL 어떤 조합이든)
        has_in = any(t.endswith("_in") for t in types)
        has_out = any(t.endswith("_out") for t in types)
        assert has_in and has_out, f"{r.id} missing in/out AL: {types}"


def test_grade_pressure_monotonic_room_to_room():
    """Room↔Room 차압이 등급 순서를 위반하지 않아야 함."""
    out = run_rule_engine(URSInput(), strict=True)
    order = {g: i for i, g in enumerate(out.constraints.pressure_grade_order)}
    room_by_id = {r.id: r for r in out.rooms}
    for adj in out.adjacency:
        if adj.relationship != "door":
            continue
        a, b = adj.from_id, adj.to_id
        if a not in room_by_id or b not in room_by_id:
            continue
        ra, rb = room_by_id[a], room_by_id[b]
        if ra.clean_grade == rb.clean_grade:
            continue
        rank_a, rank_b = order[ra.clean_grade], order[rb.clean_grade]
        if rank_a < rank_b:
            assert ra.differential_pressure_Pa > rb.differential_pressure_Pa, (
                f"{a}(G{ra.clean_grade}={ra.differential_pressure_Pa}) "
                f"vs {b}(G{rb.clean_grade}={rb.differential_pressure_Pa})"
            )


def test_validator_catches_supply_return_direct_connection():
    """C1: 강제로 supply↔return 도어 연결 → 위반 잡혀야 함."""
    state = WorkingState(urs=URSInput())
    state.adjacency.append(
        Adjacency(
            from_id="R_SUPPLY_CORRIDOR",
            to_id="R_RETURN_CORRIDOR",
            relationship="door",
            door_count=1,
            door_size_mm=1000,
        )
    )
    v = c1_supply_return_no_direct(state)
    assert v and v[0]["id"] == "C1"


def test_validator_catches_low_pressure_diff():
    """C5: 강제로 등급 다른 Room을 같은 DP로 연결 → 위반."""
    from src.contract.schemas import Room
    from src.contract.schemas import RangeMM

    state = WorkingState(urs=URSInput())
    state.rooms["RA"] = Room(
        id="RA", name_ko="a", name_en="a", category="process", clean_grade="C",
        area_m2=10, differential_pressure_Pa=10
    )
    state.rooms["RB"] = Room(
        id="RB", name_ko="b", name_en="b", category="process", clean_grade="D",
        area_m2=10, differential_pressure_Pa=8  # 차이 2Pa < 10Pa
    )
    state.adjacency.append(
        Adjacency(from_id="RA", to_id="RB", relationship="door")
    )
    v = c5_pressure_diff_min(state)
    assert v and v[0]["id"] == "C5"


def test_overrides_force_exclude_works():
    urs = URSInput(overrides={"force_exclude_rooms": ["R_LOUNGE", "R_IPC"]})
    out = run_rule_engine(urs, strict=True)
    ids = {r.id for r in out.rooms}
    assert "R_IPC" not in ids


def test_overrides_area_works():
    urs = URSInput(overrides={"area_overrides_m2": {"R_PURIFICATION_1": 350.0}})
    out = run_rule_engine(urs, strict=True)
    pur1 = next(r for r in out.rooms if r.id == "R_PURIFICATION_1")
    assert pur1.area_m2 == 350.0


def test_json_roundtrip():
    out = run_rule_engine(URSInput(), strict=True)
    js = out.model_dump_json()
    from src.contract.schemas import RuleEngineOutput
    back = RuleEngineOutput.model_validate_json(js)
    assert len(back.rooms) == len(out.rooms)
    assert len(back.airlocks) == len(out.airlocks)
