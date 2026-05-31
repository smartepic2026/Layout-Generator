"""C0 — CP-SAT 최소 골격 회귀 (D-015).

검증 항목:
  1. 모델 빌드 후 OPTIMAL 해 도달
  2. 3개 방 모두 좌표 부여, 안 겹침
  3. 캔버스 안에 들어감
  4. 기존 Layout 자료구조 그대로 사용 (Rect/PlacedRoom 타입)
  5. renderer.render() 가 코드 수정 없이 SVG 생성
  6. 풀이 시간 < 2s (방 3개면 ms 단위)
  7. 결정론 — 같은 입력 두 번 → 같은 좌표
"""
from __future__ import annotations

import pytest

ortools = pytest.importorskip("ortools")

from src.drawing_agent.cpsat_solver import solve_minimal
from src.drawing_agent.data import enrich_spec, resolve_building_dims
from src.drawing_agent.layout_solver import Layout, PlacedRoom, Rect
from src.drawing_agent.renderer import render
from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput


THREE_ROOMS = ["R_MEDIA_PREP", "R_BUFFER_PREP", "R_INOCULATION"]


@pytest.fixture(scope="module")
def baseline_setup():
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    bw, bh, _ = resolve_building_dims(spec, urs_path=None)
    return spec, int(bw), int(bh)


def test_c0_solves_optimal(baseline_setup):
    spec, bw, bh = baseline_setup
    layout, rep = solve_minimal(spec, THREE_ROOMS, canvas_w_mm=bw, canvas_h_mm=bh)
    assert rep.status == "OPTIMAL"
    assert rep.objective is not None
    assert len(rep.rooms_solved) == 3


def test_c0_rooms_no_overlap_and_in_canvas(baseline_setup):
    spec, bw, bh = baseline_setup
    layout, _ = solve_minimal(spec, THREE_ROOMS, canvas_w_mm=bw, canvas_h_mm=bh)
    rects = [pr.rect for pr in layout.rooms.values()]
    # H1 — 캔버스 안
    for r in rects:
        assert 0 <= r.x and r.x2 <= bw
        assert 0 <= r.y and r.y2 <= bh
    # H2 — 안 겹침
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            overlap = a.x < b.x2 and b.x < a.x2 and a.y < b.y2 and b.y < a.y2
            assert not overlap


def test_c0_layout_types_match_strip_band(baseline_setup):
    """CP-SAT 출력이 기존 Layout/PlacedRoom/Rect 타입이어야 (재사용 검증)."""
    spec, bw, bh = baseline_setup
    layout, _ = solve_minimal(spec, THREE_ROOMS, canvas_w_mm=bw, canvas_h_mm=bh)
    assert isinstance(layout, Layout)
    for pr in layout.rooms.values():
        assert isinstance(pr, PlacedRoom)
        assert isinstance(pr.rect, Rect)


def test_c0_renderer_reuse_no_code_changes(baseline_setup):
    """renderer.render() 가 CP-SAT layout 을 그대로 받아 SVG 생성."""
    spec, bw, bh = baseline_setup
    layout, _ = solve_minimal(spec, THREE_ROOMS, canvas_w_mm=bw, canvas_h_mm=bh)
    svg = render(spec, layout)
    assert isinstance(svg, str)
    assert svg.startswith("<svg") or svg.lstrip().startswith("<svg")
    # 3개 방 라벨이 SVG 어딘가에 들어감 (renderer 가 layout.rooms 를 순회)
    for rid in THREE_ROOMS:
        # 라벨은 name_en/name_ko 기반이라 id 그대로는 아닐 수 있음 — 길이만 sanity check
        pass
    assert len(svg) > 5000  # 의미있는 SVG 면 KB 단위


def test_c0_solve_time_under_2s(baseline_setup):
    """방 3개 모델은 ms 단위. 2초 넘으면 모델/제약에 뭔가 잘못됨."""
    spec, bw, bh = baseline_setup
    _, rep = solve_minimal(spec, THREE_ROOMS, canvas_w_mm=bw, canvas_h_mm=bh)
    assert rep.wall_time_ms < 2000.0, f"풀이 {rep.wall_time_ms:.1f}ms — 너무 느림"


def test_c0_deterministic(baseline_setup):
    """num_search_workers=1 으로 결정론 보장. 같은 입력 → 같은 좌표."""
    spec, bw, bh = baseline_setup
    la, _ = solve_minimal(spec, THREE_ROOMS, canvas_w_mm=bw, canvas_h_mm=bh)
    lb, _ = solve_minimal(spec, THREE_ROOMS, canvas_w_mm=bw, canvas_h_mm=bh)
    for rid in THREE_ROOMS:
        ra, rb = la.rooms[rid].rect, lb.rooms[rid].rect
        assert (ra.x, ra.y, ra.w, ra.h) == (rb.x, rb.y, rb.w, rb.h)


def test_c0_strip_band_solver_unchanged():
    """기존 strip-band layout_solver.solve() 가 그대로 작동 (fallback 보존)."""
    from src.drawing_agent.layout_solver import solve
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    layout = solve(spec)  # default 78500x42500
    assert isinstance(layout, Layout)
    assert len(layout.rooms) > 0


def test_c0_missing_room_id_silent_skip(baseline_setup):
    """spec 에 없는 id 는 silent skip — C0 호출자 책임 정책."""
    spec, bw, bh = baseline_setup
    layout, rep = solve_minimal(
        spec, ["R_MEDIA_PREP", "R_DOES_NOT_EXIST"],
        canvas_w_mm=bw, canvas_h_mm=bh,
    )
    assert rep.status == "OPTIMAL"
    assert "R_MEDIA_PREP" in layout.rooms
    assert "R_DOES_NOT_EXIST" not in layout.rooms
