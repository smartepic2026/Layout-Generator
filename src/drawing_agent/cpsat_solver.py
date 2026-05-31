"""CP-SAT 솔버 진입점 — Phase C0 (D-015).

`constraint_compiler.compile_minimal()` 의 결과를 풀어, 좌표를 기존 Layout
자료구조 (layout_solver.Layout) 에 채워 반환한다. Layout 인터페이스를 그대로
재사용하므로 renderer.render() / score() 가 변경 없이 동작.

C0 한계:
- 풀이 시간 60초 hard timeout (방 3개면 ms 단위라 충분).
- infeasible → strip-band fallback (기존 layout_solver.solve()).
- 장비 좌표는 본 솔버가 만들지 않음. 호출자가 필요하면 strip-band 의
  `_place_equipment_grid(layout)` 를 별도 호출.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from ortools.sat.python import cp_model

from src.drawing_agent.constraint_compiler import (
    ADJ_MAX_DEFAULT_MM,
    C3A_EQ_GAP_MM_DEFAULT,
    C3A_P1_WEIGHT_DEFAULT,
    C3A_P7_WEIGHT_DEFAULT,
    C3A_WALL_MARGIN_MM_DEFAULT,
    CompiledModel,
    CompiledModelC1a,
    CompiledRoomC3a,
    DEFAULT_GRID_RESOLUTION_MM,
    P1_WEIGHT_DEFAULT,
    P2_WEIGHT_DEFAULT,
    TIEBREAKER_WEIGHT_DEFAULT,
    compile_c1a,
    compile_c1b,
    compile_minimal,
    compile_room_c3a,
)
from src.drawing_agent.layout_solver import Layout, PlacedRoom, Rect
from src.rule_engine.schemas import RuleEngineOutput


CP_STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


@dataclass
class SolveReport:
    """풀이 결과 메타. 디버그/로깅 + 회귀 테스트용."""
    status: str                       # OPTIMAL / FEASIBLE / INFEASIBLE / ...
    status_code: int                  # cp_model.* enum
    objective: Optional[float]        # 목적함수 값 (해 없으면 None)
    wall_time_ms: float               # CP-SAT 풀이 시간 (모델 빌드 제외)
    total_wall_time_ms: float         # 빌드 + 풀이 + Layout 변환 합
    grid_resolution_mm: int
    canvas_dim_cells: tuple[int, int]
    rooms_solved: list[str]


def _placed_layout_from_solution(
    spec: RuleEngineOutput,
    compiled: CompiledModel,
    solver: cp_model.CpSolver,
) -> Layout:
    """solver 의 정수 해를 Layout (mm 좌표) 으로 환산."""
    layout = Layout(
        building_w_mm=float(compiled.canvas_w_mm),
        building_h_mm=float(compiled.canvas_h_mm),
    )
    g = compiled.grid_resolution_mm
    for rv in compiled.room_vars:
        x_mm = solver.Value(rv.x_var) * g
        y_mm = solver.Value(rv.y_var) * g
        w_mm = rv.w_cells * g
        h_mm = rv.h_cells * g
        layout.rooms[rv.room.id] = PlacedRoom(
            room=rv.room,
            rect=Rect(x_mm, y_mm, w_mm, h_mm),
        )
    return layout


def solve_minimal(
    spec: RuleEngineOutput,
    room_ids: list[str],
    canvas_w_mm: int,
    canvas_h_mm: int,
    grid_resolution_mm: int = DEFAULT_GRID_RESOLUTION_MM,
    time_limit_s: float = 60.0,
) -> tuple[Layout, SolveReport]:
    """C0 최소 진입점.

    Args:
        spec: enrich 된 RuleEngineOutput.
        room_ids: 풀 대상 방 id 목록 (subset). 누락 id 는 silent skip.
        canvas_w_mm, canvas_h_mm: 캔버스 dim (D-010 resolve_building_dims 가 결정).
        grid_resolution_mm: 격자 1 셀의 mm.
        time_limit_s: CP-SAT 풀이 시간 한계.

    Returns:
        (Layout, SolveReport). INFEASIBLE 이면 Layout 은 비어있고
        호출자가 fallback (strip-band layout_solver.solve()) 을 결정.
    """
    t_total_0 = time.perf_counter()
    compiled = compile_minimal(
        spec, room_ids,
        canvas_w_mm=canvas_w_mm,
        canvas_h_mm=canvas_h_mm,
        grid_resolution_mm=grid_resolution_mm,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 1  # 결정론 — 단일 워커 (D-013 결정론 원칙)
    solver.parameters.random_seed = 0          # 결정론 — search 시드 고정

    t_solve_0 = time.perf_counter()
    status_code = solver.Solve(compiled.model)
    solve_ms = (time.perf_counter() - t_solve_0) * 1000.0

    layout = Layout(
        building_w_mm=float(compiled.canvas_w_mm),
        building_h_mm=float(compiled.canvas_h_mm),
    )
    obj: Optional[float] = None
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        layout = _placed_layout_from_solution(spec, compiled, solver)
        obj = float(solver.ObjectiveValue())
        # C0 (minimal) 는 OPTIMAL 도달이 빨라 결정론 이슈 없음 (방 3개).

    total_ms = (time.perf_counter() - t_total_0) * 1000.0

    report = SolveReport(
        status=CP_STATUS_NAMES.get(status_code, f"UNKNOWN({status_code})"),
        status_code=status_code,
        objective=obj,
        wall_time_ms=round(solve_ms, 3),
        total_wall_time_ms=round(total_ms, 3),
        grid_resolution_mm=grid_resolution_mm,
        canvas_dim_cells=(compiled.canvas_w_cells, compiled.canvas_h_cells),
        rooms_solved=list(layout.rooms.keys()),
    )
    return layout, report


# ══════════════════════════════════════════════════════════════════════
# C1a — 전체 방 hard 제약 (D-016)
# ══════════════════════════════════════════════════════════════════════
def _placed_layout_from_c1a(
    compiled: CompiledModelC1a,
    solver: cp_model.CpSolver,
) -> Layout:
    layout = Layout(
        building_w_mm=float(compiled.canvas_w_mm),
        building_h_mm=float(compiled.canvas_h_mm),
    )
    g = compiled.grid_resolution_mm
    for rid, rv in compiled.room_vars.items():
        x_mm = solver.Value(rv.x_var) * g
        y_mm = solver.Value(rv.y_var) * g
        w_mm = solver.Value(rv.w_var) * g
        h_mm = solver.Value(rv.h_var) * g
        layout.rooms[rid] = PlacedRoom(
            room=rv.room,
            rect=Rect(x_mm, y_mm, w_mm, h_mm),
        )
    return layout


def solve_c1a(
    spec: RuleEngineOutput,
    canvas_w_mm: int,
    canvas_h_mm: int,
    grid_resolution_mm: int = DEFAULT_GRID_RESOLUTION_MM,
    time_limit_s: float = 60.0,
    enforce_zones: bool = True,
    enforce_adjacency: bool = True,
    adj_max_mm: int = ADJ_MAX_DEFAULT_MM,
) -> tuple[Layout, SolveReport]:
    """C1a 진입점 — 전체 spec.rooms hard 제약.

    완화 옵션 (`enforce_zones`, `enforce_adjacency`, `adj_max_mm`) — INFEASIBLE
    또는 timeout 시 호출자가 끄거나 풀어줄 수 있음. 본 함수는 status 그대로
    리턴하고 fallback 결정은 호출자가.
    """
    t_total_0 = time.perf_counter()
    compiled = compile_c1a(
        spec,
        canvas_w_mm=canvas_w_mm,
        canvas_h_mm=canvas_h_mm,
        grid_resolution_mm=grid_resolution_mm,
        enforce_zones=enforce_zones,
        enforce_adjacency=enforce_adjacency,
        adj_max_mm=adj_max_mm,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    # [D-016] 결정론 강화 — deterministic_time 은 wall-clock 무관 search 단위 한계.
    # 머신 부하에 무관하게 같은 좌표 도달. wall-clock 은 safety upper bound.
    solver.parameters.max_deterministic_time = time_limit_s * 4.0
    solver.parameters.num_search_workers = 1  # 결정론
    solver.parameters.random_seed = 0           # 결정론 — search 시드 고정

    t_solve_0 = time.perf_counter()
    status_code = solver.Solve(compiled.model)
    solve_ms = (time.perf_counter() - t_solve_0) * 1000.0

    layout = Layout(
        building_w_mm=float(compiled.canvas_w_mm),
        building_h_mm=float(compiled.canvas_h_mm),
    )
    obj: Optional[float] = None
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        layout = _placed_layout_from_c1a(compiled, solver)
        obj = float(solver.ObjectiveValue())

    total_ms = (time.perf_counter() - t_total_0) * 1000.0
    report = SolveReport(
        status=CP_STATUS_NAMES.get(status_code, f"UNKNOWN({status_code})"),
        status_code=status_code,
        objective=obj,
        wall_time_ms=round(solve_ms, 3),
        total_wall_time_ms=round(total_ms, 3),
        grid_resolution_mm=grid_resolution_mm,
        canvas_dim_cells=(compiled.canvas_w_cells, compiled.canvas_h_cells),
        rooms_solved=list(layout.rooms.keys()),
    )
    # 진단 메타 (compiled 에서 끌어옴)
    report.enforce_zones = enforce_zones
    report.enforce_adjacency = enforce_adjacency
    report.n_adjacency_pairs = compiled.n_adjacency_pairs
    report.adj_max_mm = adj_max_mm
    return layout, report


# ══════════════════════════════════════════════════════════════════════
# C1b — P-series surrogate 목적함수 (D-017)
# ══════════════════════════════════════════════════════════════════════
def solve_c1b(
    spec: RuleEngineOutput,
    canvas_w_mm: int,
    canvas_h_mm: int,
    grid_resolution_mm: int = DEFAULT_GRID_RESOLUTION_MM,
    time_limit_s: float = 5.0,
    enforce_zones: bool = True,
    enforce_adjacency: bool = True,
    adj_max_mm: int = ADJ_MAX_DEFAULT_MM,
    p1_weight: int = P1_WEIGHT_DEFAULT,
    p2_weight: int = P2_WEIGHT_DEFAULT,
    tiebreaker_weight: int = TIEBREAKER_WEIGHT_DEFAULT,
    aspect_min: Optional[float] = None,
    aspect_max: Optional[float] = None,
) -> tuple[Layout, SolveReport]:
    """C1b — hard 제약 + P-series surrogate (P1 단조 + P2 link 거리 + tie-breaker).

    [D-020] aspect_min/max 인자 추가 — 방 사이즈 변동 폭 제어. None 이면
    compile_c1b 의 모듈 default 사용 (D-016 ASPECT [0.7, 1.4]). C1+C3 통합 시
    [0.9, 1.1] 같이 좁혀서 C3 입력 rect 가 spec area 근처가 되도록.
    """
    from src.drawing_agent.constraint_compiler import ASPECT_MIN, ASPECT_MAX
    am = ASPECT_MIN if aspect_min is None else aspect_min
    aM = ASPECT_MAX if aspect_max is None else aspect_max
    t_total_0 = time.perf_counter()
    compiled = compile_c1b(
        spec,
        canvas_w_mm=canvas_w_mm,
        canvas_h_mm=canvas_h_mm,
        grid_resolution_mm=grid_resolution_mm,
        enforce_zones=enforce_zones,
        enforce_adjacency=enforce_adjacency,
        adj_max_mm=adj_max_mm,
        p1_weight=p1_weight,
        p2_weight=p2_weight,
        tiebreaker_weight=tiebreaker_weight,
        aspect_min=am,
        aspect_max=aM,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.max_deterministic_time = time_limit_s * 4.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0

    t_solve_0 = time.perf_counter()
    status_code = solver.Solve(compiled.model)
    solve_ms = (time.perf_counter() - t_solve_0) * 1000.0

    layout = Layout(
        building_w_mm=float(compiled.canvas_w_mm),
        building_h_mm=float(compiled.canvas_h_mm),
    )
    obj: Optional[float] = None
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        layout = _placed_layout_from_c1a(compiled, solver)
        obj = float(solver.ObjectiveValue())

    total_ms = (time.perf_counter() - t_total_0) * 1000.0
    report = SolveReport(
        status=CP_STATUS_NAMES.get(status_code, f"UNKNOWN({status_code})"),
        status_code=status_code,
        objective=obj,
        wall_time_ms=round(solve_ms, 3),
        total_wall_time_ms=round(total_ms, 3),
        grid_resolution_mm=grid_resolution_mm,
        canvas_dim_cells=(compiled.canvas_w_cells, compiled.canvas_h_cells),
        rooms_solved=list(layout.rooms.keys()),
    )
    report.enforce_zones = enforce_zones
    report.enforce_adjacency = enforce_adjacency
    report.n_adjacency_pairs = compiled.n_adjacency_pairs
    report.adj_max_mm = adj_max_mm
    return layout, report


# ══════════════════════════════════════════════════════════════════════
# C3a — 방 1개 안 장비 CP-SAT (D-018)
# ══════════════════════════════════════════════════════════════════════
def solve_room_c3a(
    room,
    room_rect_mm: tuple,
    grid_resolution_mm: int = DEFAULT_GRID_RESOLUTION_MM,
    time_limit_s: float = 5.0,
    wall_margin_mm: int = C3A_WALL_MARGIN_MM_DEFAULT,
    eq_gap_mm: int = C3A_EQ_GAP_MM_DEFAULT,
    add_p1_surrogate: bool = True,
    add_p7_surrogate: bool = True,
    p1_weight: int = C3A_P1_WEIGHT_DEFAULT,
    p7_weight: int = C3A_P7_WEIGHT_DEFAULT,
) -> tuple[list, SolveReport]:
    """C3a — 방 1개 안 장비 CP-SAT 배치. 장비 *실제* W_mm/D_mm 사용 (B-001 분리).

    Returns:
        (list[PlacedEquipment], SolveReport). INFEASIBLE 이면 빈 list.
    """
    from src.drawing_agent.layout_solver import PlacedEquipment as _PE

    t0 = time.perf_counter()
    compiled = compile_room_c3a(
        room=room,
        room_rect_mm=room_rect_mm,
        grid_resolution_mm=grid_resolution_mm,
        wall_margin_mm=wall_margin_mm,
        eq_gap_mm=eq_gap_mm,
        add_p1_surrogate=add_p1_surrogate,
        add_p7_surrogate=add_p7_surrogate,
        p1_weight=p1_weight,
        p7_weight=p7_weight,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.max_deterministic_time = time_limit_s * 4.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0

    t_solve_0 = time.perf_counter()
    code = solver.Solve(compiled.model)
    solve_ms = (time.perf_counter() - t_solve_0) * 1000.0

    placed: list = []
    obj: Optional[float] = None
    if code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        g = compiled.grid_resolution_mm
        for ev in compiled.eq_vars:
            x_mm = solver.Value(ev.x_var) * g
            y_mm = solver.Value(ev.y_var) * g
            w_mm = ev.w_cells * g
            h_mm = ev.h_cells * g
            placed.append(_PE(equipment=ev.eq, rect=Rect(x_mm, y_mm, w_mm, h_mm)))
        obj = float(solver.ObjectiveValue())

    total_ms = (time.perf_counter() - t0) * 1000.0
    report = SolveReport(
        status=CP_STATUS_NAMES.get(code, f"UNKNOWN({code})"),
        status_code=code,
        objective=obj,
        wall_time_ms=round(solve_ms, 3),
        total_wall_time_ms=round(total_ms, 3),
        grid_resolution_mm=grid_resolution_mm,
        canvas_dim_cells=(compiled.inner_w_cells, compiled.inner_h_cells),
        rooms_solved=[room.id] if placed else [],
    )
    return placed, report
