"""B3 — NNE Pharmaplan 모범 배치 vs strip-band 점수 회귀 테스트 (D-014).

목적: P-series 수식이 "좋은 배치를 높게 평가" 함을 회귀로 보장.
점수 수식이나 솔버가 바뀌어도 NNE > strip-band 가 깨지면 안 됨.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.golden_nne import compare_with_baseline, load_golden_nne_spec_and_layout
from src.reward.scorer import score_spec_p_series


BASELINES_PATH = Path("output/baselines.json")


@pytest.fixture(scope="module")
def cmp():
    return compare_with_baseline()


def test_nne_layout_loads_with_coords(cmp):
    spec, layout = load_golden_nne_spec_and_layout()
    # 모든 fixture 방이 layout 에 들어옴
    assert len(layout.rooms) == len(spec.rooms)
    # 모든 장비가 좌표 부여됨
    total_eq = sum(len(r.equipment) for r in spec.rooms)
    placed_eq = sum(len(pr.equipment) for pr in layout.rooms.values())
    assert placed_eq == total_eq


def test_nne_p1_p2_p7_active(cmp):
    """좌표 부여됐으므로 active 3개 (P1·P2·P7) 모두 raw 점수 측정 가능."""
    nne = cmp["NNE_golden"]
    for k in ("P1", "P2", "P7"):
        assert nne[k] is not None
        assert 0.0 <= nne[k] <= 1.0


def test_nne_p6_skipped(cmp):
    """clearance_m 부재 → 그대로 None."""
    assert cmp["NNE_golden"]["P6"] is None


def test_nne_norm_above_strip_band_avg(cmp):
    """[D-014 합격 기준] NNE 모범 배치가 strip-band 평균보다 정규화 점수 높음."""
    nne = cmp["NNE_golden"]
    sb = cmp["strip_band_baselines"]
    assert sb, "strip-band baselines 가 비어있음 — output/baselines.json 먼저 생성"
    avg_sb = sum(v["normalized"] for v in sb.values()) / len(sb)
    assert nne["normalized"] > avg_sb, (
        f"NNE norm={nne['normalized']:.4f} 이 strip-band 평균 {avg_sb:.4f} 보다 낮음 → 점수 수식 진단 필요"
    )


def test_nne_p1_beats_strip_band_avg(cmp):
    """P1 (흐름축 단조성): NNE 좌→우 직선 vs strip-band top/bottom zigzag → NNE 우위."""
    nne_p1 = cmp["NNE_golden"]["P1"]
    sb = cmp["strip_band_baselines"]
    avg_sb_p1 = sum(v["P1"] for v in sb.values()) / len(sb)
    assert nne_p1 > avg_sb_p1, (
        f"NNE P1={nne_p1:.4f} 이 strip-band 평균 P1 {avg_sb_p1:.4f} 보다 낮음 → 흐름축 수식 진단"
    )


def test_nne_p7_beats_strip_band_avg(cmp):
    """P7 (packing density): NNE 방 면적이 장비 면적과 잘 맞음 → strip-band 보다 우위."""
    nne_p7 = cmp["NNE_golden"]["P7"]
    sb = cmp["strip_band_baselines"]
    avg_sb_p7 = sum(v["P7"] for v in sb.values()) / len(sb)
    assert nne_p7 > avg_sb_p7, (
        f"NNE P7={nne_p7:.4f} 이 strip-band 평균 P7 {avg_sb_p7:.4f} 보다 낮음 → packing 수식 진단"
    )


def test_nne_is_deterministic():
    """같은 fixture → 같은 점수 (NaN/random 없음)."""
    spec, layout = load_golden_nne_spec_and_layout()
    a = score_spec_p_series(spec, layout=layout)
    b = score_spec_p_series(spec, layout=layout)
    for k in ("P1_flow_monotonicity", "P2_adjacency", "P7_compactness"):
        assert a[k]["raw"] == b[k]["raw"]
    assert a["_normalized"] == b["_normalized"]
