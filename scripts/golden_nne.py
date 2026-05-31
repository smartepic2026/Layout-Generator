"""Phase B3 — NNE golden fixture 로드 + Layout 구성 + strip-band 비교.

[D-014] tests/fixtures/golden_nne_layout.json (NNE Pharmaplan 모범 배치 구조)
를 읽어 (spec, Layout) 으로 반환. P-series 점수 측정 → output/baselines.json
(strip-band) 와 비교.

usage:
    .venv/bin/python -m scripts.golden_nne          # NNE vs strip-band 비교 표
    .venv/bin/python -m scripts.golden_nne --json   # 점수 dict 만 JSON 출력
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.drawing_agent.data import enrich_spec
from src.drawing_agent.layout_solver import (
    Layout,
    PlacedEquipment,
    PlacedRoom,
    Rect,
)
from src.reward.scorer import score, score_spec_p_series
from src.rule_engine.schemas import RuleEngineOutput


FIXTURE_PATH = Path("tests/fixtures/golden_nne_layout.json")
BASELINES_PATH = Path("output/baselines.json")


def load_golden_nne_spec_and_layout(
    fixture_path: Path = FIXTURE_PATH,
) -> tuple[RuleEngineOutput, Layout]:
    """fixture JSON 로드 → (spec, layout).

    layout 은 fixture 의 `layout_rects_mm` 으로 방 rect 부여 + 각 방 안 장비를
    row-major auto-pack (NNE 도면 정밀 좌표 아님 — 같은 방 내 응집만 보장).
    """
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    spec = RuleEngineOutput.model_validate(data["spec"])
    # tier3 derive — sort_order, co_locate_group, connects_to (same-room chain).
    enrich_spec(spec)

    rects = data["layout_rects_mm"]
    meta = data["_golden_meta"]
    layout = Layout(
        building_w_mm=float(meta["canvas_w_mm"]),
        building_h_mm=float(meta["canvas_h_mm"]),
    )

    EQ_GAP = 300         # 장비 간 간격 (mm)
    INNER_MARGIN = 800   # 방 안쪽 여백 (mm)

    for room in spec.rooms:
        if room.id not in rects:
            continue
        rx, ry, rw, rh = rects[room.id]
        proom = PlacedRoom(room=room, rect=Rect(rx, ry, rw, rh))
        layout.rooms[room.id] = proom

        # row-major pack — 같은 방 안 장비끼리 인접 (group 응집 자연 만족).
        cx = rx + INNER_MARGIN
        cy = ry + INNER_MARGIN
        inner_w = rw - 2 * INNER_MARGIN
        row_h = 0.0
        for eq in room.equipment:
            ew = float(eq.W_mm)
            eh = float(eq.D_mm)
            if cx + ew > rx + INNER_MARGIN + inner_w:
                cx = rx + INNER_MARGIN
                cy += row_h + EQ_GAP
                row_h = 0.0
            proom.equipment.append(
                PlacedEquipment(eq, Rect(cx, cy, ew, eh))
            )
            cx += ew + EQ_GAP
            row_h = max(row_h, eh)

    return spec, layout


def _safe_float(v):
    return None if v is None else round(float(v), 4)


def compare_with_baseline() -> dict:
    spec, layout = load_golden_nne_spec_and_layout()
    p_out = score_spec_p_series(spec, layout=layout)
    geo = score(spec, layout)

    nne_summary = {
        "P1": _safe_float(p_out["P1_flow_monotonicity"]["raw"]),
        "P2": _safe_float(p_out["P2_adjacency"]["raw"]),
        "P6": _safe_float(p_out["P6_cleaning_access"]["raw"]),
        "P7": _safe_float(p_out["P7_compactness"]["raw"]),
        "normalized": _safe_float(p_out["_normalized"]),
        "measured_denominator": p_out["_measured_denominator"],
        "rooms_count": len(spec.rooms),
        "equipment_count": sum(len(r.equipment) for r in spec.rooms),
        "geo_total": geo.total,
        "hard_violations": len(geo.hard_violations),
        "soft_violations": len(geo.soft_violations),
    }

    # strip-band baseline 비교용
    sb = {}
    if BASELINES_PATH.exists():
        bl = json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
        for name, sdata in bl["scenarios"].items():
            ps = sdata["p_series"]
            sb[name] = {
                "P1": _safe_float(ps["P1_flow_monotonicity"]["raw"]),
                "P2": _safe_float(ps["P2_adjacency"]["raw"]),
                "P6": _safe_float(ps["P6_cleaning_access"]["raw"]),
                "P7": _safe_float(ps["P7_compactness"]["raw"]),
                "normalized": _safe_float(sdata["p_series_normalized"]),
            }
    return {"NNE_golden": nne_summary, "strip_band_baselines": sb}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true",
                    help="dict 만 JSON 출력 (CI/스크립트 사용)")
    args = ap.parse_args(argv)
    cmp = compare_with_baseline()

    if args.json:
        print(json.dumps(cmp, indent=2, ensure_ascii=False))
        return 0

    nne = cmp["NNE_golden"]
    sb = cmp["strip_band_baselines"]
    print("=" * 100)
    print("B3 — NNE Pharmaplan 모범 배치 vs strip-band baseline")
    print("=" * 100)
    print(f'NNE: {nne["rooms_count"]} rooms, {nne["equipment_count"]} eq, '
          f'geo_total={nne["geo_total"]:.2f}, hard={nne["hard_violations"]}, soft={nne["soft_violations"]}')
    print()
    print(f'{"Layout":<22} {"P1":>8} {"P2":>8} {"P6":>8} {"P7":>8}   {"norm":>8}')
    print("-" * 100)

    def f(v): return "    None" if v is None else f"{v:8.4f}"

    print(f'{"NNE_golden":<22} {f(nne["P1"])} {f(nne["P2"])} {f(nne["P6"])} {f(nne["P7"])}   {f(nne["normalized"])}')
    print("-" * 100)
    for name, vals in sb.items():
        print(f'{name:<22} {f(vals["P1"])} {f(vals["P2"])} {f(vals["P6"])} {f(vals["P7"])}   {f(vals["normalized"])}')
    print("-" * 100)
    if sb:
        avg_sb_norm = sum(v["normalized"] for v in sb.values() if v["normalized"] is not None) / len(sb)
        print(f'\nNNE norm = {nne["normalized"]:.4f}  vs  strip-band avg norm = {avg_sb_norm:.4f}')
        delta = nne["normalized"] - avg_sb_norm
        verdict = "✓ NNE 우위" if delta > 0 else "✗ NNE 동등/열위 — 점수 수식 진단 필요"
        print(f'Δ = {delta:+.4f}  →  {verdict}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
