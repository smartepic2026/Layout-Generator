"""Reward Function — 도면 채점.

3계층 점수:
  1. Hard penalty (C1~C10)  — 위반 시 큰 음수. RL이 절대 피해야 함.
  2. Soft penalty (C9 + 룰 ratio + AL completeness)
  3. Geometric quality
       · 동선 분리도 (personnel/material/waste 경로 교차 없음)
       · 차압 cascade 평활도
       · 복도 효율 (직사각형 정렬)
       · 장비 clearance 마진
       · 면적 비율 fit
       · 미적 품질 (대칭/정렬/Room aspect ratio)

return: ScoreReport(total, hard_violations, soft_violations, breakdown)

RL의 step reward로 쓰일 때는 ScoreReport.total을 baseline 대비 delta로 줘도 됨.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.drawing_agent.layout_solver import Layout, Rect
from src.rule_engine.schemas import RuleEngineOutput
from src.rule_engine.validators import (
    validate_hard_constraints,
    validate_soft_constraints,
)
from src.rule_engine.working_state import WorkingState


@dataclass
class ScoreReport:
    total: float
    hard_violations: list[dict] = field(default_factory=list)
    soft_violations: list[dict] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.hard_violations


# 가중치 (튜닝 가능)
W_HARD = -50.0     # 1건당
W_SOFT = -5.0
W_FLOW_SEPARATION = 8.0
W_PRESSURE_SMOOTH = 6.0
W_CORRIDOR_EFFICIENCY = 4.0
W_EQUIPMENT_MARGIN = 5.0
W_AREA_RATIO_FIT = 3.0
W_AESTHETICS = 4.0


def score(spec: RuleEngineOutput, layout: Optional[Layout] = None) -> ScoreReport:
    """spec(+ optional layout)에 점수를 매김.

    layout이 None이면 spec만으로 평가 가능한 항목만 계산 (Hard/Soft).
    layout이 주어지면 Geometric quality 항목 추가.
    """
    breakdown: dict[str, float] = {}

    # ── Hard constraints ──
    state = _rebuild_working_state(spec)
    hard = validate_hard_constraints(state)
    breakdown["hard_penalty"] = W_HARD * len(hard)

    # ── Soft constraints ──
    soft = validate_soft_constraints(state)
    breakdown["soft_penalty"] = W_SOFT * len(soft)

    # 시작값: 100
    total = 100.0 + breakdown["hard_penalty"] + breakdown["soft_penalty"]

    # ── Geometric quality (layout이 있을 때만) ──
    # 일부 항목은 측정 불가(None)일 수 있음 — silent default 대신 명시적 skip.
    if layout is not None:
        items = [
            ("flow_separation",     W_FLOW_SEPARATION,      _flow_separation_quality(spec, layout)),
            ("pressure_smoothness", W_PRESSURE_SMOOTH,      _pressure_cascade_smoothness(spec, layout)),
            ("corridor_efficiency", W_CORRIDOR_EFFICIENCY,  _corridor_efficiency(layout)),
            ("equipment_margin",    W_EQUIPMENT_MARGIN,     _equipment_margin_quality(layout)),
            ("area_ratio_fit",      W_AREA_RATIO_FIT,       _area_ratio_fit(spec, layout)),
            ("aesthetics",          W_AESTHETICS,           _aesthetic_score(layout)),
        ]
        for key, weight, raw in items:
            if raw is None:
                breakdown[key] = None  # 측정 불가 — total 에 합산 안 됨
            else:
                contrib = weight * raw
                breakdown[key] = contrib
                total += contrib

    return ScoreReport(
        total=round(total, 2),
        hard_violations=hard,
        soft_violations=soft,
        breakdown={k: (None if v is None else round(v, 2)) for k, v in breakdown.items()},
    )


# ──────────────────────────────────────────────────────────────────────
# WorkingState 재구축 — validators는 WorkingState를 입력으로 받음
# ──────────────────────────────────────────────────────────────────────
def _rebuild_working_state(spec: RuleEngineOutput) -> WorkingState:
    from src.rule_engine.schemas import URSInput
    ws = WorkingState(urs=URSInput(project_name=spec.project_name))
    for r in spec.rooms:
        ws.rooms[r.id] = r
    for a in spec.airlocks:
        ws.airlocks[a.id] = a
    ws.adjacency = list(spec.adjacency)
    ws.zones = spec.zones
    ws.flow_paths = spec.flow_paths
    ws.constraints = spec.constraints
    return ws


# ──────────────────────────────────────────────────────────────────────
# Geometric quality — 0~1 점수
# ──────────────────────────────────────────────────────────────────────
def _flow_separation_quality(spec: RuleEngineOutput, layout: Layout) -> float:
    """personnel/material/waste 경로의 공간 분리도. corridor 분리 + AL 분리도로 측정.
    v1: supply↔return 분리 + waste exit이 return 통하는지로 단순 측정.
    """
    score = 0.0
    has_sup = "R_SUPPLY_CORRIDOR" in layout.rooms
    has_ret = "R_RETURN_CORRIDOR" in layout.rooms
    if has_sup and has_ret:
        score += 0.5
    # waste path가 return을 거치는지
    if "R_RETURN_CORRIDOR" in spec.flow_paths.waste_exit:
        score += 0.25
    # personnel exit이 return을 거치는지
    if "R_RETURN_CORRIDOR" in spec.flow_paths.personnel_exit:
        score += 0.25
    return min(score, 1.0)


def _pressure_cascade_smoothness(
    spec: RuleEngineOutput, layout: Layout
) -> Optional[float]:
    """인접 Room 간 차압 차이의 표준편차 → 작을수록 좋음.

    S4 수정 (silent good-score 차단): 모든 Room.DP=0 (스키마 default 로 들어온
    채로 변경 없음) 인 경우 "측정 불가"로 None 반환. 이전 동작은 std=0 → 1.0
    만점이라 망가진 도면도 통과했음.
    """
    rooms_by_id = {r.id: r for r in spec.rooms}
    # 측정 가능 조건 1: 어느 한 방이라도 의미있는 DP 가 있어야 함
    if not any(r.differential_pressure_Pa for r in spec.rooms):
        return None  # 측정 불가 — 모든 DP=0 (스키마 default 인 채)
    diffs = []
    for adj in spec.adjacency:
        a = rooms_by_id.get(adj.from_id)
        b = rooms_by_id.get(adj.to_id)
        if not a or not b:
            continue
        if a.clean_grade != b.clean_grade:
            diffs.append(abs(a.differential_pressure_Pa - b.differential_pressure_Pa))
    if not diffs:
        return None  # 측정 가능한 등급 경계 쌍이 없음
    mean = sum(diffs) / len(diffs)
    var = sum((d - mean) ** 2 for d in diffs) / len(diffs)
    std = var ** 0.5
    # 표준편차가 5Pa 이하면 1.0, 20Pa 이상이면 0.0
    return max(0.0, min(1.0, 1.0 - (std - 5.0) / 15.0))


def _corridor_efficiency(layout: Layout) -> float:
    """복도의 aspect ratio (직사각형 길쭉함). 가로/세로 비율 ≥ 4 권장."""
    ratios = []
    for pr in layout.rooms.values():
        if not pr.room.is_corridor:
            continue
        long, short = max(pr.rect.w, pr.rect.h), min(pr.rect.w, pr.rect.h)
        if short > 0:
            ratios.append(long / short)
    if not ratios:
        return 0.5
    avg = sum(ratios) / len(ratios)
    # ratio 4 이상이면 1.0, 1.5 이하면 0.0
    return max(0.0, min(1.0, (avg - 1.5) / 2.5))


def _equipment_margin_quality(layout: Layout) -> float:
    """장비 ↔ 장비 최소 간격이 1000mm 이상인 비율."""
    total = 0
    ok = 0
    for pr in layout.rooms.values():
        equips = pr.equipment
        for i, ei in enumerate(equips):
            for ej in equips[i+1:]:
                total += 1
                gap = _rect_gap(ei.rect, ej.rect)
                if gap >= 1000:
                    ok += 1
    return ok / total if total else 0.7


def _area_ratio_fit(
    spec: RuleEngineOutput, layout: Optional[Layout] = None
) -> Optional[float]:
    """주공정 비율이 50% 근처에 있을수록 좋음.

    S1 수정 (silent default 차단): 이전엔 `constraints.process_zone_area_ratio
    .get("current", 0.5)` 라 팀원 출력에 'current' 키 없으면 silent 0.5
    default → 모든 도면이 동일 점수. 이제 우선순위:
      1. layout 으로부터 process_zone 면적 비율 실측 계산
      2. constraints 의 'current' 키 (rule_engine 이 명시적으로 채운 경우)
      3. 어느 쪽도 없으면 None (측정 불가)
    """
    cur: Optional[float] = None

    # 1) layout 실측 (가장 신뢰도 높음)
    if layout is not None:
        proc_area = 0.0
        total_area = 0.0
        for pr in layout.rooms.values():
            a = pr.rect.w * pr.rect.h  # mm² 비율이라 단위 무관
            total_area += a
            if pr.room.category == "process":
                proc_area += a
        if total_area > 0:
            cur = proc_area / total_area

    # 2) constraints 의 명시적 'current' (rule_engine 이 채운 경우만)
    if cur is None:
        r = spec.constraints.process_zone_area_ratio
        if "current" in r:
            cur = r["current"]

    if cur is None:
        return None  # 측정 불가

    # 50% 근처에서 최대치, 40% 또는 70%에서 0
    delta = abs(cur - 0.55)
    return max(0.0, 1.0 - delta / 0.15)


def _aesthetic_score(layout: Layout) -> float:
    """Room aspect ratio가 0.5~2 사이면 좋음 (너무 길쭉하지 않음).
    is_corridor 제외."""
    if not layout.rooms:
        return 0.5
    scores = []
    for pr in layout.rooms.values():
        if pr.room.is_corridor:
            continue
        if pr.rect.w <= 0 or pr.rect.h <= 0:
            continue
        ar = pr.rect.w / pr.rect.h
        # log scale: ar=1이면 1.0, ar=0.25 또는 4면 0
        if ar < 1:
            ar = 1 / ar
        scores.append(max(0.0, 1.0 - (ar - 1.0) / 3.0))
    return sum(scores) / len(scores) if scores else 0.5


def _rect_gap(a: Rect, b: Rect) -> float:
    """두 사각형의 최단 거리 (mm). 겹치면 0."""
    dx = max(0, max(a.x, b.x) - min(a.x2, b.x2))
    dy = max(0, max(a.y, b.y) - min(a.y2, b.y2))
    return (dx ** 2 + dy ** 2) ** 0.5


# ══════════════════════════════════════════════════════════════════════
# SPEC scoring skeleton — P1~P8 (GMP_Layout_Engine_SPEC v0.1 §2 + PATCH v0.2 §6)
# ══════════════════════════════════════════════════════════════════════
#
# 활성/보류 (PATCH v0.2 §6.1):
#   ACTIVE   : P1 flow_monotonicity, P2 adjacency, P6 cleaning_access, P7 compactness
#              → 엑셀 `단위공정`/`rule_equipment_layout`/`spec` 시트에서 데이터 도출 가능.
#   DEFERRED : P3 environmental_protection_open, P5 airflow_contaminant_alignment, P8 HSE
#              → 도메인 검수자 부재. 1차에서는 가중치 0 + 데이터 null이면 skip.
#
# 정규화 분모 = 활성 가중치 합 = 23 (PATCH §6.2).
# **이 함수군은 score()에 아직 연결되어 있지 않다 (skeleton).** Phase 1.1에서 수식 채움.
#
# 모든 P_*() 함수는 다음 계약을 따른다:
#   - 반환값 None    = 입력 데이터 부족(또는 미구현) → 가중치 기여 0, breakdown에 null.
#   - 반환값 float   = 0.0~1.0 정규화 점수.
P_WEIGHTS: dict[str, float] = {
    "P1_flow_monotonicity": 10.0,            # ACTIVE
    "P2_adjacency": 6.0,                     # ACTIVE
    "P3_environmental_protection_open": 0.0, # DEFERRED — PATCH §6.2
    "P5_airflow_contaminant_alignment": 0.0, # DEFERRED — PATCH §6.2
    "P6_cleaning_access": 4.0,               # ACTIVE
    "P7_compactness": 3.0,                   # ACTIVE
    "P8_hse": 0.0,                           # DEFERRED — PATCH §6.2
}
P_DEFERRED: frozenset = frozenset({
    "P3_environmental_protection_open",
    "P5_airflow_contaminant_alignment",
    "P8_hse",
})
P_ACTIVE_DENOMINATOR: float = sum(P_WEIGHTS[k] for k in P_WEIGHTS if k not in P_DEFERRED)
# = 10 + 6 + 4 + 3 = 23 (PATCH §6.2 분모)


def _equipment_iter(spec: RuleEngineOutput):
    for room in spec.rooms:
        for eq in room.equipment:
            yield eq


def _p1_flow_monotonicity(spec: RuleEngineOutput, layout: Optional[Layout]) -> Optional[float]:
    """P1 [ACTIVE]. SPEC §2 P1. 공정 단조성: proj(stepᵢ) ≤ proj(stepⱼ) for stepᵢ<stepⱼ.
    필요 데이터: equipment.sort_order + layout 좌표 + room.airflow.direction_vector.
    1차 1단계 작업에서는 수식 미구현 → None.
    """
    return None  # TODO Phase 1.1


def _p2_adjacency(spec: RuleEngineOutput, layout: Optional[Layout]) -> Optional[float]:
    """P2 [ACTIVE]. SPEC §2 P2. connects_to 가까이, incompatible_with 멀리.
    필요 데이터: equipment.connects_to / incompatible_with + layout.
    """
    return None  # TODO Phase 1.1


def _p3_environmental_protection_open(
    spec: RuleEngineOutput, layout: Optional[Layout]
) -> Optional[float]:
    """P3 [DEFERRED]. SPEC §2 P3. open 장비 환경보호 (HEPA 근접, 통로 회피).
    필요 데이터: equipment.open_closed + needs.downflow_booth.
    PATCH §6.2: null 가드 → 데이터 없으면 skip.
    """
    has_data = any(eq.open_closed is not None for eq in _equipment_iter(spec))
    if not has_data:
        return None
    return None  # 데이터 있더라도 1차에서는 수식 미구현


def _p5_airflow_contaminant_alignment(
    spec: RuleEngineOutput, layout: Optional[Layout]
) -> Optional[float]:
    """P5 [DEFERRED]. SPEC §2 P5. 기능-오염 정렬: env 장비는 return쪽으로.
    필요 데이터: equipment.contamination_class + room.airflow.direction_vector.
    """
    has_contam = any(eq.contamination_class for eq in _equipment_iter(spec))
    has_airflow = any(r.airflow is not None for r in spec.rooms)
    if not (has_contam and has_airflow):
        return None
    return None  # 1차 미구현


def _p6_cleaning_access(spec: RuleEngineOutput, layout: Optional[Layout]) -> Optional[float]:
    """P6 [ACTIVE]. SPEC §2 P6. 청소/유지보수 통로 연속성.
    필요 데이터: equipment.clearance_m + layout.
    """
    return None  # TODO Phase 1.1


def _p7_compactness(spec: RuleEngineOutput, layout: Optional[Layout]) -> Optional[float]:
    """P7 [ACTIVE]. SPEC §2 P7. bbox 최소화 (IPS §1: optimal ft²)."""
    return None  # TODO Phase 1.1


def _p8_hse(spec: RuleEngineOutput, layout: Optional[Layout]) -> Optional[float]:
    """P8 [DEFERRED]. SPEC §2 P8. 소음/발열/가연성 격리.
    필요 데이터: equipment.heat_kw / noise_dba / flammable.
    """
    has_data = any(
        (eq.heat_kw is not None) or (eq.noise_dba is not None) or (eq.flammable is not None)
        for eq in _equipment_iter(spec)
    )
    if not has_data:
        return None
    return None


def score_spec_p_series(spec: RuleEngineOutput, layout: Optional[Layout] = None) -> dict:
    """SPEC §2 P1~P8 채점 골격. **score()에 미연결.** Phase 1.1에서 수식 채움.

    Returns:
        {
          "P1_flow_monotonicity": {"raw": float|None, "weight": 10, "contrib": float|None,
                                   "status": "active"|"deferred"|"skipped"},
          ...,
          "_normalized": float,            # contrib합 / 활성 가중치 합(23). PATCH §6.2
          "_active_denominator": 23.0,
        }
    """
    fns = {
        "P1_flow_monotonicity": _p1_flow_monotonicity,
        "P2_adjacency": _p2_adjacency,
        "P3_environmental_protection_open": _p3_environmental_protection_open,
        "P5_airflow_contaminant_alignment": _p5_airflow_contaminant_alignment,
        "P6_cleaning_access": _p6_cleaning_access,
        "P7_compactness": _p7_compactness,
        "P8_hse": _p8_hse,
    }
    out: dict = {}
    weighted_sum = 0.0
    for key, fn in fns.items():
        raw = fn(spec, layout)
        w = P_WEIGHTS[key]
        deferred = key in P_DEFERRED
        if raw is None:
            status = "deferred" if deferred else "skipped"
            contrib: Optional[float] = None
        else:
            status = "deferred" if deferred else "active"
            contrib = w * raw
            weighted_sum += contrib
        out[key] = {
            "raw": raw,
            "weight": w,
            "contrib": round(contrib, 4) if contrib is not None else None,
            "status": status,
        }
    out["_normalized"] = (
        round(weighted_sum / P_ACTIVE_DENOMINATOR, 4) if P_ACTIVE_DENOMINATOR else 0.0
    )
    out["_active_denominator"] = P_ACTIVE_DENOMINATOR
    return out
