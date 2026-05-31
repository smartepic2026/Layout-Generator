"""C1+C3 통합 파이프라인 회귀 (D-020).

검증:
  1. mab_8000L 통합 파이프라인 수렴 + 28방 모두 좌표.
  2. mab_8000L 의 norm 이 strip-band 보다 향상 (실측 +0.06).
  3. R_PURIFICATION_1 FEASIBLE (fallback 안 함).
  4. solve_c1b 의 aspect 인자 작동 — 좁히면 방 사이즈 spec area 근처.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ortools = pytest.importorskip("ortools")

from scripts.c1c3_pipeline import solve_full_pipeline
from src.drawing_agent.cpsat_solver import solve_c1b
from src.drawing_agent.data import enrich_spec, resolve_building_dims
from src.reward.scorer import score_spec_p_series
from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput


def test_pipeline_mab_8000L_converges():
    """통합 파이프라인 mab_8000L 수렴 — 28방 모두 좌표."""
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    result = solve_full_pipeline(spec, urs_path="examples/urs_mab_8000L.json",
                                  c1_time_s=10.0)
    assert result["c1_status"] in ("OPTIMAL", "FEASIBLE")
    assert len(result["layout"].rooms) == len(spec.rooms)


def test_pipeline_mab_norm_beats_strip_band():
    """mab_8000L norm > strip-band baseline (실측 +0.06)."""
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    result = solve_full_pipeline(spec, urs_path="examples/urs_mab_8000L.json",
                                  c1_time_s=10.0)
    bl = json.loads(Path("output/baselines.json").read_text(encoding="utf-8"))
    sb_norm = bl["scenarios"]["mab_8000L"]["p_series_normalized"]
    cp_norm = result["p_series"]["_normalized"]
    assert cp_norm > sb_norm, (
        f"CP-SAT C1+C3 mab norm={cp_norm:.4f} 가 strip-band {sb_norm:.4f} 보다 낮음"
    )


def test_pipeline_purification_1_no_fallback():
    """[D-020 핵심] mab_8000L 의 R_PURIFICATION_1 (23장비) FEASIBLE — fallback 안 함."""
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    result = solve_full_pipeline(spec, urs_path="examples/urs_mab_8000L.json",
                                  c1_time_s=10.0)
    rr = result["room_reports"].get("R_PURIFICATION_1")
    assert rr is not None
    assert rr["fallback"] is False, f"정제실1 fallback={rr['fallback']}"


def test_solve_c1b_aspect_argument_narrow():
    """solve_c1b 에 aspect=[0.9, 1.1] 좁히면 방 면적이 spec area 근처."""
    spec = run_rule_engine(URSInput(), strict=False)
    enrich_spec(spec)
    bw, bh, _ = resolve_building_dims(spec, urs_path=None)
    # 좁은 aspect — 방 면적이 spec area 의 [0.81, 1.21] 범위
    layout, _ = solve_c1b(
        spec, canvas_w_mm=int(bw), canvas_h_mm=int(bh),
        time_limit_s=3.0, aspect_min=0.9, aspect_max=1.1,
        p1_weight=500, p2_weight=0, tiebreaker_weight=0,
    )
    # R_MEDIA_PREP spec area = 100m². 좁은 aspect 면 81~121m² 안에.
    pr = layout.rooms.get("R_MEDIA_PREP")
    if pr:
        assert 80 <= pr.rect.area_m2 <= 130, (
            f"좁은 aspect 인데 R_MEDIA_PREP 면적 {pr.rect.area_m2:.1f}m² (기대 80-130)"
        )
