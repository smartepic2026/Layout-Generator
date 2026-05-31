"""C1a — 전체 방 + hard 제약 회귀 (D-016).

검증 항목:
  1. 28방 (mab_8000L baseline) FEASIBLE 도달, 모든 방 좌표 부여.
  2. 모든 hard 제약 만족 (안 겹침, 캔버스 안, adjacency 25m 안).
  3. 첫 feasible 시간 < 2s (sub-second 기대, 여유 + 머신 변동).
  4. 결정론 — 두 번 풀이 같은 좌표 (random_seed=0).
  5. zone 완화 옵션이 INFEASIBLE 진단 격리에 사용 가능.
  6. renderer.render() 재사용 SVG 생성.
  7. 기존 strip-band / C0 보존 (regression).
"""
from __future__ import annotations

import pytest

ortools = pytest.importorskip("ortools")

from src.drawing_agent.cpsat_solver import solve_c1a, solve_minimal
from src.drawing_agent.data import enrich_spec, resolve_building_dims
from src.drawing_agent.layout_solver import Layout, PlacedRoom, Rect
from src.drawing_agent.renderer import render
from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput


@pytest.fixture(scope="module")
def setup_8000L():
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    bw, bh, _ = resolve_building_dims(spec, urs_path=None)
    return spec, int(bw), int(bh)


def test_c1a_solves_feasible_all_28_rooms(setup_8000L):
    spec, bw, bh = setup_8000L
    layout, rep = solve_c1a(
        spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=5.0,
        enforce_zones=True, enforce_adjacency=True,
    )
    assert rep.status in ("OPTIMAL", "FEASIBLE")
    assert len(layout.rooms) == len(spec.rooms)
    assert rep.objective is not None


def test_c1a_no_overlap_in_canvas(setup_8000L):
    spec, bw, bh = setup_8000L
    layout, _ = solve_c1a(
        spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=5.0,
        enforce_zones=True, enforce_adjacency=True,
    )
    rects = list(layout.rooms.values())
    for i in range(len(rects)):
        r = rects[i].rect
        assert 0 <= r.x and r.x2 <= bw
        assert 0 <= r.y and r.y2 <= bh
        for j in range(i + 1, len(rects)):
            o = rects[j].rect
            overlap = r.x < o.x2 and o.x < r.x2 and r.y < o.y2 and o.y < r.y2
            assert not overlap


def test_c1a_adjacency_pairs_within_threshold(setup_8000L):
    """adjacency hard — room↔room 쌍이 25m (manhattan) 안에."""
    spec, bw, bh = setup_8000L
    layout, rep = solve_c1a(
        spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=5.0,
        enforce_zones=True, enforce_adjacency=True,
    )
    # adjacency 의 room↔room 쌍만 (room↔airlock 은 모델 밖)
    over = 0
    for adj in spec.adjacency:
        if adj.relationship == "passthrough_only":
            continue
        if adj.from_id in layout.rooms and adj.to_id in layout.rooms:
            a = layout.rooms[adj.from_id].rect
            b = layout.rooms[adj.to_id].rect
            d = abs(a.x - b.x) + abs(a.y - b.y)
            if d > rep.adj_max_mm:
                over += 1
    assert over == 0


def test_c1a_first_feasible_under_2s(setup_8000L):
    """첫 feasible 해는 sub-second 이지만 머신 변동 여유로 2s 한계."""
    spec, bw, bh = setup_8000L
    layout, rep = solve_c1a(
        spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0,
        enforce_zones=True, enforce_adjacency=True,
    )
    assert rep.status in ("OPTIMAL", "FEASIBLE")
    assert len(layout.rooms) == len(spec.rooms)


def test_c1a_deterministic(setup_8000L):
    """random_seed=0 으로 두 번 풀이 → 같은 좌표."""
    spec, bw, bh = setup_8000L
    la, _ = solve_c1a(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0)
    lb, _ = solve_c1a(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0)
    for rid in la.rooms:
        ra, rb = la.rooms[rid].rect, lb.rooms[rid].rect
        assert (ra.x, ra.y, ra.w, ra.h) == (rb.x, rb.y, rb.w, rb.h)


def test_c1a_relaxation_flags_for_diagnosis(setup_8000L):
    """완화 옵션 — INFEASIBLE 진단용. zones 끄면 풀이 더 자유."""
    spec, bw, bh = setup_8000L
    # 둘 다 끄기 (가장 자유)
    layout, rep = solve_c1a(
        spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0,
        enforce_zones=False, enforce_adjacency=False,
    )
    assert rep.status in ("OPTIMAL", "FEASIBLE")
    assert rep.enforce_zones is False
    assert rep.enforce_adjacency is False
    assert rep.n_adjacency_pairs == 0  # 끈 상태에선 pair 0


def test_c1a_renderer_reuse(setup_8000L):
    """renderer.render() 가 코드 수정 없이 28방 SVG 생성."""
    spec, bw, bh = setup_8000L
    layout, _ = solve_c1a(
        spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0,
        enforce_zones=True, enforce_adjacency=True,
    )
    svg = render(spec, layout)
    assert svg.startswith("<svg") or svg.lstrip().startswith("<svg")
    assert len(svg) > 10_000  # 28방 SVG 면 충분히 큼


def test_c1a_returns_strip_band_compatible_layout_types(setup_8000L):
    spec, bw, bh = setup_8000L
    layout, _ = solve_c1a(spec, canvas_w_mm=bw, canvas_h_mm=bh, time_limit_s=2.0)
    assert isinstance(layout, Layout)
    for pr in layout.rooms.values():
        assert isinstance(pr, PlacedRoom)
        assert isinstance(pr.rect, Rect)


def test_c0_minimal_still_works(setup_8000L):
    """C0 (solve_minimal) 가 factor 변경 후에도 그대로 동작."""
    spec, bw, bh = setup_8000L
    layout, rep = solve_minimal(
        spec, ["R_MEDIA_PREP", "R_BUFFER_PREP", "R_INOCULATION"],
        canvas_w_mm=bw, canvas_h_mm=bh,
    )
    assert rep.status == "OPTIMAL"
    assert len(layout.rooms) == 3


def test_c1a_strip_band_solver_still_unchanged():
    """기존 strip-band layout_solver.solve() 가 그대로 동작 (fallback 보존)."""
    from src.drawing_agent.layout_solver import solve
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    layout = solve(spec)
    assert isinstance(layout, Layout)
    assert len(layout.rooms) > 0
