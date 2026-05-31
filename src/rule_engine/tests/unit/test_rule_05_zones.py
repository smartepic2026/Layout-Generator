"""L1 unit test — rule_05_zones.

검증 포인트:
    1. category별 Room ID가 정확히 분류되는가
    2. process zone 면적 비율이 40~70% 안이면 flag 없음
    3. 비율이 범위 밖이면 suspected_violation flag
    4. area_m2가 None이면 비율 검증을 skip하고 flag 없음
"""
from __future__ import annotations

import dataclasses

from src.rule_engine.models import Rationale
from src.rule_engine.rules import rule_05_zones


def test_zone_partition(minimal_rooms):
    """4개 Room 입력 시 category별로 정확히 분류."""
    rationale: list[Rationale] = []

    zones = rule_05_zones.apply(minimal_rooms, rationale)

    assert zones.process_zone == ["R_INOC", "R_CC"]
    assert zones.auxiliary_zone == ["R_MATSTORE"]
    assert zones.nc_zone == ["R_OFFICE"]


def test_skip_ratio_when_area_missing(minimal_rooms):
    """area_m2가 None이면 비율 검증 skip — flag 없음."""
    rationale: list[Rationale] = []

    rule_05_zones.apply(minimal_rooms, rationale)

    assert not rationale[0].flags
    assert rationale[0].input_facts["process_zone_ratio"] is None


def test_ratio_in_range(minimal_rooms):
    """process 면적이 50% — 40~70% 범위 안 → flag 없음."""
    # process 100+100, auxiliary 100, NC 100 → process 50%
    rooms = [
        dataclasses.replace(minimal_rooms[0], area_m2=100.0),
        dataclasses.replace(minimal_rooms[1], area_m2=100.0),
        dataclasses.replace(minimal_rooms[2], area_m2=100.0),
        dataclasses.replace(minimal_rooms[3], area_m2=100.0),
    ]
    rationale: list[Rationale] = []

    rule_05_zones.apply(rooms, rationale)

    assert not rationale[0].flags
    assert rationale[0].input_facts["process_zone_ratio"] == 0.5


def test_ratio_out_of_range_flags(minimal_rooms):
    """process 면적이 20%로 너무 작음 → suspected_violation flag."""
    rooms = [
        dataclasses.replace(minimal_rooms[0], area_m2=10.0),
        dataclasses.replace(minimal_rooms[1], area_m2=10.0),
        dataclasses.replace(minimal_rooms[2], area_m2=40.0),
        dataclasses.replace(minimal_rooms[3], area_m2=40.0),
    ]
    rationale: list[Rationale] = []

    rule_05_zones.apply(rooms, rationale)

    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "suspected_violation"
    assert "비율" in flags[0].note
