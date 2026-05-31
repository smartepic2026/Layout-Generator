"""L1 unit test — rule_11_wash_prep."""
from __future__ import annotations

from src.rule_engine.models import AdjacencyEdge, Rationale, Room
from src.rule_engine.rules import rule_11_wash_prep


def _room(rid, name_en):
    return Room(
        room_id=rid, name_ko=name_en, name_en=name_en,
        category="process", clean_grade="C", room_flow="Both-way",
        gowning_type="무진복", gowning_method=None, equipment=[],
        process_no=[], area_m2=60.0, width_mm=None, depth_mm=None,
        ceiling_height_mm=None, volume_m3=None,
        differential_pressure_Pa=None, air_changes_per_hour=None,
        recovery_time_min=None, background_color=None,
        transparency_pct=None, well_type_ceiling=False,
    )


def test_passthrough_edge_added():
    """Washing + Preparation 둘 다 있으면 passthrough_only 엣지 추가."""
    rooms = [_room("R_WASH", "Washing"), _room("R_PREP", "Preparation")]
    rationale: list[Rationale] = []

    out = rule_11_wash_prep.apply([], rooms, rationale)

    pts = [e for e in out if e.relationship == "passthrough_only"]
    assert len(pts) == 1
    assert {pts[0].from_id, pts[0].to_id} == {"R_WASH", "R_PREP"}
    assert pts[0].door_count == 0


def test_info_flag_when_added():
    """엣지 추가 시 사람 통행 차단 안내 info flag."""
    rooms = [_room("R_WASH", "Washing"), _room("R_PREP", "Preparation")]
    rationale: list[Rationale] = []

    rule_11_wash_prep.apply([], rooms, rationale)

    flags = rationale[0].flags
    assert len(flags) == 1
    assert flags[0].severity == "info"
    assert "사람 직접 통행을 차단" in flags[0].note


def test_skipped_when_missing_room():
    """Washing이나 Preparation이 없으면 skip."""
    rooms = [_room("R_WASH", "Washing")]  # Preparation 없음
    rationale: list[Rationale] = []

    out = rule_11_wash_prep.apply([], rooms, rationale)

    assert all(e.relationship != "passthrough_only" for e in out)
    assert "skipped" in rationale[0].decision


def test_no_duplicate_edge():
    """이미 passthrough_only 엣지가 있으면 추가하지 않음."""
    rooms = [_room("R_WASH", "Washing"), _room("R_PREP", "Preparation")]
    existing = AdjacencyEdge(
        from_id="R_WASH", to_id="R_PREP",
        relationship="passthrough_only",
        door_count=0, door_size_mm=None, door_swing_target=None,
        flow_direction="bidirectional", is_elevator_constraint=False,
    )
    rationale: list[Rationale] = []

    out = rule_11_wash_prep.apply([existing], rooms, rationale)

    pts = [e for e in out if e.relationship == "passthrough_only"]
    assert len(pts) == 1  # 중복 추가 안 됨
    assert "already exists" in rationale[0].decision
