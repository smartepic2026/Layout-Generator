"""CP-SAT 모델 컴파일러 — Phase C0 최소 버전 (D-015).

목적: spec 의 일부 방을 CP-SAT 변수 (격자 (x, y) 위치) 로 컴파일하고, 격자
"안 겹침 + 캔버스 안" 제약만 박는다. C0 는 골격 검증 — 점수 연동·zone·
adjacency 제약·정제실 분리·장비 좌표는 **모두 C1 이후**.

분리 원칙 (C0):
- 본 파일은 *모델 빌딩만 수행*. cp_model.CpModel 인스턴스 + 메타 (격자
  해상도, 방 ↔ 변수 매핑) 를 반환. 풀이는 cpsat_solver.solve() 가 담당.
- 변수 자료형: 정수 격자 cell index (mm 단위는 격자 → mm 환산 후 Layout 에 박음).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ortools.sat.python import cp_model

from src.contract.schemas import Room, RuleEngineOutput


# 방 크기 결정 정책 — 방 한 변 = √area_m2 × FACTOR (m).
# [D-016 진단] 1.4 (1.96× 면적) 로 잡으면 zone stripe 에 못 들어가 INFEASIBLE.
# 1.0 으로 둠 — 룰엔진 area_m2 가 권장 면적이고 솔버가 aspect [0.7, 1.4] 안에서
# 자유롭게 변동. (aspect 변동으로 자연스러운 통로 여유 확보)
ROOM_AREA_TO_SIDE_FACTOR: float = 1.0

# 격자 해상도 — 1 cell = 500mm. 78500×42500mm 캔버스라면 157×85 격자.
# 변수 수가 격자 면적의 O(N·M) 이라 해상도 ↓ 시 풀이시간 ↑. 500mm 가 GMP
# 도면의 의미있는 최소 단위 (도어 폭 1000mm 의 절반).
DEFAULT_GRID_RESOLUTION_MM: int = 500


@dataclass
class RoomVars:
    """한 방의 CP-SAT 변수 집합."""
    room: Room
    w_cells: int                       # 격자 칸 폭 (= ceil(side_mm / grid_mm))
    h_cells: int                       # 격자 칸 높이
    x_var: cp_model.IntVar             # 좌상단 x (격자 셀 단위)
    y_var: cp_model.IntVar             # 좌상단 y
    x_interval: cp_model.IntervalVar   # AddNoOverlap2D 용
    y_interval: cp_model.IntervalVar


@dataclass
class CompiledModel:
    """spec → CP-SAT 모델. cpsat_solver.solve() 의 입력."""
    model: cp_model.CpModel
    grid_resolution_mm: int
    canvas_w_cells: int
    canvas_h_cells: int
    canvas_w_mm: int
    canvas_h_mm: int
    room_vars: list[RoomVars] = field(default_factory=list)
    selected_room_ids: list[str] = field(default_factory=list)


def _room_side_cells(room: Room, grid_mm: int) -> int:
    """방 한 변 격자 칸 수 (정사각 가정)."""
    side_m = (room.area_m2 ** 0.5) * ROOM_AREA_TO_SIDE_FACTOR
    side_mm = side_m * 1000.0
    return max(1, int(round(side_mm / grid_mm)))


def compile_minimal(
    spec: RuleEngineOutput,
    room_ids: list[str],
    canvas_w_mm: int,
    canvas_h_mm: int,
    grid_resolution_mm: int = DEFAULT_GRID_RESOLUTION_MM,
) -> CompiledModel:
    """C0 최소 모델 — `room_ids` 의 방을 캔버스에 안 겹치게 배치.

    제약 (hard):
      H1. 모든 방의 (x, y, w, h) bbox 가 캔버스 [0, canvas_w/h_cells] 안.
      H2. 방끼리 AddNoOverlap2D — 안 겹침.

    목적함수: 좌상단 모으기 (Σ x + Σ y 최소화). C1 에서 P-series 점수로 교체.

    누락 방 (spec.rooms 에 없는 id) 은 silent skip (호출자 책임).
    """
    canvas_w_cells = canvas_w_mm // grid_resolution_mm
    canvas_h_cells = canvas_h_mm // grid_resolution_mm

    rooms_by_id = {r.id: r for r in spec.rooms}
    selected = [rooms_by_id[rid] for rid in room_ids if rid in rooms_by_id]

    model = cp_model.CpModel()
    room_vars: list[RoomVars] = []

    for room in selected:
        w_c = _room_side_cells(room, grid_resolution_mm)
        h_c = w_c  # 정사각 가정 (C0)
        # 변수: 좌상단 (x, y). 캔버스 안에 들어가도록 도메인 제한 (H1).
        x = model.NewIntVar(0, canvas_w_cells - w_c, f"x_{room.id}")
        y = model.NewIntVar(0, canvas_h_cells - h_c, f"y_{room.id}")
        # AddNoOverlap2D 는 IntervalVar 를 받음.
        x_int = model.NewFixedSizeIntervalVar(x, w_c, f"xi_{room.id}")
        y_int = model.NewFixedSizeIntervalVar(y, h_c, f"yi_{room.id}")
        room_vars.append(RoomVars(room, w_c, h_c, x, y, x_int, y_int))

    # H2 — 방 간 안 겹침
    if len(room_vars) >= 2:
        model.AddNoOverlap2D(
            [rv.x_interval for rv in room_vars],
            [rv.y_interval for rv in room_vars],
        )

    # 목적함수 (C0 임시) — 좌상단 모으기. C1 에서 점수 기반으로 교체.
    if room_vars:
        model.Minimize(sum(rv.x_var + rv.y_var for rv in room_vars))

    return CompiledModel(
        model=model,
        grid_resolution_mm=grid_resolution_mm,
        canvas_w_cells=canvas_w_cells,
        canvas_h_cells=canvas_h_cells,
        canvas_w_mm=canvas_w_mm,
        canvas_h_mm=canvas_h_mm,
        room_vars=room_vars,
        selected_room_ids=[rv.room.id for rv in room_vars],
    )


# ══════════════════════════════════════════════════════════════════════
# Phase C1a — 전체 방 + hard 제약. 점수 목적함수는 C1b. (D-016)
# ══════════════════════════════════════════════════════════════════════
# C1a 정책:
#   - 직사각 (w, h 분리) — w/h_target = √area_m2 × 1.4 × 1000mm 의 aspect [0.7, 1.4].
#   - hard 제약:
#       H1. 캔버스 안 (x + w ≤ W, y + h ≤ H).
#       H2. 방끼리 안 겹침 (AddNoOverlap2D).
#       H3. zone 영역 분리 — aux/process/nc 가 캔버스 좌/중/우 stripe 에 들어감.
#           corridor 는 process 안에서 자유 (양옆 corridor stripe 가 process zone 안).
#       H4. adjacency 인접 — spec.adjacency 의 door/shared_wall 쌍은 중심점
#           맨해튼 거리 ≤ ADJ_MAX (default 25m). 너무 멀어지면 hard violation.
#   - 목적함수: 좌상단 모으기 (임시). C1b 에서 P-series surrogate 교체.
ADJ_MAX_DEFAULT_MM: int = 25_000  # 인접 쌍 중심 거리 한계 (Manhattan)
ASPECT_MIN: float = 0.7
ASPECT_MAX: float = 1.4


@dataclass
class RoomVarsC1a:
    room: Room
    w_var: cp_model.IntVar
    h_var: cp_model.IntVar
    x_var: cp_model.IntVar
    y_var: cp_model.IntVar
    x_interval: cp_model.IntervalVar
    y_interval: cp_model.IntervalVar
    side_target_cells: int


@dataclass
class AdjPairVars:
    """adjacency hard 제약을 위해 만든 |dx|, |dy| 변수. C1b 가 cost 로 재사용."""
    from_id: str
    to_id: str
    abs_dx: cp_model.IntVar
    abs_dy: cp_model.IntVar


@dataclass
class CompiledModelC1a:
    model: cp_model.CpModel
    grid_resolution_mm: int
    canvas_w_cells: int
    canvas_h_cells: int
    canvas_w_mm: int
    canvas_h_mm: int
    room_vars: dict                              # room_id → RoomVarsC1a
    # 진단 — 어떤 제약을 활성/완화 했나
    enforce_zones: bool
    enforce_adjacency: bool
    adj_max_mm: int
    n_adjacency_pairs: int                       # 실제 추가된 adjacency hard pair 수
    adj_pair_vars: list = field(default_factory=list)  # AdjPairVars list (C1b reuse)
    has_objective: bool = True                   # compile_c1a 가 objective 박았나


def _zone_x_bounds(
    spec: RuleEngineOutput,
    canvas_w_cells: int,
) -> dict[str, tuple[int, int]]:
    """zone 별 x 도메인 (cell). aux 좌, process 가운데, nc 우.

    spec.zones 의 분포를 봐서 stripe 비율을 단순히 결정 (C1a 단순화).
    실제 area 비율 보정은 C1b 에서.
    """
    aux_end = int(canvas_w_cells * 0.20)
    nc_start = int(canvas_w_cells * 0.82)
    bounds: dict[str, tuple[int, int]] = {}
    for rid in spec.zones.auxiliary_zone:
        bounds[rid] = (0, aux_end)
    for rid in spec.zones.nc_zone:
        bounds[rid] = (nc_start, canvas_w_cells)
    for rid in spec.zones.process_zone:
        # process: aux_end ~ nc_start. corridor 는 약간 더 여유.
        bounds[rid] = (max(0, aux_end - int(canvas_w_cells * 0.03)),
                       min(canvas_w_cells, nc_start + int(canvas_w_cells * 0.03)))
    return bounds


def compile_c1a(
    spec: RuleEngineOutput,
    canvas_w_mm: int,
    canvas_h_mm: int,
    grid_resolution_mm: int = DEFAULT_GRID_RESOLUTION_MM,
    enforce_zones: bool = True,
    enforce_adjacency: bool = True,
    adj_max_mm: int = ADJ_MAX_DEFAULT_MM,
    aspect_min: float = ASPECT_MIN,
    aspect_max: float = ASPECT_MAX,
    add_compactness_objective: bool = True,
) -> CompiledModelC1a:
    """C1a — 전체 spec.rooms 에 대해 hard 제약 (H1~H4) 모델 생성.

    완화 플래그 (`enforce_zones`, `enforce_adjacency`) — infeasible/timeout 시
    어떤 제약이 충돌인지 격리하기 위한 진단용. False 면 해당 제약 skip.
    """
    canvas_w_cells = canvas_w_mm // grid_resolution_mm
    canvas_h_cells = canvas_h_mm // grid_resolution_mm

    model = cp_model.CpModel()
    room_vars: dict[str, RoomVarsC1a] = {}

    zone_bounds = _zone_x_bounds(spec, canvas_w_cells) if enforce_zones else {}

    for room in spec.rooms:
        # 정사각 한 변 → aspect [aspect_min, aspect_max] 직사각.
        # FACTOR=1.0 (D-016 진단). 방 면적 ≈ [aspect_min², aspect_max²] × area_m2.
        side_target_cells = max(
            2, int(round((room.area_m2 ** 0.5) * 1000.0 * ROOM_AREA_TO_SIDE_FACTOR
                         / grid_resolution_mm))
        )
        w_min = max(2, int(round(side_target_cells * aspect_min)))
        w_max = max(w_min + 1, int(round(side_target_cells * aspect_max)))
        h_min = max(2, int(round(side_target_cells * aspect_min)))
        h_max = max(h_min + 1, int(round(side_target_cells * aspect_max)))

        # x_var 도메인 = zone bounds (∩ 캔버스). zone 미적용 시 캔버스 전체.
        if enforce_zones and room.id in zone_bounds:
            x_lo, x_hi = zone_bounds[room.id]
        else:
            x_lo, x_hi = 0, canvas_w_cells
        # w 가 zone 폭보다 크면 도메인 충돌 → 미리 clamp
        zone_w = x_hi - x_lo
        if w_max > zone_w:
            w_max = max(2, zone_w)
        if w_min > w_max:
            w_min = w_max
        if h_max > canvas_h_cells:
            h_max = canvas_h_cells
        if h_min > h_max:
            h_min = h_max

        w_var = model.NewIntVar(w_min, w_max, f"w_{room.id}")
        h_var = model.NewIntVar(h_min, h_max, f"h_{room.id}")
        x_var = model.NewIntVar(x_lo, x_hi - w_min, f"x_{room.id}")
        y_var = model.NewIntVar(0, canvas_h_cells - h_min, f"y_{room.id}")
        # H1 캔버스 안 + zone 우측
        model.Add(x_var + w_var <= x_hi)
        model.Add(y_var + h_var <= canvas_h_cells)

        # IntervalVar — start + size == end (ortools 자동 보장)
        x_end = model.NewIntVar(x_lo + w_min, x_hi, f"xe_{room.id}")
        y_end = model.NewIntVar(h_min, canvas_h_cells, f"ye_{room.id}")
        model.Add(x_end == x_var + w_var)
        model.Add(y_end == y_var + h_var)
        x_int = model.NewIntervalVar(x_var, w_var, x_end, f"xi_{room.id}")
        y_int = model.NewIntervalVar(y_var, h_var, y_end, f"yi_{room.id}")

        room_vars[room.id] = RoomVarsC1a(
            room=room, w_var=w_var, h_var=h_var, x_var=x_var, y_var=y_var,
            x_interval=x_int, y_interval=y_int,
            side_target_cells=side_target_cells,
        )

    # H2 안 겹침
    if room_vars:
        model.AddNoOverlap2D(
            [rv.x_interval for rv in room_vars.values()],
            [rv.y_interval for rv in room_vars.values()],
        )

    # H4 인접 — 중심점 맨해튼 거리 ≤ adj_max_cells
    adj_pair_count = 0
    adj_pair_vars: list[AdjPairVars] = []
    if enforce_adjacency:
        adj_max_cells = adj_max_mm // grid_resolution_mm
        for adj in spec.adjacency:
            if adj.from_id not in room_vars or adj.to_id not in room_vars:
                continue
            if adj.relationship == "passthrough_only":
                continue
            a = room_vars[adj.from_id]
            b = room_vars[adj.to_id]
            dx = model.NewIntVar(-canvas_w_cells, canvas_w_cells, f"dx_{adj.from_id}_{adj.to_id}_{adj_pair_count}")
            dy = model.NewIntVar(-canvas_h_cells, canvas_h_cells, f"dy_{adj.from_id}_{adj.to_id}_{adj_pair_count}")
            model.Add(dx == a.x_var - b.x_var)
            model.Add(dy == a.y_var - b.y_var)
            adx = model.NewIntVar(0, canvas_w_cells, f"adx_{adj_pair_count}")
            ady = model.NewIntVar(0, canvas_h_cells, f"ady_{adj_pair_count}")
            model.AddAbsEquality(adx, dx)
            model.AddAbsEquality(ady, dy)
            model.Add(adx + ady <= adj_max_cells)
            adj_pair_vars.append(AdjPairVars(
                from_id=adj.from_id, to_id=adj.to_id,
                abs_dx=adx, abs_dy=ady,
            ))
            adj_pair_count += 1

    # 목적함수 (C1a 임시) — 좌상단 모으기. C1b 가 P-series surrogate 로 override.
    if room_vars and add_compactness_objective:
        model.Minimize(sum(rv.x_var + rv.y_var for rv in room_vars.values()))

    return CompiledModelC1a(
        model=model,
        grid_resolution_mm=grid_resolution_mm,
        canvas_w_cells=canvas_w_cells,
        canvas_h_cells=canvas_h_cells,
        canvas_w_mm=canvas_w_mm,
        canvas_h_mm=canvas_h_mm,
        room_vars=room_vars,
        enforce_zones=enforce_zones,
        enforce_adjacency=enforce_adjacency,
        adj_max_mm=adj_max_mm,
        n_adjacency_pairs=adj_pair_count,
        adj_pair_vars=adj_pair_vars,
        has_objective=add_compactness_objective,
    )


# ══════════════════════════════════════════════════════════════════════
# Phase C1b — P-series surrogate 목적함수 (D-017)
# ══════════════════════════════════════════════════════════════════════
# 점수 surrogate 가중치 (P-series 점수 weight 비율 반영):
#   P1 (흐름축 단조) — P_WEIGHTS["P1"]=10
#   P2 (link 거리)   — P_WEIGHTS["P2"]=6 (이미 hard 25m 박힘. surrogate 로 더 가깝게)
#   tie-breaker (좌상단 모으기) — 가중치 1
P1_WEIGHT_DEFAULT: int = 100
P2_WEIGHT_DEFAULT: int = 60
TIEBREAKER_WEIGHT_DEFAULT: int = 1


def compile_c1b(
    spec: RuleEngineOutput,
    canvas_w_mm: int,
    canvas_h_mm: int,
    grid_resolution_mm: int = DEFAULT_GRID_RESOLUTION_MM,
    enforce_zones: bool = True,
    enforce_adjacency: bool = True,
    adj_max_mm: int = ADJ_MAX_DEFAULT_MM,
    p1_weight: int = P1_WEIGHT_DEFAULT,
    p2_weight: int = P2_WEIGHT_DEFAULT,
    tiebreaker_weight: int = TIEBREAKER_WEIGHT_DEFAULT,
    aspect_min: float = ASPECT_MIN,
    aspect_max: float = ASPECT_MAX,
) -> CompiledModelC1a:
    """C1b — C1a 의 hard 제약 위에 P-series surrogate 목적함수 얹음.

    Surrogate 항 (작을수록 좋음 → minimize):
      P1 surrogate: PPO 인접 쌍 (i, i+1) 의 흐름축(가로) 단조 페널티.
        cx_i ≤ cx_{i+1} 위반 시 pen = max(0, cx_i - cx_{i+1}).
        cx = 2*x + w (격자 셀 단위, 정수 표현 위해 ×2 스케일).
      P2 surrogate: adjacency hard 제약 변수 (|dx| + |dy|) 의 합 — 25m 한계
        안에서 더 가깝게.
      tie-breaker: Σ (x + y) — 좌상단 모으기 (P-series 영향 작음, 약하게).

    가중치 (P-series weight 비율): P1=100, P2=60, tie=1. 정수.
    """
    # H1~H4 hard 제약은 C1a 그대로. 다만 objective 는 안 박음 (여기서 박을 거).
    compiled = compile_c1a(
        spec,
        canvas_w_mm=canvas_w_mm,
        canvas_h_mm=canvas_h_mm,
        grid_resolution_mm=grid_resolution_mm,
        enforce_zones=enforce_zones,
        enforce_adjacency=enforce_adjacency,
        adj_max_mm=adj_max_mm,
        aspect_min=aspect_min,
        aspect_max=aspect_max,
        add_compactness_objective=False,  # objective 는 C1b 가 박음
    )
    model = compiled.model
    cw = compiled.canvas_w_cells

    objective_terms = []

    # P1 surrogate — PPO 인접 쌍 흐름축(가로) 단조 페널티
    ppo = spec.flow_paths.product_process_order
    p1_pen_sum = []
    for i in range(len(ppo) - 1):
        a_id, b_id = ppo[i], ppo[i + 1]
        if a_id not in compiled.room_vars or b_id not in compiled.room_vars:
            continue
        a = compiled.room_vars[a_id]
        b = compiled.room_vars[b_id]
        # cx_a (×2 스케일) = 2*x_a + w_a, cx_b = 2*x_b + w_b
        # diff = cx_a - cx_b. pen = max(0, diff). 페널티 = a 가 b 우측이면 발생.
        diff = model.NewIntVar(-2 * cw, 2 * cw, f"p1_diff_{i}")
        model.Add(diff == (2 * a.x_var + a.w_var) - (2 * b.x_var + b.w_var))
        pen = model.NewIntVar(0, 2 * cw, f"p1_pen_{i}")
        model.AddMaxEquality(pen, [diff, 0])
        p1_pen_sum.append(pen)

    if p1_pen_sum:
        objective_terms.append(p1_weight * sum(p1_pen_sum))

    # P2 surrogate — adjacency 거리 합 (hard 제약 변수 재사용)
    if compiled.adj_pair_vars:
        p2_dist_sum = sum(ap.abs_dx + ap.abs_dy for ap in compiled.adj_pair_vars)
        objective_terms.append(p2_weight * p2_dist_sum)

    # tie-breaker — 좌상단 모으기 (작은 가중치)
    if compiled.room_vars and tiebreaker_weight > 0:
        objective_terms.append(
            tiebreaker_weight * sum(rv.x_var + rv.y_var for rv in compiled.room_vars.values())
        )

    if objective_terms:
        model.Minimize(sum(objective_terms))

    compiled.has_objective = True
    return compiled


# ══════════════════════════════════════════════════════════════════════
# Phase C3a — 방 1개 안 장비 CP-SAT 배치 (D-018)
# ══════════════════════════════════════════════════════════════════════
# 정책 (D-018):
#   - 장비 좌표 (x, y) 변수. W/D 는 *실제 W_mm/D_mm* 고정 (B-001 시각 축소 분리).
#   - 방 rect (mm) 은 인자로 받음 (호출자 책임 — strip-band/C1a/C1b 어디서든).
#   - hard: H1 방 안 (inner margin), H2 안 겹침 (AddNoOverlap2D), H3 장비 간격 (eq_gap).
#   - 목적: P1 surrogate (sort_order 단조, 흐름축 가로) + P7 surrogate
#     (장비 외접 bbox perimeter 최소화).
C3A_WALL_MARGIN_MM_DEFAULT: int = 500     # 벽 ↔ 장비 (B-001 — 실제 mm 모드 가정)
C3A_EQ_GAP_MM_DEFAULT: int = 500          # 장비 ↔ 장비 (clearance proxy)
C3A_P1_WEIGHT_DEFAULT: int = 100
C3A_P7_WEIGHT_DEFAULT: int = 20


@dataclass
class EquipmentVarsC3a:
    eq: object                     # Equipment (forward-decl 회피)
    x_var: cp_model.IntVar
    y_var: cp_model.IntVar
    x_int: cp_model.IntervalVar
    y_int: cp_model.IntervalVar
    w_cells: int                   # 실제 W_mm / grid
    h_cells: int


@dataclass
class CompiledRoomC3a:
    model: cp_model.CpModel
    grid_resolution_mm: int
    room_id: str
    room_rect_mm: tuple             # (x, y, w, h) mm — 호출자 입력 그대로
    inner_x_cells: int              # inner 좌상단 cell
    inner_y_cells: int
    inner_w_cells: int
    inner_h_cells: int
    eq_vars: list                   # EquipmentVarsC3a
    has_objective: bool


def compile_room_c3a(
    room,                                       # Room
    room_rect_mm: tuple,                        # (x, y, w, h) mm
    grid_resolution_mm: int = DEFAULT_GRID_RESOLUTION_MM,
    wall_margin_mm: int = C3A_WALL_MARGIN_MM_DEFAULT,
    eq_gap_mm: int = C3A_EQ_GAP_MM_DEFAULT,
    add_p1_surrogate: bool = True,
    add_p7_surrogate: bool = True,
    p1_weight: int = C3A_P1_WEIGHT_DEFAULT,
    p7_weight: int = C3A_P7_WEIGHT_DEFAULT,
) -> CompiledRoomC3a:
    """C3a — 한 방 안 장비 N개 CP-SAT 배치 모델.

    호출자 책임: room.equipment 의 W_mm/D_mm + sort_order 이미 채워져 있어야 함.
    """
    g = grid_resolution_mm
    rx, ry, rw, rh = room_rect_mm
    inner_x = int(rx // g) + max(1, wall_margin_mm // g)
    inner_y = int(ry // g) + max(1, wall_margin_mm // g)
    inner_w = max(1, int(rw // g) - 2 * max(1, wall_margin_mm // g))
    inner_h = max(1, int(rh // g) - 2 * max(1, wall_margin_mm // g))
    gap_cells = max(1, eq_gap_mm // g)

    model = cp_model.CpModel()
    eq_vars: list[EquipmentVarsC3a] = []
    for idx, eq in enumerate(room.equipment):
        w_c = max(1, int(round(eq.W_mm / g)))
        h_c = max(1, int(round(eq.D_mm / g)))
        # H1 방 안 — gap 마진은 양옆/위아래에 한 칸씩 (안 겹침 보조)
        x_lo = inner_x
        x_hi = inner_x + max(w_c, inner_w) - w_c  # 도메인 상한
        y_lo = inner_y
        y_hi = inner_y + max(h_c, inner_h) - h_c
        x = model.NewIntVar(x_lo, max(x_lo, inner_x + inner_w - w_c), f"x_{room.id}_{idx}")
        y = model.NewIntVar(y_lo, max(y_lo, inner_y + inner_h - h_c), f"y_{room.id}_{idx}")
        x_int = model.NewFixedSizeIntervalVar(x, w_c + gap_cells, f"xi_{room.id}_{idx}")
        y_int = model.NewFixedSizeIntervalVar(y, h_c + gap_cells, f"yi_{room.id}_{idx}")
        eq_vars.append(EquipmentVarsC3a(
            eq=eq, x_var=x, y_var=y, x_int=x_int, y_int=y_int,
            w_cells=w_c, h_cells=h_c,
        ))

    # H2 안 겹침 (gap_cells 만큼 padding 된 interval 로)
    if len(eq_vars) >= 2:
        model.AddNoOverlap2D(
            [e.x_int for e in eq_vars],
            [e.y_int for e in eq_vars],
        )

    obj_terms = []
    range_bound = 2 * max(inner_x + inner_w, inner_y + inner_h) + 4

    # P1 surrogate — sort_order 인접 쌍 흐름축(가로) 단조
    if add_p1_surrogate:
        sorted_eqs = sorted(
            [(i, e) for i, e in enumerate(eq_vars) if e.eq.sort_order is not None],
            key=lambda t: t[1].eq.sort_order,
        )
        p1_pens = []
        for k in range(len(sorted_eqs) - 1):
            i_a, a = sorted_eqs[k]
            i_b, b = sorted_eqs[k + 1]
            if a.eq.sort_order == b.eq.sort_order:
                continue  # [D-003] 병렬 — 중립
            diff = model.NewIntVar(-range_bound, range_bound, f"p1_diff_{room.id}_{k}")
            # cx = 2*x + w (×2 스케일)
            model.Add(diff == (2 * a.x_var + a.w_cells) - (2 * b.x_var + b.w_cells))
            pen = model.NewIntVar(0, range_bound, f"p1_pen_{room.id}_{k}")
            model.AddMaxEquality(pen, [diff, 0])
            p1_pens.append(pen)
        if p1_pens:
            obj_terms.append(p1_weight * sum(p1_pens))

    # P7 surrogate — 장비 외접 bbox perimeter 최소화
    if add_p7_surrogate and len(eq_vars) >= 2:
        x_min = model.NewIntVar(inner_x, inner_x + inner_w, f"xmin_{room.id}")
        y_min = model.NewIntVar(inner_y, inner_y + inner_h, f"ymin_{room.id}")
        x_max = model.NewIntVar(inner_x, inner_x + inner_w, f"xmax_{room.id}")
        y_max = model.NewIntVar(inner_y, inner_y + inner_h, f"ymax_{room.id}")
        model.AddMinEquality(x_min, [e.x_var for e in eq_vars])
        model.AddMinEquality(y_min, [e.y_var for e in eq_vars])
        x_ends = []
        y_ends = []
        for k, e in enumerate(eq_vars):
            xe = model.NewIntVar(inner_x, inner_x + inner_w, f"xe_{room.id}_{k}")
            ye = model.NewIntVar(inner_y, inner_y + inner_h, f"ye_{room.id}_{k}")
            model.Add(xe == e.x_var + e.w_cells)
            model.Add(ye == e.y_var + e.h_cells)
            x_ends.append(xe)
            y_ends.append(ye)
        model.AddMaxEquality(x_max, x_ends)
        model.AddMaxEquality(y_max, y_ends)
        env_perim = model.NewIntVar(0, 4 * (inner_w + inner_h), f"env_perim_{room.id}")
        model.Add(env_perim == (x_max - x_min) + (y_max - y_min))
        obj_terms.append(p7_weight * env_perim)

    if obj_terms:
        model.Minimize(sum(obj_terms))

    return CompiledRoomC3a(
        model=model,
        grid_resolution_mm=g,
        room_id=room.id,
        room_rect_mm=room_rect_mm,
        inner_x_cells=inner_x,
        inner_y_cells=inner_y,
        inner_w_cells=inner_w,
        inner_h_cells=inner_h,
        eq_vars=eq_vars,
        has_objective=bool(obj_terms),
    )
