"""C3b — 장비 있는 모든 방 sweep 회귀 (D-019).

검증:
  1. mab_8000L baseline 의 13 방 (장비 있는 모든 방) 모두 FEASIBLE 도달.
  2. R_PURIFICATION_1 (23장비) 도 FEASIBLE — fallback 불필요.
  3. P7 향상 평균 (CP-SAT > row-major 실제) — 13방 평균.
  4. 결정론 — 같은 입력 → 같은 결과.
"""
from __future__ import annotations

import pytest

ortools = pytest.importorskip("ortools")

from scripts.c3b_room_map import _square_rect_for_area, measure_room_modes
from src.drawing_agent.data import enrich_spec
from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput


@pytest.fixture(scope="module")
def rooms_with_eq():
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    rooms = [r for r in spec.rooms if r.equipment]
    rooms.sort(key=lambda r: (len(r.equipment), r.id))
    return rooms


def test_c3b_all_rooms_feasible(rooms_with_eq):
    """13 방 모두 OPTIMAL 또는 FEASIBLE."""
    for room in rooms_with_eq:
        rect = _square_rect_for_area(room.area_m2)
        m = measure_room_modes(room, rect, time_limit_s=5.0)
        status = m["cpsat"]["status"]
        assert status in ("OPTIMAL", "FEASIBLE"), (
            f"{room.id}: {status} — 안 풀림 (n_eq={room.n_eq if hasattr(room,'n_eq') else len(room.equipment)})"
        )


def test_c3b_purification_1_feasible():
    """[D-019 핵심] 정제실1 (23장비, density 0.39) 도 FEASIBLE — fallback 불필요."""
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    room = next(r for r in spec.rooms if r.id == "R_PURIFICATION_1")
    rect = _square_rect_for_area(room.area_m2)
    m = measure_room_modes(room, rect, time_limit_s=10.0)
    assert m["cpsat"]["status"] in ("OPTIMAL", "FEASIBLE")
    # 23장비 풀이 시간 — 우리 머신에서 ~5s timeout 도달 첫 feasible. 15s 한계.
    assert m["cpsat"]["solve_ms"] < 15_000


def test_c3b_average_p7_improvement(rooms_with_eq):
    """13 방 평균 — CP-SAT P7 > row-major 실제 P7."""
    p7_cp_sum = 0.0
    p7_rm_sum = 0.0
    n = 0
    for room in rooms_with_eq:
        rect = _square_rect_for_area(room.area_m2)
        m = measure_room_modes(room, rect, time_limit_s=5.0)
        rm_p7 = m["row_major_actual"]["p7_room"]
        cp_p7 = m["cpsat"]["p7_room"]
        if rm_p7 is not None and cp_p7 is not None:
            p7_rm_sum += rm_p7
            p7_cp_sum += cp_p7
            n += 1
    assert n > 0
    rm_avg = p7_rm_sum / n
    cp_avg = p7_cp_sum / n
    assert cp_avg > rm_avg, f"CP avg P7 {cp_avg:.4f} 가 row-major avg {rm_avg:.4f} 보다 낮음"


def test_c3b_deterministic_purification_1():
    """정제실1 두 번 풀이 → 같은 P7."""
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    room = next(r for r in spec.rooms if r.id == "R_PURIFICATION_1")
    rect = _square_rect_for_area(room.area_m2)
    a = measure_room_modes(room, rect, time_limit_s=5.0)
    b = measure_room_modes(room, rect, time_limit_s=5.0)
    assert a["cpsat"]["p7_room"] == b["cpsat"]["p7_room"]
    assert a["cpsat"]["p1_local"] == b["cpsat"]["p1_local"]
