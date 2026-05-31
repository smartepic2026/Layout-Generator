"""L1 unit test — rule_10_equipment."""
from __future__ import annotations

import dataclasses

from src.rule_engine.models import Equipment, Rationale
from src.rule_engine.rules import rule_10_equipment


def _eq(name: str, process_no_list: list[str]) -> Equipment:
    return Equipment(
        instance_id=name, name=name,
        width_mm=2000, depth_mm=2000, height_mm=2000,
        weight_kg=None, max_operating_weight_kg=None,
        process_no=process_no_list,
    )


def test_sort_by_process_no(minimal_rooms, empty_input):
    """역순으로 입력한 장비가 P1-1 → P1-2 → P2-1 순서로 정렬."""
    eqs = [
        _eq("Mix Tank", ["P2-1. 버퍼 제조"]),
        _eq("Weigh booth", ["P1-1. 배지 원료 칭량"]),
        _eq("Filter", ["P1-2. 배지 여과"]),
    ]
    target = dataclasses.replace(minimal_rooms[1], equipment=eqs)
    rationale: list[Rationale] = []

    result = rule_10_equipment.apply([target], empty_input, rationale)

    names = [e.name for e in result[0].equipment]
    assert names == ["Weigh booth", "Filter", "Mix Tank"]


def test_unmapped_goes_to_end(minimal_rooms, empty_input):
    """process_no 없는 장비는 뒤로."""
    eqs = [
        _eq("Unmapped", []),
        _eq("Weigh booth", ["P1-1"]),
    ]
    target = dataclasses.replace(minimal_rooms[1], equipment=eqs)
    rationale: list[Rationale] = []

    result = rule_10_equipment.apply([target], empty_input, rationale)

    names = [e.name for e in result[0].equipment]
    assert names == ["Weigh booth", "Unmapped"]


def test_flag_for_unmapped_in_process_room(minimal_rooms, empty_input):
    """공정 Room에 process_no 없는 장비 → info flag."""
    eqs = [_eq("Mystery", [])]
    target = dataclasses.replace(
        minimal_rooms[0], category="process", equipment=eqs
    )
    rationale: list[Rationale] = []

    rule_10_equipment.apply([target], empty_input, rationale)

    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "info"


def test_no_flag_for_unmapped_in_auxiliary(minimal_rooms, empty_input):
    """보조 Room의 unmapped 장비는 flag 없음 (storage 등은 정상)."""
    eqs = [_eq("Deep freezer", [])]
    target = dataclasses.replace(
        minimal_rooms[2], category="auxiliary", equipment=eqs
    )
    rationale: list[Rationale] = []

    rule_10_equipment.apply([target], empty_input, rationale)

    assert not rationale[0].flags


def test_count_in_decision(minimal_rooms, empty_input):
    """rationale.decision에 정렬된 장비 수 명시."""
    eqs = [_eq(f"E{i}", [f"P1-{i}"]) for i in range(1, 4)]
    target = dataclasses.replace(minimal_rooms[1], equipment=eqs)
    rationale: list[Rationale] = []

    rule_10_equipment.apply([target], empty_input, rationale)

    assert "sorted 3" in rationale[0].decision
