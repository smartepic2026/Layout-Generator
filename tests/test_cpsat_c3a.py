"""C3a — 방 1개 안 장비 CP-SAT 회귀 (D-018).

검증:
  1. R_MEDIA_PREP 5장비, 10×10m 방 rect 에서 OPTIMAL 도달, 5장비 모두 배치.
  2. 풀이 시간 < 1s (sub-second 기대).
  3. CP-SAT 가 row-major (실제 W_mm) 보다 P7_room (한 방 packing) 향상.
  4. 결정론 — 두 번 풀이 같은 좌표.
  5. INFEASIBLE 케이스 (방 너무 작음) 빈 list 반환, 호출자 fallback 가능.
  6. _place_equipment_grid(use_actual_mm=True) 도 새 모드 작동.
  7. 기존 strip-band 동작 보존 (use_actual_mm=False default).
"""
from __future__ import annotations

import pytest

ortools = pytest.importorskip("ortools")

from src.drawing_agent.cpsat_solver import solve_room_c3a
from src.drawing_agent.data import enrich_spec
from src.drawing_agent.layout_solver import (
    Layout,
    PlacedEquipment,
    PlacedRoom,
    Rect,
    _place_equipment_grid,
    solve,
)
from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput


SQUARE_100M2 = (0, 0, 10000, 10000)


def _build_baseline_room():
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    layout = solve(spec)
    return layout.rooms["R_MEDIA_PREP"].room


@pytest.fixture(scope="module")
def media_prep_room():
    return _build_baseline_room()


def test_c3a_optimal_5_eq_in_100m2(media_prep_room):
    placed, rep = solve_room_c3a(
        media_prep_room, SQUARE_100M2, time_limit_s=2.0,
        wall_margin_mm=300, eq_gap_mm=300,
    )
    assert rep.status == "OPTIMAL"
    assert len(placed) == 5


def test_c3a_solve_time_under_1s(media_prep_room):
    _, rep = solve_room_c3a(
        media_prep_room, SQUARE_100M2, time_limit_s=2.0,
        wall_margin_mm=300, eq_gap_mm=300,
    )
    assert rep.wall_time_ms < 1000.0


def test_c3a_no_overlap_and_in_room(media_prep_room):
    placed, _ = solve_room_c3a(
        media_prep_room, SQUARE_100M2, time_limit_s=2.0,
        wall_margin_mm=300, eq_gap_mm=300,
    )
    rx, ry, rw, rh = SQUARE_100M2
    for i in range(len(placed)):
        r = placed[i].rect
        assert rx <= r.x and r.x2 <= rx + rw
        assert ry <= r.y and r.y2 <= ry + rh
        for j in range(i + 1, len(placed)):
            o = placed[j].rect
            overlap = r.x < o.x2 and o.x < r.x2 and r.y < o.y2 and o.y < r.y2
            assert not overlap


def test_c3a_p7_improvement_over_row_major_actual(media_prep_room):
    """CP-SAT 가 row-major (실제 W_mm) 보다 한 방 P7 향상."""
    placed_cp, _ = solve_room_c3a(
        media_prep_room, SQUARE_100M2, time_limit_s=2.0,
        wall_margin_mm=300, eq_gap_mm=300,
    )

    # row-major 실제 W_mm 모드로 동일 방 packing
    rx, ry, rw, rh = SQUARE_100M2
    layout_rm = Layout(building_w_mm=10000, building_h_mm=10000)
    layout_rm.rooms["R_MEDIA_PREP"] = PlacedRoom(
        room=media_prep_room, rect=Rect(rx, ry, rw, rh)
    )
    _place_equipment_grid(layout_rm, use_actual_mm=True)
    placed_rm = layout_rm.rooms["R_MEDIA_PREP"].equipment

    def p7_room(equips):
        eq_area = sum(pe.rect.w * pe.rect.h for pe in equips) / 1e6
        xs = [pe.rect.x for pe in equips] + [pe.rect.x2 for pe in equips]
        ys = [pe.rect.y for pe in equips] + [pe.rect.y2 for pe in equips]
        env_area = (max(xs) - min(xs)) * (max(ys) - min(ys)) / 1e6
        inner = min(1.0, eq_area / env_area)
        outer_fill = env_area / (rw * rh / 1e6)
        outer = max(0.0, 1.0 - abs(outer_fill - 0.50) / 0.40)
        return (inner + outer) / 2.0

    p7_cp = p7_room(placed_cp)
    p7_rm = p7_room(placed_rm)
    assert p7_cp > p7_rm, f"CP-SAT P7_room {p7_cp:.3f} 가 row-major 실제 {p7_rm:.3f} 보다 낮음"


def test_c3a_deterministic(media_prep_room):
    pa, _ = solve_room_c3a(media_prep_room, SQUARE_100M2, time_limit_s=2.0,
                            wall_margin_mm=300, eq_gap_mm=300)
    pb, _ = solve_room_c3a(media_prep_room, SQUARE_100M2, time_limit_s=2.0,
                            wall_margin_mm=300, eq_gap_mm=300)
    assert len(pa) == len(pb)
    for ea, eb in zip(pa, pb):
        assert (ea.rect.x, ea.rect.y, ea.rect.w, ea.rect.h) == (
            eb.rect.x, eb.rect.y, eb.rect.w, eb.rect.h)


def test_c3a_infeasible_when_room_too_small(media_prep_room):
    """방 rect 가 장비 합보다 작으면 INFEASIBLE → 빈 list."""
    # 5장비 실제 합 39m². 30m² rect 면 안 들어감.
    placed, rep = solve_room_c3a(
        media_prep_room, (0, 0, 5000, 6000), time_limit_s=1.0,
        wall_margin_mm=300, eq_gap_mm=300,
    )
    assert rep.status == "INFEASIBLE"
    assert placed == []


def test_actual_mm_mode_preserves_strip_band_default():
    """`use_actual_mm=False` (default) = 기존 strip-band 동작. baselines/B3 안 흔듦."""
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    layout_default = solve(spec)  # 시각 축소 적용된 layout (기본)
    # default 가 use_actual_mm=False 인지 — R_MEDIA_PREP 의 한 장비 rect 가 W_mm 보다 작음
    eq0 = layout_default.rooms["R_MEDIA_PREP"].equipment[0]
    assert eq0.rect.w < eq0.equipment.W_mm, (
        f"기본은 시각 축소 적용되야 (eq.rect.w={eq0.rect.w} < W_mm={eq0.equipment.W_mm})"
    )


def test_actual_mm_mode_uses_real_dimensions():
    """`use_actual_mm=True` → 장비 rect 가 W_mm/D_mm 그대로."""
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    layout = solve(spec)  # 일단 strip-band 의 방 좌표만 가져옴
    # 시각 축소 적용된 장비 지우고 다시 packing
    for pr in layout.rooms.values():
        pr.equipment.clear()
    _place_equipment_grid(layout, use_actual_mm=True)
    # R_MEDIA_PREP 의 R_CELL_CULTURE 방 같은 큰 방 — 실제 W_mm 그대로 들어갔는지
    # (작은 방은 inner 음수라 fallback 으로 축소될 수 있음 — 큰 방으로 검증)
    pr = layout.rooms.get("R_CELL_CULTURE")
    if pr and pr.equipment:
        eq0 = pr.equipment[0]
        assert eq0.rect.w == eq0.equipment.W_mm or eq0.rect.w == eq0.equipment.D_mm, (
            f"use_actual_mm=True 인데 시각 축소됨 (rect.w={eq0.rect.w} vs W_mm={eq0.equipment.W_mm})"
        )
