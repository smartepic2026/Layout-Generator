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
