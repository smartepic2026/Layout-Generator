"""Reward function smoke + behavioral tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.drawing_agent.data import enrich_spec
from src.drawing_agent.data.tier1_ruleengine import load_external_spec
from src.drawing_agent.floorplan import generate_floorplan
from src.reward.scorer import P_DEFERRED, P_WEIGHTS, ScoreReport, score, score_spec_p_series
from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput


def test_baseline_passes_hard():
    spec = run_rule_engine(URSInput(), strict=True)
    _, layout = generate_floorplan(spec)
    r = score(spec, layout)
    assert r.passed
    assert r.total > 100  # baseline 도면이 100점 이상이어야 의미 있음


def test_score_breakdown_keys():
    spec = run_rule_engine(URSInput(), strict=True)
    _, layout = generate_floorplan(spec)
    r = score(spec, layout)
    for k in [
        "hard_penalty",
        "soft_penalty",
        "flow_separation",
        "pressure_smoothness",
        "corridor_efficiency",
        "equipment_margin",
        "area_ratio_fit",
        "aesthetics",
    ]:
        assert k in r.breakdown


def test_score_without_layout():
    """layout=None 일 때도 Hard/Soft만 평가하고 정상 동작."""
    spec = run_rule_engine(URSInput(), strict=True)
    r = score(spec, layout=None)
    # geometric quality 없음, 100 - penalty만
    assert isinstance(r, ScoreReport)
    assert "flow_separation" not in r.breakdown
    assert r.passed


def test_hard_violation_drops_score():
    """Hard constraint 위반이 있으면 점수가 baseline보다 -50 이상 낮음."""
    spec = run_rule_engine(URSInput(), strict=True)
    baseline = score(spec).total
    # 강제 위반 주입
    from src.contract.schemas import Adjacency
    spec.adjacency.append(
        Adjacency(
            from_id="R_SUPPLY_CORRIDOR",
            to_id="R_RETURN_CORRIDOR",
            relationship="door",
        )
    )
    bad = score(spec).total
    assert bad < baseline - 40


# ══════════════════════════════════════════════════════════════════════
# Phase B1 — P-series 수식 (좌표 기반, D-009)
#   원칙: 점수 = 배치 품질 (layout 좌표). 데이터 일관성은 점수가 아닌 validation.
#   layout=None → P1/P2/P7 모두 None (silent 만점 차단).
# ══════════════════════════════════════════════════════════════════════
TEAMMATE_FIXTURE = Path(__file__).parent / "fixtures" / "teammate_output_sample.json"


@pytest.fixture
def teammate_spec_with_layout():
    """팀원 fixture spec + strip-band layout (좌표 부여)."""
    spec = load_external_spec(TEAMMATE_FIXTURE.read_text(encoding="utf-8"))
    enrich_spec(spec)
    _, layout = generate_floorplan(spec)
    return spec, layout


@pytest.fixture
def engine_spec_with_layout():
    """run_rule_engine 으로 만든 baseline spec + strip-band layout."""
    spec = run_rule_engine(URSInput(), strict=False)
    from src.drawing_agent.data import enrich_spec as _enrich
    _enrich(spec)
    _, layout = generate_floorplan(spec)
    return spec, layout


def test_p_series_active_keys_present(engine_spec_with_layout):
    spec, layout = engine_spec_with_layout
    out = score_spec_p_series(spec, layout=layout)
    for k in ("P1_flow_monotonicity", "P2_adjacency", "P6_cleaning_access", "P7_compactness"):
        assert k in out
        assert "raw" in out[k]
        assert "status" in out[k]


def test_p1_p2_p7_return_none_without_layout(engine_spec_with_layout):
    """[D-009] layout=None → 좌표 없으므로 P1/P2/P7 모두 None (silent 만점 차단)."""
    spec, _ = engine_spec_with_layout
    out = score_spec_p_series(spec, layout=None)
    for k in ("P1_flow_monotonicity", "P2_adjacency", "P7_compactness"):
        assert out[k]["raw"] is None, f"{k} 가 layout 없이 점수 내면 silent 만점 버그"
        assert out[k]["status"] == "skipped_no_data"


def test_p1_p2_p7_active_with_strip_band_layout(engine_spec_with_layout):
    """strip-band layout 에서 P1/P2/P7 모두 유의미 점수 (0~1)."""
    spec, layout = engine_spec_with_layout
    out = score_spec_p_series(spec, layout=layout)
    for k in ("P1_flow_monotonicity", "P2_adjacency", "P7_compactness"):
        raw = out[k]["raw"]
        assert raw is not None, f"{k} 가 layout 있을 때 점수 측정되어야 함"
        assert 0.0 <= raw <= 1.0
        assert out[k]["status"] == "active"


def test_strip_band_is_imperfect_baseline(engine_spec_with_layout):
    """strip-band 는 격자 배치 → P1·P7 모두 1.0 미만 (CP-SAT 개선 여지 확보)."""
    spec, layout = engine_spec_with_layout
    out = score_spec_p_series(spec, layout=layout)
    assert out["P1_flow_monotonicity"]["raw"] < 1.0, "strip-band 가 P1 만점이면 수식 잘못"
    assert out["P7_compactness"]["raw"] < 1.0, "strip-band 가 P7 만점이면 수식 잘못"


def test_p_series_p6_skipped_when_clearance_missing(teammate_spec_with_layout):
    """P6 는 clearance_m 부재 → None (epistemic honesty)."""
    spec, layout = teammate_spec_with_layout
    out = score_spec_p_series(spec, layout=layout)
    assert out["P6_cleaning_access"]["raw"] is None
    assert out["P6_cleaning_access"]["status"] == "skipped_no_data"


def test_p_series_p3_p5_p8_deferred(engine_spec_with_layout):
    spec, layout = engine_spec_with_layout
    out = score_spec_p_series(spec, layout=layout)
    for k in P_DEFERRED:
        assert out[k]["status"] == "deferred"
        assert P_WEIGHTS[k] == 0.0


def test_normalized_denominator_dynamic(engine_spec_with_layout):
    """measured_denominator 는 측정된 active 가중치 합 (None 인 P6 제외)."""
    spec, layout = engine_spec_with_layout
    out = score_spec_p_series(spec, layout=layout)
    assert out["_active_denominator"] == 23.0  # 상수
    # P6 가 None → P1(10)+P2(6)+P7(3) = 19
    assert out["_measured_denominator"] == 19.0
    assert out["_normalized"] is not None


def test_p1_axis_projection_respects_sort_order(engine_spec_with_layout):
    """흐름축 투영 단조성 — sort_order 작은 장비가 PPO 시작 방 쪽에 있어야 forward."""
    spec, layout = engine_spec_with_layout
    out_layout = score_spec_p_series(spec, layout=layout)
    out_none = score_spec_p_series(spec, layout=None)
    assert out_layout["P1_flow_monotonicity"]["raw"] is not None
    assert out_none["P1_flow_monotonicity"]["raw"] is None


def test_p7_high_density_room_scores_high():
    """장비 끼리 빈틈 없이 packed + 방의 절반 차지 → P7 score 높음."""
    from src.drawing_agent.layout_solver import Layout, PlacedEquipment, PlacedRoom, Rect
    from src.contract.schemas import (
        Constraints, Equipment, FlowPaths, RangeMM, Room, RuleEngineOutput, Zones,
    )
    eq1 = Equipment(name="X1", W_mm=5000, D_mm=5000, H_mm=3000, bbox_m=[5.0, 5.0])
    eq2 = Equipment(name="X2", W_mm=5000, D_mm=5000, H_mm=3000, bbox_m=[5.0, 5.0])
    room = Room(
        id="R_TEST", name_ko="t", name_en="t", category="process",
        clean_grade="C", area_m2=100.0, equipment=[eq1, eq2],
    )
    spec = RuleEngineOutput(
        project_name="t", modality="mAb", rooms=[room], airlocks=[], adjacency=[],
        flow_paths=FlowPaths(), zones=Zones(),
        constraints=Constraints(corridor_width_mm=RangeMM()),
    )
    layout = Layout(building_w_mm=10000, building_h_mm=10000)
    # 10m x 10m 방 안에 5x5 + 5x5 장비를 좌상단 / 우상단에 인접 배치
    # envelope = 10x5 = 50m², 장비 합 = 50m², inner = 1.0
    # outer_fill = 50/100 = 0.50 → outer_score = 1.0
    # P7 = (1.0 + 1.0) / 2 = 1.0
    proom = PlacedRoom(room=room, rect=Rect(0, 0, 10000, 10000))
    proom.equipment.append(PlacedEquipment(eq1, Rect(0, 0, 5000, 5000)))
    proom.equipment.append(PlacedEquipment(eq2, Rect(5000, 0, 5000, 5000)))
    layout.rooms["R_TEST"] = proom
    out = score_spec_p_series(spec, layout=layout)
    assert out["P7_compactness"]["raw"] == pytest.approx(1.0, abs=1e-6)


def test_p7_scattered_equipment_scores_low():
    """장비 둘이 방 양 끝에 떨어져 있으면 outer_fill 크지만 inner 작음 → 점수 낮음."""
    from src.drawing_agent.layout_solver import Layout, PlacedEquipment, PlacedRoom, Rect
    from src.contract.schemas import (
        Constraints, Equipment, FlowPaths, RangeMM, Room, RuleEngineOutput, Zones,
    )
    eq1 = Equipment(name="X1", W_mm=1000, D_mm=1000, H_mm=3000, bbox_m=[1.0, 1.0])
    eq2 = Equipment(name="X2", W_mm=1000, D_mm=1000, H_mm=3000, bbox_m=[1.0, 1.0])
    room = Room(
        id="R_TEST", name_ko="t", name_en="t", category="process",
        clean_grade="C", area_m2=100.0, equipment=[eq1, eq2],
    )
    spec = RuleEngineOutput(
        project_name="t", modality="mAb", rooms=[room], airlocks=[], adjacency=[],
        flow_paths=FlowPaths(), zones=Zones(),
        constraints=Constraints(corridor_width_mm=RangeMM()),
    )
    layout = Layout(building_w_mm=10000, building_h_mm=10000)
    proom = PlacedRoom(room=room, rect=Rect(0, 0, 10000, 10000))
    proom.equipment.append(PlacedEquipment(eq1, Rect(0, 0, 1000, 1000)))
    proom.equipment.append(PlacedEquipment(eq2, Rect(9000, 9000, 1000, 1000)))
    layout.rooms["R_TEST"] = proom
    out = score_spec_p_series(spec, layout=layout)
    # envelope = 10x10 = 100m², 장비 합 = 2m², inner = 0.02
    # outer_fill = 1.0 → outer_score = max(0, 1 - 0.5/0.4) = 0
    # P7 = (0.02 + 0) / 2 = 0.01
    assert out["P7_compactness"]["raw"] < 0.1


def test_p2_distant_group_members_score_lower():
    """같은 co_locate_group 멤버가 멀리 떨어져 있으면 P2 group_term 낮음."""
    from src.drawing_agent.layout_solver import Layout, PlacedEquipment, PlacedRoom, Rect
    from src.contract.schemas import (
        Constraints, Equipment, FlowPaths, RangeMM, Room, RuleEngineOutput, Zones,
    )
    eq1 = Equipment(name="X1", W_mm=1000, D_mm=1000, H_mm=3000,
                    bbox_m=[1.0, 1.0], co_locate_group="G")
    eq2 = Equipment(name="X2", W_mm=1000, D_mm=1000, H_mm=3000,
                    bbox_m=[1.0, 1.0], co_locate_group="G")
    room = Room(
        id="R_TEST", name_ko="t", name_en="t", category="process",
        clean_grade="C", area_m2=400.0, equipment=[eq1, eq2],
    )
    spec = RuleEngineOutput(
        project_name="t", modality="mAb", rooms=[room], airlocks=[], adjacency=[],
        flow_paths=FlowPaths(product_process_order=["R_TEST"]), zones=Zones(),
        constraints=Constraints(corridor_width_mm=RangeMM()),
    )
    # 두 layout 비교: 가까이 vs 멀리
    def build(d):
        layout = Layout(building_w_mm=20000, building_h_mm=20000)
        proom = PlacedRoom(room=room, rect=Rect(0, 0, 20000, 20000))
        proom.equipment.append(PlacedEquipment(eq1, Rect(0, 0, 1000, 1000)))
        proom.equipment.append(PlacedEquipment(eq2, Rect(d, 0, 1000, 1000)))
        layout.rooms["R_TEST"] = proom
        return layout
    close = score_spec_p_series(spec, layout=build(2000))["P2_adjacency"]["raw"]
    far = score_spec_p_series(spec, layout=build(19000))["P2_adjacency"]["raw"]
    assert close > far
    assert far < 1.0
