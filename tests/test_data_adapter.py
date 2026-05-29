"""4-tier data adapter 동작 검증 (Phase A1).

테스트 범위:
  - tier3 derive 단위 함수: parse_sort_order, derive_bbox_m
  - enrich_spec 전체 흐름 (4-tier 순차)
  - source 태그가 올바른 tier 로 기록되는지
  - idempotency (재호출 시 중복 채움 없음)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.drawing_agent.data import enrich_spec
from src.drawing_agent.data.tier3_derive import derive_bbox_m, parse_sort_order
from src.rule_engine.schemas import RuleEngineOutput


# ── tier3 단위 함수 ──
def test_parse_sort_order_phase_seq():
    assert parse_sort_order("P1-1") == 11
    assert parse_sort_order("P1-2") == 12
    assert parse_sort_order("P10-3") == 103


def test_parse_sort_order_fallback():
    assert parse_sort_order("USP-30") == 30
    assert parse_sort_order("step42") == 42


def test_parse_sort_order_none():
    assert parse_sort_order(None) is None
    assert parse_sort_order("") is None
    assert parse_sort_order("nodigits") is None


def test_derive_bbox_m():
    assert derive_bbox_m(3000, 2000) == [3.0, 2.0]
    assert derive_bbox_m(1500, 750) == [1.5, 0.75]


# ── adapter 전체 흐름 ──
@pytest.fixture
def baseline_spec() -> RuleEngineOutput:
    path = Path("output/spec_v4.json")
    if not path.exists():
        pytest.skip("output/spec_v4.json missing — run cli rule-engine first")
    return RuleEngineOutput.model_validate_json(path.read_text())


def test_enrich_fills_bbox_m_for_all(baseline_spec):
    """bbox_m 은 모든 장비에 채워짐 (W_mm/D_mm 무조건 있으니까)."""
    enrich_spec(baseline_spec)
    for r in baseline_spec.rooms:
        for eq in r.equipment:
            assert eq.bbox_m is not None
            assert len(eq.bbox_m) == 2


def test_enrich_fills_sort_order_when_process_step_exists(baseline_spec):
    """sort_order 는 process_step 있는 장비만 채워짐."""
    enrich_spec(baseline_spec)
    for r in baseline_spec.rooms:
        for eq in r.equipment:
            if eq.process_step:
                assert eq.sort_order is not None and eq.sort_order > 0
            # process_step 없는 장비(autoclave 등)는 None 유지 — OK


def test_enrich_connects_to_same_room_chain(baseline_spec):
    """sort_order 가 연속인 같은 방 장비 사이에 chain 이 생긴다."""
    enrich_spec(baseline_spec)
    found_chain = False
    for r in baseline_spec.rooms:
        for eq in r.equipment:
            if eq.connects_to:
                found_chain = True
                # connects_to 의 대상은 같은 방 안에 있는 장비여야 함
                names_in_room = {e.name for e in r.equipment}
                for target in eq.connects_to:
                    assert target in names_in_room, (
                        f"connects_to 가 방 밖 장비 가리킴: {eq.name} → {target}"
                    )
    assert found_chain, "어느 방에도 same-room chain 안 만들어짐"


def test_source_tags_recorded(baseline_spec):
    """tier3 가 채운 필드는 source 태그가 tier3_derive."""
    tracker = enrich_spec(baseline_spec)
    assert "tier3_derive" in tracker.per_tier_stats
    stat = tracker.per_tier_stats["tier3_derive"]
    assert stat.get("bbox_m", 0) > 0
    assert stat.get("sort_order", 0) > 0
    # 모든 enrich 한 필드는 source 가 기록되어야 함
    for room in baseline_spec.rooms:
        for idx, eq in enumerate(room.equipment):
            if eq.bbox_m is not None:
                assert tracker.get(room.id, idx, "bbox_m") is not None


def test_idempotent(baseline_spec):
    """두 번 호출해도 추가로 채우는 거 없음."""
    enrich_spec(baseline_spec)
    tracker2 = enrich_spec(baseline_spec)
    # 두 번째 호출은 모든 필드가 이미 차 있으니 tier3 가 0 채움
    if "tier3_derive" in tracker2.per_tier_stats:
        stat = tracker2.per_tier_stats["tier3_derive"]
        assert stat.get("sort_order", 0) == 0
        assert stat.get("bbox_m", 0) == 0
        assert stat.get("connects_to", 0) == 0


def test_no_cross_room_chain(baseline_spec):
    """Phase A1 의 핵심 제약: cross-room link 는 만들지 않음.

    같은 방 안 sort_order chain 만. 검수자 없는 cross-room 추론값은
    Phase B 에서 P2 수식 만들 때 검증과 함께.
    """
    enrich_spec(baseline_spec)
    for room in baseline_spec.rooms:
        names_in_room = {eq.name for eq in room.equipment}
        for eq in room.equipment:
            for target in eq.connects_to:
                assert target in names_in_room, (
                    f"Phase A1 위반: cross-room link 가 derive 됨 — "
                    f"{room.id}/{eq.name} → {target}"
                )


# ══════════════════════════════════════════════════════════════════════
# D-003 anti-corruption layer (tier1_ruleengine 변환)
# ══════════════════════════════════════════════════════════════════════
from src.drawing_agent.data import load_external_spec, parse_dimensions
from src.drawing_agent.data.tier1_ruleengine import (
    _adapt_equipment, _adapt_room, _adapt_adjacency, _adapt_airlock,
    _adapt_rationale,
)


def test_parse_dimensions_basic():
    assert parse_dimensions("3500×3000×3000") == (3500, 3000, 3000)
    assert parse_dimensions("3500x3000x3000") == (3500, 3000, 3000)
    assert parse_dimensions("3500X3000X3000") == (3500, 3000, 3000)
    assert parse_dimensions("3500*3000*3000") == (3500, 3000, 3000)


def test_parse_dimensions_with_comma():
    assert parse_dimensions("3,000×2,500×4,000") == (3000, 2500, 4000)


def test_parse_dimensions_invalid():
    assert parse_dimensions(None) == (None, None, None)
    assert parse_dimensions("") == (None, None, None)
    assert parse_dimensions("not numbers") == (None, None, None)


def test_adapt_equipment_combined_wxdxh():
    eq = _adapt_equipment({
        "name": "Mixing Tank",
        "W×D×H(mm)": "3500×3000×3000",
        "weight": 500, "max_op": 600,
    })
    assert eq["W_mm"] == 3500 and eq["D_mm"] == 3000 and eq["H_mm"] == 3000
    assert eq["weight_kg"] == 500 and eq["max_op_weight_kg"] == 600


def test_adapt_equipment_process_no_alias():
    eq = _adapt_equipment({"name": "X", "process_no": "P1-2"})
    assert eq["process_step"] == "P1-2"


def test_adapt_equipment_name_strip():
    eq = _adapt_equipment({"name": "  Weigh booth  "})
    assert eq["name"] == "Weigh booth"


def test_adapt_room_field_mapping():
    r = _adapt_room({
        "room_id": "R_X", "name_ko": "방", "name_en": "Room",
        "cat": "process", "grade": "C", "area_m2": 50,
        "DP": 30, "ACPH": 30, "color": "yellow", "투명%": 50,
        "gowning": "무진복",
    })
    assert r["id"] == "R_X"
    assert r["category"] == "process"
    assert r["clean_grade"] == "C"
    assert r["differential_pressure_Pa"] == 30
    assert r["air_changes_per_hour"] == 30
    assert r["background_color"] == "yellow"
    assert r["transparency_pct"] == 50
    assert r["gowning_type"] == "무진복"


def test_adapt_room_trailing_space_strip():
    r = _adapt_room({
        "room_id": "R_X ", "name_ko": "방 ", "name_en": "Cell Culture ",
        "cat": "process", "grade": "C", "area_m2": 1,
    })
    assert r["id"] == "R_X"
    assert r["name_en"] == "Cell Culture"
    assert r["name_ko"] == "방"


def test_adapt_airlock_field_mapping():
    a = _adapt_airlock({
        "al_id": "AL_X", "kind": "PAL_in", "grade": "C", "DP": 25,
        "area_m2": 6.0, "flow_type": "cascade",
        "connects_higher": "R_A", "connects_lower": "R_B", "purpose": "personnel_entry",
    })
    assert a["id"] == "AL_X"
    assert a["type"] == "PAL_in"
    assert a["clean_grade"] == "C"
    assert a["differential_pressure_Pa"] == 25


def test_adapt_adjacency_doors_door_size():
    a = _adapt_adjacency({
        "from_id": "R_A", "to_id": "R_B", "relationship": "door",
        "doors": 2, "door_size": 1500, "flow_direction": "bidirectional",
    })
    assert a["door_count"] == 2
    assert a["door_size_mm"] == 1500


def test_adapt_adjacency_swing_to_notes():
    """swing 은 의미가 Room id 가 아니라 방향 descriptor 라 notes 로 보존."""
    a = _adapt_adjacency({
        "from_id": "R_A", "to_id": "R_B", "relationship": "door",
        "swing": "high_pressure_side", "flow_direction": "one_way_in",
    })
    assert "swing=high_pressure_side" in a["notes"]
    assert "swing" not in a   # 원래 키는 사라져야


def test_adapt_rationale_severity_note():
    r = _adapt_rationale({
        "rule_id": "rule_10", "target_id": "R_X",
        "severity": "info", "note": "공정 외 장비",
    })
    assert r["target"] == "R_X"
    assert "info" in r["decision"]
    assert r["reason"] == "공정 외 장비"


def test_load_external_spec_extra_meta_ignored():
    """최상위 meta 같은 모르는 필드는 extra='ignore' 가 흡수해야 한다."""
    import json
    raw = json.dumps({
        "meta": {"engine_version": "0.1.0"},
        "project_name": "test", "modality": "mAb",
        "rooms": [], "airlocks": [], "adjacency": [],
        "flow_paths": {"personnel_entry": [], "personnel_exit": [],
                       "material_entry": [], "waste_exit": [],
                       "product_process_order": []},
        "zones": {"process_zone": [], "auxiliary_zone": [], "nc_zone": []},
        "constraints": {"corridor_width_mm": {"min": 1500}},
        "rationale": [],
    })
    spec = load_external_spec(raw)
    assert spec.project_name == "test"


# ══════════════════════════════════════════════════════════════════════
# S1 / S4 silent failure 차단
# ══════════════════════════════════════════════════════════════════════
def test_area_ratio_fit_returns_none_when_no_data():
    """S1: layout 없고 'current' 키도 없으면 None (이전엔 silent 0.5 default)."""
    from src.reward.scorer import _area_ratio_fit
    from src.rule_engine.schemas import RuleEngineOutput
    spec = RuleEngineOutput.model_validate({
        "project_name": "t", "modality": "mAb",
        "rooms": [], "airlocks": [], "adjacency": [],
        "flow_paths": {"personnel_entry": [], "personnel_exit": [],
                       "material_entry": [], "waste_exit": [],
                       "product_process_order": []},
        "zones": {"process_zone": [], "auxiliary_zone": [], "nc_zone": []},
        "constraints": {"corridor_width_mm": {"min": 1500},
                        "process_zone_area_ratio": {"min": 0.4, "max": 0.7}},
        "rationale": [],
    })
    assert _area_ratio_fit(spec, layout=None) is None


def test_pressure_cascade_smoothness_returns_none_when_all_dp_zero():
    """S4: 모든 Room.DP=0 이면 None (이전엔 silent 1.0 만점)."""
    from src.reward.scorer import _pressure_cascade_smoothness
    from src.rule_engine.schemas import RuleEngineOutput
    spec = RuleEngineOutput.model_validate({
        "project_name": "t", "modality": "mAb",
        "rooms": [
            {"id": "R_A", "name_ko": "a", "name_en": "a", "category": "process",
             "clean_grade": "C", "area_m2": 10, "differential_pressure_Pa": 0},
        ],
        "airlocks": [], "adjacency": [],
        "flow_paths": {"personnel_entry": [], "personnel_exit": [],
                       "material_entry": [], "waste_exit": [],
                       "product_process_order": []},
        "zones": {"process_zone": [], "auxiliary_zone": [], "nc_zone": []},
        "constraints": {"corridor_width_mm": {"min": 1500}},
        "rationale": [],
    })
    assert _pressure_cascade_smoothness(spec, layout=None) is None
