"""L1 unit test — derive/rooms_selector.

검증 포인트:
    1. URS dict 1개 → Room 객체 1개로 변환
    2. 한글 category ("주공정 구역" 등)가 영문으로 정확히 매핑
    3. force_exclude된 Room은 결과에 없음
    4. force_include인데 URS에 없는 Room은 warning flag
    5. urs_equipment가 Room name_en으로 정확히 그룹화되어 Equipment 리스트로 부착
    6. derive 필드(area_m2 등)는 None, ACPH는 URS 값 통과
    7. room_id가 R_UPPER_UNDERSCORED 형식으로 생성됨
"""
from __future__ import annotations

import dataclasses

from src.rule_engine.derive import select_required_rooms
from src.rule_engine.models import Rationale


def _make_urs_room(name_en: str, **overrides) -> dict:
    """기본값으로 채운 URS Room dict."""
    base = {
        "name_ko": name_en,
        "name_en": name_en,
        "category": "주공정 구역",
        "clean_grade": "C",
        "room_flow": "One-way",
        "gowning_type": "무진복",
        "process_no": ["P1-1"],
        "air_changes_per_hour": 30,
    }
    base.update(overrides)
    return base


def test_basic_conversion(empty_input):
    """URS dict 1개 → Room 1개."""
    inp = dataclasses.replace(
        empty_input,
        urs_rooms=[_make_urs_room("Inoculation", clean_grade="B", gowning_type="무균복")],
    )
    rationale: list[Rationale] = []

    rooms = select_required_rooms(inp, rationale)

    assert len(rooms) == 1
    r = rooms[0]
    assert r.name_en == "Inoculation"
    assert r.room_id == "R_INOCULATION"
    assert r.category == "process"
    assert r.clean_grade == "B"
    assert r.air_changes_per_hour == 30.0
    # derive 필드는 None.
    assert r.area_m2 is None
    assert r.differential_pressure_Pa is None
    assert r.background_color is None


def test_category_korean_to_english(empty_input):
    """한글 카테고리 매핑."""
    inp = dataclasses.replace(empty_input, urs_rooms=[
        _make_urs_room("Inoculation", category="주공정 구역"),
        _make_urs_room("Material storage", category="보조 구역", clean_grade="D",
                       gowning_type="스크럽"),
        _make_urs_room("Office", category="NC 구역", clean_grade="NC",
                       gowning_type="일상복"),
    ])
    rationale: list[Rationale] = []

    rooms = select_required_rooms(inp, rationale)

    cats = [r.category for r in rooms]
    assert cats == ["process", "auxiliary", "NC"]


def test_unknown_category_skipped_with_flag(empty_input):
    """알 수 없는 카테고리는 skip되고 warning flag."""
    inp = dataclasses.replace(empty_input, urs_rooms=[
        _make_urs_room("X", category="이상한구역"),
    ])
    rationale: list[Rationale] = []

    rooms = select_required_rooms(inp, rationale)

    assert rooms == []
    flags = rationale[0].flags
    assert len(flags) == 1
    assert "알 수 없는 category" in flags[0].note


def test_force_exclude(empty_input):
    """force_exclude된 Room은 결과에서 제거."""
    overrides = dataclasses.replace(
        empty_input.overrides, force_exclude_rooms=["Office"]
    )
    inp = dataclasses.replace(
        empty_input,
        urs_rooms=[
            _make_urs_room("Inoculation"),
            _make_urs_room("Office", category="NC 구역", clean_grade="NC"),
        ],
        overrides=overrides,
    )
    rationale: list[Rationale] = []

    rooms = select_required_rooms(inp, rationale)

    names = [r.name_en for r in rooms]
    assert "Office" not in names
    assert "Inoculation" in names


def test_force_include_missing_warns(empty_input):
    """force_include에 명시된 Room이 URS에 없으면 warning flag."""
    overrides = dataclasses.replace(
        empty_input.overrides, force_include_rooms=["Lyophilizer"]
    )
    inp = dataclasses.replace(
        empty_input,
        urs_rooms=[_make_urs_room("Inoculation")],
        overrides=overrides,
    )
    rationale: list[Rationale] = []

    select_required_rooms(inp, rationale)

    flags = rationale[0].flags
    assert any("force_include" in f.note and "Lyophilizer" in f.note for f in flags)


def test_equipment_grouping(empty_input):
    """urs_equipment가 Room name_en으로 그룹화."""
    inp = dataclasses.replace(
        empty_input,
        urs_rooms=[
            _make_urs_room("Media preparation"),
            _make_urs_room("Buffer preparation"),
        ],
        urs_equipment=[
            {"room_en": "Media preparation", "instance_id": "MT-1",
             "name": "Mixing Tank 100L", "W": 2000, "D": 2000, "H": 2000,
             "weight_kg": 1000, "max_operating_weight_kg": 1100,
             "process_no": ["P1-2"]},
            {"room_en": "Media preparation", "instance_id": "WB-1",
             "name": "Weigh booth", "W": 3500, "D": 3000, "H": 3000,
             "weight_kg": 500, "max_operating_weight_kg": 600,
             "process_no": ["P1-1"]},
            {"room_en": "Buffer preparation", "instance_id": "MT-5",
             "name": "Mixing Tank 500L", "W": 2500, "D": 2000, "H": 3000,
             "weight_kg": 1500, "max_operating_weight_kg": 2000,
             "process_no": ["P2-2"]},
        ],
    )
    rationale: list[Rationale] = []

    rooms = select_required_rooms(inp, rationale)

    media = next(r for r in rooms if r.name_en == "Media preparation")
    buffer = next(r for r in rooms if r.name_en == "Buffer preparation")
    assert len(media.equipment) == 2
    assert {eq.instance_id for eq in media.equipment} == {"MT-1", "WB-1"}
    assert len(buffer.equipment) == 1
    assert buffer.equipment[0].instance_id == "MT-5"
    assert buffer.equipment[0].width_mm == 2500


def test_room_id_slugify(empty_input):
    """영문명 → R_UPPER_UNDERSCORED 식별자."""
    inp = dataclasses.replace(empty_input, urs_rooms=[
        _make_urs_room("Purification 1"),
        _make_urs_room("MAL-in Cell Culture", category="주공정 구역"),
    ])
    rationale: list[Rationale] = []

    rooms = select_required_rooms(inp, rationale)

    ids = [r.room_id for r in rooms]
    assert ids == ["R_PURIFICATION_1", "R_MAL_IN_CELL_CULTURE"]


def test_rationale_emitted(empty_input):
    """반드시 rationale에 1줄 추가."""
    inp = dataclasses.replace(empty_input, urs_rooms=[
        _make_urs_room("Inoculation"),
        _make_urs_room("Cell Culture"),
    ])
    rationale: list[Rationale] = []

    select_required_rooms(inp, rationale)

    assert len(rationale) == 1
    entry = rationale[0]
    assert entry.rule_id == "rooms_selector"
    assert entry.input_facts["urs_room_count"] == 2
    assert "selected 2 rooms" in entry.decision
