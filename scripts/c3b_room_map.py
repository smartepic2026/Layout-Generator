"""C3b — 장비 있는 모든 방에 C3a (장비 CP-SAT) 적용 + 방별 feasible 지도 (D-019).

목적: "한 방 됐다고 22방 된다는 보장 없다" — 방마다 feasible 여부, 점수 향상,
풀이시간 측정. R_PURIFICATION_1 (23장비) 별도 강조.

usage:
    .venv/bin/python -m scripts.c3b_room_map
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.drawing_agent.cpsat_solver import solve_room_c3a
from src.drawing_agent.data import enrich_spec
from src.drawing_agent.layout_solver import (
    Layout,
    PlacedEquipment,
    PlacedRoom,
    Rect,
    _place_equipment_grid,
)
from src.rule_engine.engine import run_rule_engine
from src.contract.schemas import URSInput


def _square_rect_for_area(area_m2: float) -> tuple:
    """spec area_m2 정사각 rect (mm). 한 변 = √area × 1000."""
    side_mm = (area_m2 ** 0.5) * 1000.0
    return (0, 0, int(round(side_mm)), int(round(side_mm)))


def _measure_room(equips, rect_mm) -> dict:
    """한 방 packing 의 P7_room + P1_local 측정."""
    if not equips:
        return {"p7_room": None, "p1_local": None, "eq_area_m2": 0,
                "env_area_m2": 0, "outer_fill": None, "inner": None}
    eq_area = sum(pe.rect.w * pe.rect.h for pe in equips) / 1e6
    xs = [pe.rect.x for pe in equips] + [pe.rect.x2 for pe in equips]
    ys = [pe.rect.y for pe in equips] + [pe.rect.y2 for pe in equips]
    env_area = (max(xs) - min(xs)) * (max(ys) - min(ys)) / 1e6
    inner = min(1.0, eq_area / env_area) if env_area > 0 else 0.0
    _, _, rw, rh = rect_mm
    room_area = rw * rh / 1e6
    outer_fill = env_area / room_area if room_area > 0 else 0.0
    OUTER_SWEET, OUTER_HB = 0.50, 0.40
    outer_score = max(0.0, 1.0 - abs(outer_fill - OUTER_SWEET) / OUTER_HB)
    p7 = (inner + outer_score) / 2.0

    # P1 local (sort_order 다른 쌍의 가로 단조 비율)
    fwd, rev = 0, 0
    for i in range(len(equips)):
        for j in range(i + 1, len(equips)):
            ei, ej = equips[i].equipment, equips[j].equipment
            if ei.sort_order is None or ej.sort_order is None:
                continue
            if ei.sort_order == ej.sort_order:
                continue
            cxi, cxj = equips[i].rect.cx, equips[j].rect.cx
            if ei.sort_order < ej.sort_order:
                if cxi <= cxj:
                    fwd += 1
                else:
                    rev += 1
            else:
                if cxj <= cxi:
                    fwd += 1
                else:
                    rev += 1
    p1 = (fwd / (fwd + rev)) if (fwd + rev) else None
    return {
        "p7_room": p7, "p1_local": p1,
        "eq_area_m2": eq_area, "env_area_m2": env_area,
        "outer_fill": outer_fill, "inner": inner,
    }


def _row_major_actual(room, rect_mm) -> list:
    """row-major 실제 W_mm 모드. C3a 와 같은 기준 (B-001 분리)."""
    layout = Layout(building_w_mm=rect_mm[2], building_h_mm=rect_mm[3])
    layout.rooms[room.id] = PlacedRoom(room=room, rect=Rect(*rect_mm))
    _place_equipment_grid(layout, use_actual_mm=True)
    return layout.rooms[room.id].equipment


def measure_room_modes(
    room,
    rect_mm: tuple,
    time_limit_s: float = 5.0,
    wall_margin_mm: int = 300,
    eq_gap_mm: int = 300,
) -> dict:
    """한 방에 대해 row-major(실제) vs CP-SAT 비교."""
    rm_placed = _row_major_actual(room, rect_mm)
    rm_metrics = _measure_room(rm_placed, rect_mm)

    cp_placed, rep = solve_room_c3a(
        room, rect_mm, time_limit_s=time_limit_s,
        wall_margin_mm=wall_margin_mm, eq_gap_mm=eq_gap_mm,
    )
    cp_metrics = _measure_room(cp_placed, rect_mm)
    return {
        "room_id": room.id,
        "category": room.category,
        "n_eq": len(room.equipment),
        "area_m2": room.area_m2,
        "rect_mm": rect_mm,
        "eq_area_sum_m2": rm_metrics["eq_area_m2"],
        "density_eq_room": rm_metrics["eq_area_m2"] / (rect_mm[2] * rect_mm[3] / 1e6),
        "row_major_actual": rm_metrics,
        "cpsat": {**cp_metrics, "status": rep.status, "solve_ms": rep.wall_time_ms,
                  "objective": rep.objective},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-limit-s", type=float, default=5.0)
    ap.add_argument("--out", default="output/c3b_room_map.json")
    args = ap.parse_args(argv)

    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    rooms_with_eq = [r for r in spec.rooms if r.equipment]
    rooms_with_eq.sort(key=lambda r: (len(r.equipment), r.id))

    results = []
    for room in rooms_with_eq:
        rect = _square_rect_for_area(room.area_m2)
        m = measure_room_modes(room, rect, time_limit_s=args.time_limit_s)
        results.append(m)

    # 표
    print("=" * 138)
    print("C3b — 장비 있는 모든 방에 C3a (장비 CP-SAT) 적용 (장비 적은 순)")
    print("=" * 138)
    h = (f'{"Room":<24} {"cat":<8} {"n":>3} {"area":>6} {"rect":>10} '
         f'{"dens":>5}   {"RM P7":>6} {"RM P1":>6}  {"CP st":<10} '
         f'{"CP ms":>7} {"CP P7":>6} {"CP P1":>6}  {"ΔP7":>7} {"ΔP1":>7}')
    print(h)
    print("-" * 138)

    def f(v):
        return "  None" if v is None else f"{v:6.4f}"

    feasible_count = 0
    for m in results:
        rm = m["row_major_actual"]
        cp = m["cpsat"]
        rect_str = f'{m["rect_mm"][2]/1000:.1f}×{m["rect_mm"][3]/1000:.1f}'
        d_p7 = (cp["p7_room"] - rm["p7_room"]) if (cp["p7_room"] is not None and rm["p7_room"] is not None) else None
        d_p1 = (cp["p1_local"] - rm["p1_local"]) if (cp["p1_local"] is not None and rm["p1_local"] is not None) else None
        print(
            f'{m["room_id"]:<24} {m["category"]:<8} {m["n_eq"]:>3} '
            f'{m["area_m2"]:>6.1f} {rect_str:>10} {m["density_eq_room"]:>5.3f}   '
            f'{f(rm["p7_room"])} {f(rm["p1_local"])}  '
            f'{cp["status"]:<10} {cp["solve_ms"]:>7.0f} {f(cp["p7_room"])} {f(cp["p1_local"])}  '
            f'{f(d_p7)} {f(d_p1)}'
        )
        if cp["status"] in ("OPTIMAL", "FEASIBLE"):
            feasible_count += 1

    print("-" * 138)
    print(f"feasible: {feasible_count}/{len(results)}")
    print()

    # R_PURIFICATION_1 강조
    purif1 = next((m for m in results if m["room_id"] == "R_PURIFICATION_1"), None)
    if purif1:
        cp = purif1["cpsat"]
        rm = purif1["row_major_actual"]
        print("=" * 80)
        print("⚠️  R_PURIFICATION_1 (정제실 1) — 23 장비, density {:.3f}".format(
            purif1["density_eq_room"]))
        print("=" * 80)
        print(f"   spec area = {purif1['area_m2']} m², rect = "
              f"{purif1['rect_mm'][2]/1000:.1f}×{purif1['rect_mm'][3]/1000:.1f} m")
        print(f"   장비 합 = {purif1['eq_area_sum_m2']:.1f} m², "
              f"density (eq/rect) = {purif1['density_eq_room']:.3f}")
        print(f"   row-major (실제 W_mm): "
              f"P7={f(rm['p7_room'])}, P1={f(rm['p1_local'])}")
        print(f"   CP-SAT:                "
              f"status={cp['status']}, solve_ms={cp['solve_ms']:.0f}, "
              f"P7={f(cp['p7_room'])}, P1={f(cp['p1_local'])}")
        if cp["status"] == "INFEASIBLE":
            print(f"   ★ INFEASIBLE — fallback 전략 결정 필요")

    # JSON 저장 (결정론적 메타 + 결과)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = []
    for m in results:
        clean = dict(m)
        clean["rect_mm"] = list(m["rect_mm"])
        serializable.append(clean)
    out_path.write_text(json.dumps({
        "schema_version": "1.0",
        "phase": "C3b",
        "decision_anchor": "D-019",
        "time_limit_s": args.time_limit_s,
        "n_rooms": len(results),
        "feasible_count": feasible_count,
        "results": serializable,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
