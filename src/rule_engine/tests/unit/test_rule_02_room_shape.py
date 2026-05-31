"""L1 unit test — rule_02_room_shape."""
from __future__ import annotations

import dataclasses
import math

from src.rule_engine.models import Equipment, Rationale
from src.rule_engine.rules import rule_02_room_shape


def test_area_100_no_equipment(minimal_rooms, empty_input):
    """100 m² + 장비 없음 → default aspect 1.5 → w≈12247, d≈8165."""
    target = dataclasses.replace(minimal_rooms[0], area_m2=100.0)
    rationale: list[Rationale] = []

    result = rule_02_room_shape.apply([target], empty_input, rationale)

    r = result[0]
    assert r.width_mm is not None and r.depth_mm is not None
    # area는 area_m2와 거의 같아야 함 (반올림 차이 약간 허용).
    actual_area = r.width_mm * r.depth_mm / 1_000_000
    assert abs(actual_area - 100.0) < 1.0
    # aspect 1.5 가정 → w/d == 1.5.
    assert abs(r.width_mm / r.depth_mm - 1.5) < 0.01


def test_existing_w_d_preserved(minimal_rooms, empty_input):
    """이미 width_mm·depth_mm가 채워져 있으면 derive 안 함."""
    target = dataclasses.replace(
        minimal_rooms[0], area_m2=100.0, width_mm=10000, depth_mm=10000
    )
    rationale: list[Rationale] = []

    result = rule_02_room_shape.apply([target], empty_input, rationale)

    assert result[0].width_mm == 10000
    assert result[0].depth_mm == 10000


def test_no_area_no_derive(minimal_rooms, empty_input):
    """area_m2=None이면 width·depth 모두 None 유지."""
    target = dataclasses.replace(minimal_rooms[0], area_m2=None)
    rationale: list[Rationale] = []

    result = rule_02_room_shape.apply([target], empty_input, rationale)

    assert result[0].width_mm is None
    assert result[0].depth_mm is None


def test_aspect_clamped_to_max(minimal_rooms, empty_input):
    """장비 W 합이 매우 크더라도 aspect는 2.0 상한."""
    huge_eqs = [
        Equipment(instance_id=f"E{i}", name="X",
                  width_mm=10000, depth_mm=1000, height_mm=2000,
                  weight_kg=None, max_operating_weight_kg=None,
                  process_no=[])
        for i in range(10)
    ]
    target = dataclasses.replace(
        minimal_rooms[0], area_m2=200.0, equipment=huge_eqs
    )
    rationale: list[Rationale] = []

    result = rule_02_room_shape.apply([target], empty_input, rationale)

    r = result[0]
    aspect = r.width_mm / r.depth_mm
    assert aspect <= 2.01


def test_flag_when_room_too_shallow(minimal_rooms, empty_input):
    """area가 너무 작아서 max 장비 depth가 안 들어가면 flag."""
    # 장비 D=3000인데 Room area 5 m² → d≈2000 으로 들어갈 수 없음.
    eq = Equipment(
        instance_id="BIG", name="Big tank",
        width_mm=2000, depth_mm=3000, height_mm=3000,
        weight_kg=None, max_operating_weight_kg=None, process_no=[],
    )
    target = dataclasses.replace(
        minimal_rooms[0], area_m2=5.0, equipment=[eq]
    )
    rationale: list[Rationale] = []

    rule_02_room_shape.apply([target], empty_input, rationale)

    assert any(
        f.severity == "suspected_violation"
        for f in rationale[0].flags
    )


def test_rationale_per_room(minimal_rooms, empty_input):
    """4개 Room → 4개 rationale 항목."""
    rooms = [
        dataclasses.replace(r, area_m2=50.0) for r in minimal_rooms
    ]
    rationale: list[Rationale] = []

    rule_02_room_shape.apply(rooms, empty_input, rationale)

    assert len(rationale) == 4
    assert all(r.rule_id == "rule_02_room_shape" for r in rationale)
