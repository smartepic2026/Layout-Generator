"""L1 unit test — rule_12_nc_rooms."""
from __future__ import annotations

import dataclasses

from src.rule_engine.models import Rationale, Zones
from src.rule_engine.rules import rule_12_nc_rooms


def _make_room(rid, name_en, category="NC", grade="NC"):
    """Test용 NC Room 생성 — conftest의 minimal_rooms를 응용."""
    from rule_engine.models import Room
    return Room(
        room_id=rid, name_ko=name_en, name_en=name_en,
        category=category, clean_grade=grade,
        room_flow="Both-way", gowning_type="일상복",
        gowning_method=None, equipment=[], process_no=[],
        area_m2=None, width_mm=None, depth_mm=None,
        ceiling_height_mm=None, volume_m3=None,
        differential_pressure_Pa=None, air_changes_per_hour=None,
        recovery_time_min=None, background_color=None,
        transparency_pct=None, well_type_ceiling=False,
    )


def test_full_onsite_keeps_all(empty_input):
    """모든 NC 옵션이 True면 nc_zone 그대로."""
    rooms = [
        _make_room("R_OFFICE", "Office"),
        _make_room("R_TOILET", "Toilet (Female)"),
        _make_room("R_MON", "Monitoring"),
        _make_room("R_LOBBY", "Lobby"),
    ]
    zones = Zones(process_zone=[], auxiliary_zone=[],
                  nc_zone=[r.room_id for r in rooms])
    rationale: list[Rationale] = []

    out = rule_12_nc_rooms.apply(zones, rooms, empty_input, rationale)

    assert out.nc_zone == zones.nc_zone


def test_office_offsite_removes_only_office(empty_input):
    """include_office_onsite=False면 Office만 제거."""
    rooms = [
        _make_room("R_OFFICE", "Office"),
        _make_room("R_TOILET", "Toilet (Female)"),
        _make_room("R_LOBBY", "Lobby"),
    ]
    zones = Zones(process_zone=[], auxiliary_zone=[],
                  nc_zone=[r.room_id for r in rooms])
    org = dataclasses.replace(empty_input.organization, include_office_onsite=False)
    inp = dataclasses.replace(empty_input, organization=org)
    rationale: list[Rationale] = []

    out = rule_12_nc_rooms.apply(zones, rooms, inp, rationale)

    assert "R_OFFICE" not in out.nc_zone
    assert "R_TOILET" in out.nc_zone
    assert "R_LOBBY" in out.nc_zone


def test_all_offsite_empties_nc_zone(empty_input):
    """모든 NC 옵션 False면 nc_zone 비워짐."""
    rooms = [
        _make_room("R_OFFICE", "Office"),
        _make_room("R_TOILET", "Toilet (Male)"),
        _make_room("R_MON", "Monitoring"),
        _make_room("R_LOBBY", "Lobby"),
        _make_room("R_LOUNGE", "Lounge"),
    ]
    zones = Zones(process_zone=[], auxiliary_zone=[],
                  nc_zone=[r.room_id for r in rooms])
    org = dataclasses.replace(
        empty_input.organization,
        include_office_onsite=False, include_toilet_onsite=False,
        include_monitoring_room_onsite=False, include_lobby_onsite=False,
    )
    inp = dataclasses.replace(empty_input, organization=org)
    rationale: list[Rationale] = []

    out = rule_12_nc_rooms.apply(zones, rooms, inp, rationale)

    assert out.nc_zone == []
    # info flag가 5개 (5개 제거).
    info_flags = [f for f in rationale[0].flags if f.severity == "info"]
    assert len(info_flags) == 5


def test_other_zones_preserved(empty_input):
    """process/auxiliary zone은 손대지 않음."""
    rooms = [_make_room("R_OFFICE", "Office")]
    zones = Zones(
        process_zone=["R_X", "R_Y"],
        auxiliary_zone=["R_Z"],
        nc_zone=["R_OFFICE"],
    )
    org = dataclasses.replace(empty_input.organization, include_office_onsite=False)
    inp = dataclasses.replace(empty_input, organization=org)
    rationale: list[Rationale] = []

    out = rule_12_nc_rooms.apply(zones, rooms, inp, rationale)

    assert out.process_zone == ["R_X", "R_Y"]
    assert out.auxiliary_zone == ["R_Z"]
    assert out.nc_zone == []
