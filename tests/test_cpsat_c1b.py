"""C1b — P-series surrogate 목적함수 회귀 (D-017).

검증:
  1. C1b 가 mab_8000L 28방 FEASIBLE / OPTIMAL 도달.
  2. P-series surrogate 적용 후에도 hard 제약 (안 겹침, 캔버스, adjacency) 유지.
  3. 결정론 — 두 번 풀이 같은 좌표.
  4. layout 에 strip-band 장비 packing 적용 시 P-series 점수 측정 가능.
  5. P1-only weight 설정으로 작은 시나리오 (A_small) 에서 strip-band 보다 향상.
  6. strip-band / C0 / C1a 보존.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ortools = pytest.importorskip("ortools")

from src.drawing_agent.cpsat_solver import solve_c1a, solve_c1b
from src.drawing_agent.data import enrich_spec, resolve_building_dims
from src.drawing_agent.layout_solver import (
    Layout,
    PlacedRoom,
    Rect,
    _place_equipment_grid,
    solve,
)
from src.drawing_agent.renderer import render
from src.reward.scorer import score_spec_p_series
from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput


@pytest.fixture(scope="module")
def setup_8000L():
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    bw, bh, _ = resolve_building_dims(spec, urs_path=None)
    return spec, int(bw), int(bh)


def test_c1b_solves_feasible(setup_8000L):
    spec, bw, bh = setup_8000L
    layout, rep = solve_c1b(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=3.0)
    assert rep.status in ("OPTIMAL", "FEASIBLE")
    assert len(layout.rooms) == len(spec.rooms)


def test_c1b_hard_constraints_preserved(setup_8000L):
    """surrogate objective 가 hard 제약 (안 겹침/캔버스/adjacency) 깨지 않음."""
    spec, bw, bh = setup_8000L
    layout, rep = solve_c1b(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=3.0)
    # 안 겹침 + 캔버스 안
    rects = list(layout.rooms.values())
    for i in range(len(rects)):
        r = rects[i].rect
        assert 0 <= r.x and r.x2 <= bw
        for j in range(i + 1, len(rects)):
            o = rects[j].rect
            assert not (r.x < o.x2 and o.x < r.x2 and r.y < o.y2 and o.y < r.y2)
    # adjacency room↔room 25m 안
    for adj in spec.adjacency:
        if adj.relationship == "passthrough_only":
            continue
        if adj.from_id in layout.rooms and adj.to_id in layout.rooms:
            a = layout.rooms[adj.from_id].rect
            b = layout.rooms[adj.to_id].rect
            assert abs(a.x - b.x) + abs(a.y - b.y) <= rep.adj_max_mm


def test_c1b_deterministic(setup_8000L):
    spec, bw, bh = setup_8000L
    la, _ = solve_c1b(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0)
    lb, _ = solve_c1b(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0)
    for rid in la.rooms:
        ra, rb = la.rooms[rid].rect, lb.rooms[rid].rect
        assert (ra.x, ra.y, ra.w, ra.h) == (rb.x, rb.y, rb.w, rb.h)


def test_c1b_layout_supports_p_series_after_eq_packing(setup_8000L):
    """C1b 방 좌표 + strip-band _place_equipment_grid → P-series 점수 측정 가능 (D-015 층2 재사용)."""
    spec, bw, bh = setup_8000L
    layout, _ = solve_c1b(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=3.0)
    _place_equipment_grid(layout)  # 층2 재사용
    out = score_spec_p_series(spec, layout=layout)
    for k in ("P1_flow_monotonicity", "P2_adjacency", "P7_compactness"):
        assert out[k]["raw"] is not None
        assert 0.0 <= out[k]["raw"] <= 1.0
    assert out["_normalized"] is not None


def test_c1b_p1only_surrogate_improves_small_scenario():
    """A_small_aseptic 에서 P1-only weight 가 strip-band 보다 norm 향상."""
    urs = URSInput(**json.loads(
        Path("examples/urs_A_small_aseptic.json").read_text(encoding="utf-8")
    ))
    spec = run_rule_engine(urs, strict=False)
    enrich_spec(spec)
    bw, bh, _ = resolve_building_dims(spec, urs_path="examples/urs_A_small_aseptic.json")
    layout, _ = solve_c1b(
        spec, canvas_w_mm=int(bw), canvas_h_mm=int(bh),
        time_limit_s=5.0, p1_weight=500, p2_weight=0, tiebreaker_weight=0,
    )
    _place_equipment_grid(layout)
    out_cp = score_spec_p_series(spec, layout=layout)

    # strip-band 비교
    from src.drawing_agent.floorplan import generate_floorplan
    spec2 = run_rule_engine(urs, strict=False)
    enrich_spec(spec2)
    _, sb_layout = generate_floorplan(
        spec2, urs_path="examples/urs_A_small_aseptic.json",
    )
    out_sb = score_spec_p_series(spec2, layout=sb_layout)

    # A_small 에서 CP-SAT P1-only 가 strip-band 보다 norm 높음 (실측 +0.04)
    assert out_cp["_normalized"] > out_sb["_normalized"], (
        f"CP-SAT C1b norm={out_cp['_normalized']:.4f} 가 strip-band {out_sb['_normalized']:.4f} 보다 낮음"
    )


def test_c1b_renderer_reuse(setup_8000L):
    spec, bw, bh = setup_8000L
    layout, _ = solve_c1b(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0)
    _place_equipment_grid(layout)
    svg = render(spec, layout)
    assert svg.startswith("<svg") or svg.lstrip().startswith("<svg")
    assert len(svg) > 10_000


def test_c1b_layout_types_unchanged(setup_8000L):
    spec, bw, bh = setup_8000L
    layout, _ = solve_c1b(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0)
    assert isinstance(layout, Layout)
    for pr in layout.rooms.values():
        assert isinstance(pr, PlacedRoom)
        assert isinstance(pr.rect, Rect)


def test_c1a_c1b_strip_band_all_still_work(setup_8000L):
    """C1a, strip-band 모두 그대로 동작 (회귀)."""
    spec, bw, bh = setup_8000L
    la, _ = solve_c1a(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0)
    assert len(la.rooms) == len(spec.rooms)
    sb = solve(spec)
    assert len(sb.rooms) > 0
