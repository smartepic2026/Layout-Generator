"""Phase B2 — strip-band before-baseline 측정 + output/baselines.json 저장.

논문 "before → after" 서사의 출발점. 4 시나리오 × (P-series + geometric
quality 6종 + hard/soft) 를 결정론적으로 측정.

usage:
    .venv/bin/python -m scripts.baselines              # 측정 + 저장
    .venv/bin/python -m scripts.baselines --check      # 두 번 돌려서 결정론 검증

[D-013] 이 시점 한계를 메타에 기록 — 향후 "장비 변별 후" "CP-SAT 후" 비교 시
무엇이 달랐는지 추적 가능.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.drawing_agent.data import resolve_building_dims
from src.drawing_agent.floorplan import generate_floorplan
from src.reward.scorer import (
    P_ACTIVE_DENOMINATOR,
    P_DEFERRED,
    P_WEIGHTS,
    score,
    score_spec_p_series,
)
from src.rule_engine.engine import run_rule_engine
from src.contract.schemas import URSInput

SCHEMA_VERSION = "1.0"

SCENARIOS = [
    ("A_small_aseptic", "examples/urs_A_small_aseptic.json"),
    ("mab_8000L", "examples/urs_mab_8000L.json"),
    ("C_closed_sys", "examples/urs_C_closed_system.json"),
    ("B_large_multi", "examples/urs_B_large_multiproduct.json"),
]

LIMITATIONS = [
    "rule_engine 이 URS 의 culture_scale_L / n_product_types / building dim 을 "
    "spec 에 흘리지 않음 → 4 시나리오 장비 65 종 동일. 사용자(팀원) 가 URS "
    "3.6 Critical Process Equipment List 채운 뒤 rule_engine 이 그를 읽도록 "
    "연결 예정. (D-010 책임 분리 — 장비 사양은 rule_engine 영역).",
    "CP-SAT 솔버 미도입 (Phase C 예정). 현재 strip-band 격자 (결정론적, "
    "stripe_ratios 고정 — layout_solver.py:154) — 자유 배치 아님.",
    "P3 (environmental_protection_open) / P5 (airflow_contaminant_alignment) "
    "/ P8 (HSE) 보류 (P_DEFERRED). 도메인 검수자 부재 — 추론 데이터 오염 회피.",
    "P6 (cleaning_access) 본 수식 미구현 + clearance_m 데이터 부재 → "
    "현 시점 항상 None. status='skipped_no_data'. (D-009 epistemic honesty).",
    "P-series 정규화 분모는 측정 가능한 active 가중치 합 — 현재 P6 빠진 19. "
    "활성 4개 가중치 합 (상수 23) 도 함께 노출.",
]

EXPECTED_VARIATION_NOTE = (
    "현재 변동 폭이 좁은 것 (norm 0.6511~0.6965, ~7%p) 은 버그가 아닌 "
    "예상된 중간 상태. (1) 장비 변별 부재 + (2) CP-SAT 전 strip-band 격자 "
    "라는 두 제약 때문이며, 두 요인 모두 해소되면 변동 폭이 커지는 것이 논문 "
    "'before → after' 서사의 핵심 신호다."
)


def _serialize_p_series(out: dict) -> dict:
    """score_spec_p_series 의 반환을 JSON serializable dict 로."""
    res: dict[str, Any] = {}
    for k, v in out.items():
        if k.startswith("_"):
            res[k] = v
            continue
        # 항목별 sub-dict (raw / weight / contrib / status)
        res[k] = {
            "raw": v["raw"],
            "weight": v["weight"],
            "contrib": v["contrib"],
            "status": v["status"],
        }
    return res


def _measure_scenario(name: str, urs_path: str) -> dict:
    """한 시나리오 spec 생성 + layout 부여 + 점수 측정."""
    urs = URSInput(**json.loads(Path(urs_path).read_text(encoding="utf-8")))
    spec = run_rule_engine(urs, strict=False)
    bw, bh, bsrc = resolve_building_dims(spec, urs_path=urs_path)
    _, layout = generate_floorplan(spec, urs_path=urs_path)

    p_out = score_spec_p_series(spec, layout=layout)
    rep = score(spec, layout)

    return {
        "meta": {
            "urs_path": urs_path,
            "project_name": spec.project_name,
            "modality": spec.modality,
            "rooms_count": len(spec.rooms),
            "airlocks_count": len(spec.airlocks),
            "equipment_count": sum(len(r.equipment) for r in spec.rooms),
            "building_dim_mm": [bw, bh],
            "building_dim_source": bsrc,
            "ppo_length": len(spec.flow_paths.product_process_order),
        },
        "p_series": _serialize_p_series(p_out),
        "p_series_normalized": p_out["_normalized"],
        "p_series_measured_denominator": p_out["_measured_denominator"],
        "p_series_active_denominator": p_out["_active_denominator"],
        "geometric_quality": {
            "total": rep.total,
            "hard_violations_count": len(rep.hard_violations),
            "soft_violations_count": len(rep.soft_violations),
            "breakdown": rep.breakdown,
        },
    }


def collect_baselines(include_timestamp: bool = True) -> dict:
    """모든 시나리오 측정 → dict 반환 (저장은 분리)."""
    scenarios = {name: _measure_scenario(name, path) for name, path in SCENARIOS}
    out = {
        "schema_version": SCHEMA_VERSION,
        "phase": "B2",
        "decision_anchor": "D-013",
        "p_weights": dict(P_WEIGHTS),
        "p_deferred": sorted(P_DEFERRED),
        "p_active_denominator_constant": P_ACTIVE_DENOMINATOR,
        "limitations": LIMITATIONS,
        "expected_variation_note": EXPECTED_VARIATION_NOTE,
        "scenarios": scenarios,
    }
    if include_timestamp:
        out["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return out


def _strip_timestamp(d: dict) -> dict:
    """결정론 비교용 — timestamp 만 빼고 동일성 검사."""
    return {k: v for k, v in d.items() if k != "generated_at"}


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="B2 baseline collector")
    p.add_argument("--check", action="store_true",
                   help="두 번 측정해 결정론 (동일 입력 → 동일 출력) 검증만 수행")
    p.add_argument("--out", default="output/baselines.json")
    args = p.parse_args(argv)

    if args.check:
        a = collect_baselines(include_timestamp=False)
        b = collect_baselines(include_timestamp=False)
        if a == b:
            print("[OK] 결정론 검증 통과 — 같은 입력 → 같은 baselines dict")
            return 0
        # diff 위치 찾기
        for sname, sdata_a in a["scenarios"].items():
            if sdata_a != b["scenarios"][sname]:
                print(f"[FAIL] {sname} 가 결정론 위반:")
                print(f"  a: {sdata_a}")
                print(f"  b: {b['scenarios'][sname]}")
        return 1

    data = collect_baselines(include_timestamp=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] baselines 저장 → {out_path}")
    # 사용자용 요약 표
    print()
    print(f'{"Scenario":<18} {"URS dim":>15}   {"P1":>6} {"P2":>6} {"P6":>6} {"P7":>6}   {"norm":>6}   {"geo total":>9}   {"hard":>4} {"soft":>4}')
    print("-" * 110)
    for name, sdata in data["scenarios"].items():
        ps = sdata["p_series"]
        gq = sdata["geometric_quality"]
        bw, bh = sdata["meta"]["building_dim_mm"]
        def f(v):
            return "   None" if v is None else f"{v:6.4f}"
        p1 = ps["P1_flow_monotonicity"]["raw"]
        p2 = ps["P2_adjacency"]["raw"]
        p6 = ps["P6_cleaning_access"]["raw"]
        p7 = ps["P7_compactness"]["raw"]
        norm = sdata["p_series_normalized"]
        gt = gq["total"]
        h = gq["hard_violations_count"]
        s = gq["soft_violations_count"]
        print(f'{name:<18} {f"{int(bw)}×{int(bh)}":>15}   {f(p1)} {f(p2)} {f(p6)} {f(p7)}   {f(norm)}   {gt:>9.2f}   {h:>4} {s:>4}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
