"""C1+C3 통합 파이프라인 (D-020).

방 좌표 (C1b) → 장비 좌표 (C3a) → P-series 측정 → strip-band/NNE 비교.

usage:
    .venv/bin/python -m scripts.c1c3_pipeline
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.drawing_agent.cpsat_solver import solve_c1b, solve_room_c3a
from src.drawing_agent.data import enrich_spec, resolve_building_dims
from src.drawing_agent.layout_solver import (
    Layout,
    PlacedRoom,
    Rect,
    _place_equipment_grid,
)
from src.reward.scorer import score_spec_p_series
from src.rule_engine.engine import run_rule_engine
from src.contract.schemas import URSInput


# C3 시간 배분 정책 (n_eq 별) — D-020 통합 후 시간 절감 (사용자 요청)
def _c3_time_limit(n_eq: int) -> float:
    if n_eq <= 4:
        return 1.0
    if n_eq <= 10:
        return 3.0
    return 8.0  # 정제실1 23 장비


def _fallback_row_major_actual(layout: Layout, room_id: str) -> int:
    """C3a INFEASIBLE 시 row-major 실제 W_mm 으로 fallback.
    Returns: 배치된 장비 수.
    """
    # 일시 layout 에 그 방만 담아 _place_equipment_grid 호출
    tmp = Layout(building_w_mm=layout.building_w_mm, building_h_mm=layout.building_h_mm)
    tmp.rooms[room_id] = layout.rooms[room_id]
    _place_equipment_grid(tmp, use_actual_mm=True)
    return len(layout.rooms[room_id].equipment)


def solve_full_pipeline(
    spec,
    urs_path: str,
    c1_time_s: float = 10.0,
    c3_wall_margin_mm: int = 300,
    c3_eq_gap_mm: int = 300,
) -> dict:
    """C1b (방) + C3a (장비 × 방) 통합. 시간 측정 + INFEASIBLE fallback."""
    bw, bh, _ = resolve_building_dims(spec, urs_path=urs_path)

    # 1. C1b — 방 좌표
    # [D-020] aspect 동적 결정 — 캔버스 여유에 따라 좁힘 / 넓힘.
    # 좁힘 [0.9, 1.1] = 방 면적 spec area 근처, C3 친화 (P7 향상 큼).
    # 넓힘 [0.7, 1.4] = C1a feasibility 우선 (작은 캔버스 시나리오).
    spec_area_sum = sum(r.area_m2 for r in spec.rooms)
    canvas_area_m2 = bw * bh / 1e6
    if canvas_area_m2 < spec_area_sum * 1.0:
        # 캔버스가 빡빡 — aspect 넓혀야 feasible (A_small 같은 경우)
        am, aM = 0.7, 1.4
    else:
        am, aM = 0.9, 1.1
    t1 = time.perf_counter()
    layout, c1_rep = solve_c1b(
        spec, canvas_w_mm=int(bw), canvas_h_mm=int(bh),
        time_limit_s=c1_time_s,
        p1_weight=500, p2_weight=0, tiebreaker_weight=0,
        aspect_min=am, aspect_max=aM,
    )
    c1_ms = (time.perf_counter() - t1) * 1000

    # 2. 각 방 (장비 있는) — C3a
    room_reports = {}
    c3_total_ms = 0.0
    n_fallback = 0
    n_feasible_c3 = 0

    for proom in layout.rooms.values():
        room = proom.room
        if not room.equipment:
            continue
        rect_mm = (proom.rect.x, proom.rect.y, proom.rect.w, proom.rect.h)
        n_eq = len(room.equipment)
        t_limit = _c3_time_limit(n_eq)
        eq_sum_m2 = sum(e.W_mm * e.D_mm for e in room.equipment) / 1e6
        rect_area_m2 = rect_mm[2] * rect_mm[3] / 1e6

        placed, c3_rep = solve_room_c3a(
            room, rect_mm,
            time_limit_s=t_limit,
            wall_margin_mm=c3_wall_margin_mm,
            eq_gap_mm=c3_eq_gap_mm,
        )
        c3_total_ms += c3_rep.wall_time_ms

        if placed:
            proom.equipment[:] = placed
            n_feasible_c3 += 1
            room_reports[room.id] = {
                "n_eq": n_eq,
                "rect_area_m2": round(rect_area_m2, 1),
                "eq_sum_m2": round(eq_sum_m2, 1),
                "density": round(eq_sum_m2 / rect_area_m2, 3) if rect_area_m2 > 0 else None,
                "status": c3_rep.status,
                "solve_ms": c3_rep.wall_time_ms,
                "fallback": False,
            }
        else:
            # Fallback — row-major 실제 W_mm
            n_placed = _fallback_row_major_actual(layout, room.id)
            n_fallback += 1
            room_reports[room.id] = {
                "n_eq": n_eq,
                "rect_area_m2": round(rect_area_m2, 1),
                "eq_sum_m2": round(eq_sum_m2, 1),
                "density": round(eq_sum_m2 / rect_area_m2, 3) if rect_area_m2 > 0 else None,
                "status": "INFEASIBLE → row-major fallback",
                "solve_ms": c3_rep.wall_time_ms,
                "fallback": True,
                "fallback_n_placed": n_placed,
            }

    # 3. P-series 측정
    p_out = score_spec_p_series(spec, layout=layout)

    return {
        "layout": layout,
        "spec": spec,
        "canvas_dim_mm": (int(bw), int(bh)),
        "c1_solve_ms": round(c1_ms, 1),
        "c1_status": c1_rep.status,
        "c3_total_ms": round(c3_total_ms, 1),
        "total_solve_ms": round(c1_ms + c3_total_ms, 1),
        "n_rooms_with_eq": len(room_reports),
        "n_feasible_c3": n_feasible_c3,
        "n_fallback": n_fallback,
        "p_series": p_out,
        "room_reports": room_reports,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/c1c3_pipeline.json")
    args = ap.parse_args(argv)

    scenarios = [
        ("A_small_aseptic", "examples/urs_A_small_aseptic.json"),
        ("mab_8000L", "examples/urs_mab_8000L.json"),
        ("C_closed_sys", "examples/urs_C_closed_system.json"),
        ("B_large_multi", "examples/urs_B_large_multiproduct.json"),
    ]

    # strip-band baseline + NNE golden
    bl = json.loads(Path("output/baselines.json").read_text(encoding="utf-8"))
    from scripts.golden_nne import compare_with_baseline
    nne = compare_with_baseline()["NNE_golden"]

    def f(v):
        return "   None" if v is None else f"{v:7.4f}"

    print("=" * 145)
    print("C1+C3 통합 (D-020) — 4 시나리오 (strip-band before vs CP-SAT after vs NNE golden)")
    print("=" * 145)
    print("주: CP-SAT 는 실제 W_mm 기준, strip-band 는 시각축소 (0.8x) 기준 — 공정성 단서")
    print("-" * 145)
    h = (f'{"Scenario":<18} {"Solver":<14} {"Status":<10} {"Time(s)":>8} '
         f'{"P1":>7} {"P2":>7} {"P6":>7} {"P7":>7} {"norm":>7} {"Δnorm":>8} '
         f'{"c3_FB":>6}')
    print(h)
    print("-" * 145)

    results = []
    for name, path in scenarios:
        urs = URSInput(**json.loads(Path(path).read_text(encoding="utf-8")))
        spec = run_rule_engine(urs, strict=False)
        enrich_spec(spec)

        pipe = solve_full_pipeline(spec, urs_path=path)
        p_out = pipe["p_series"]

        sb = bl["scenarios"][name]
        sb_p = sb["p_series"]
        sb_norm = sb["p_series_normalized"]

        cp_p1 = p_out["P1_flow_monotonicity"]["raw"]
        cp_p2 = p_out["P2_adjacency"]["raw"]
        cp_p6 = p_out["P6_cleaning_access"]["raw"]
        cp_p7 = p_out["P7_compactness"]["raw"]
        cp_norm = p_out["_normalized"]

        # strip-band 줄
        print(f'{name:<18} {"strip-band":<14} {"-":<10} {"-":>8} '
              f'{f(sb_p["P1_flow_monotonicity"]["raw"])} {f(sb_p["P2_adjacency"]["raw"])} {f(None)} {f(sb_p["P7_compactness"]["raw"])} {f(sb_norm)} {"-":>8} {"-":>6}')
        dn = cp_norm - sb_norm if (cp_norm is not None and sb_norm is not None) else None
        # CP-SAT 통합 줄
        print(f'{"":<18} {"CP-SAT C1+C3":<14} {pipe["c1_status"]:<10} {pipe["total_solve_ms"]/1000:>8.2f} '
              f'{f(cp_p1)} {f(cp_p2)} {f(cp_p6)} {f(cp_p7)} {f(cp_norm)} {f(dn)} {pipe["n_fallback"]:>6}')
        print()

        results.append({
            "scenario": name,
            "urs_path": path,
            "canvas_dim_mm": pipe["canvas_dim_mm"],
            "c1_status": pipe["c1_status"],
            "c1_solve_ms": pipe["c1_solve_ms"],
            "c3_total_ms": pipe["c3_total_ms"],
            "total_solve_ms": pipe["total_solve_ms"],
            "n_rooms_with_eq": pipe["n_rooms_with_eq"],
            "n_feasible_c3": pipe["n_feasible_c3"],
            "n_fallback": pipe["n_fallback"],
            "p1": cp_p1, "p2": cp_p2, "p6": cp_p6, "p7": cp_p7,
            "normalized": cp_norm,
            "strip_band_normalized": sb_norm,
            "delta_norm": dn,
            "room_reports": pipe["room_reports"],
        })

    # NNE 참고
    print("-" * 145)
    print(f'{"NNE golden (ref)":<18} {"manual":<14} {"-":<10} {"-":>8} '
          f'{f(nne["P1"])} {f(nne["P2"])} {f(nne["P6"])} {f(nne["P7"])} {f(nne["normalized"])} {"-":>8} {"-":>6}')

    # 요약
    print()
    sb_avg = sum(bl["scenarios"][n]["p_series_normalized"] for n, _ in scenarios) / len(scenarios)
    cp_avg = sum(r["normalized"] for r in results) / len(results)
    total_time = sum(r["total_solve_ms"] for r in results) / 1000.0
    print(f"strip-band avg norm: {sb_avg:.4f}")
    print(f"CP-SAT C1+C3 avg   : {cp_avg:.4f}  (Δ {cp_avg-sb_avg:+.4f})")
    print(f"NNE golden         : {nne['normalized']:.4f}")
    print(f"전체 풀이시간 합   : {total_time:.1f}s")
    print(f"INFEASIBLE→fallback: {sum(r['n_fallback'] for r in results)} (4 시나리오 통합)")

    # 정제실1 강조 (mab_8000L)
    mab = next((r for r in results if r["scenario"] == "mab_8000L"), None)
    if mab and "R_PURIFICATION_1" in mab["room_reports"]:
        pr = mab["room_reports"]["R_PURIFICATION_1"]
        print()
        print("⚠️  R_PURIFICATION_1 (mab_8000L, 23 장비) 강조 — 사용자 1순위 관심:")
        print(f"   status={pr['status']}, time_ms={pr['solve_ms']:.0f}, fallback={pr['fallback']}")
        print(f"   rect_area={pr['rect_area_m2']}m², eq_sum={pr['eq_sum_m2']}m², density={pr['density']}")

    # JSON 저장
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # layout / spec 제외
    serializable_results = []
    for r in results:
        clean = dict(r)
        clean["canvas_dim_mm"] = list(r["canvas_dim_mm"])
        serializable_results.append(clean)
    out_path.write_text(json.dumps({
        "schema_version": "1.0",
        "phase": "C1+C3",
        "decision_anchor": "D-020",
        "scenarios": serializable_results,
        "strip_band_avg_norm": round(sb_avg, 4),
        "cpsat_avg_norm": round(cp_avg, 4),
        "delta_avg": round(cp_avg - sb_avg, 4),
        "nne_golden_norm": round(nne["normalized"], 4),
        "total_solve_time_s": round(total_time, 1),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
