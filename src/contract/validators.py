"""Hard constraint validators (C1 ~ C10).

근거: GMP_Layout_Decision_Tree.md 부록 C + DESIGN.md / Layout Logic 룰.

각 validator는 위반 사항 리스트를 반환. 빈 리스트면 통과.
"""
from __future__ import annotations

from .working_state import WorkingState

Violation = dict  # {"id": "C3", "message": "..."}


def validate_hard_constraints(state: WorkingState) -> list[Violation]:
    """안전·규제 직결 룰만 hard.
    C9(주공정 비율)는 효율 권장사항이라 soft로 분류(rule_03_size가 rationale에 WARNING 로깅).
    """
    out: list[Violation] = []
    out.extend(c1_supply_return_no_direct(state))
    out.extend(c2_wash_prep_no_personnel(state))
    out.extend(c3_oneway_in_out_separate(state))
    out.extend(c4_grade_b_oneway_4_airlocks(state))
    out.extend(c5_pressure_diff_min(state))
    out.extend(c6_grade_pressure_order(state))
    out.extend(c7_corridor_width_min(state))
    out.extend(c8_equipment_clearance(state))
    out.extend(c10_door_swing(state))
    return out


def validate_soft_constraints(state: WorkingState) -> list[Violation]:
    """효율/품질 권장. Reward function이 사용."""
    return c9_process_area_ratio(state)


# C1: Supply ↔ Return 직접 연결 금지
def c1_supply_return_no_direct(state: WorkingState) -> list[Violation]:
    sup, ret = "R_SUPPLY_CORRIDOR", "R_RETURN_CORRIDOR"
    for adj in state.adjacency:
        if adj.relationship == "door" and {adj.from_id, adj.to_id} == {sup, ret}:
            return [{"id": "C1", "message": f"Supply↔Return 직접 도어 연결 ({adj.from_id}→{adj.to_id})"}]
    return []


# C2: 세척실 ↔ 준비실 사람 왕래 차단 (passthrough만)
def c2_wash_prep_no_personnel(state: WorkingState) -> list[Violation]:
    for adj in state.adjacency:
        if {adj.from_id, adj.to_id} == {"R_WASHING", "R_PREPARATION"}:
            if adj.relationship == "door":
                return [{"id": "C2", "message": "세척실↔준비실은 passthrough_only 여야 함 (사람 차단)"}]
    return []


# C3: One-way Room 의 입구 AL ≠ 출구 AL
def c3_oneway_in_out_separate(state: WorkingState) -> list[Violation]:
    violations = []
    for rid, room in state.rooms.items():
        if not room.one_way_flow:
            continue
        ins = [al for al in state.airlocks.values() if al.connects_higher == rid and al.type.endswith("_in")]
        outs = [al for al in state.airlocks.values() if al.connects_higher == rid and al.type.endswith("_out")]
        if not ins or not outs:
            violations.append({"id": "C3", "message": f"{rid} one-way인데 입구 AL({len(ins)})/출구 AL({len(outs)}) 누락"})
        # 입구와 출구가 동일 AL 객체이면 안됨
        if any(i.id == o.id for i in ins for o in outs):
            violations.append({"id": "C3", "message": f"{rid} 입구/출구 AL이 동일"})
    return violations


# C4: Grade B + one-way → 4 AL 필수 (PAL_in, MAL_in, PAL_out, MAL_out)
def c4_grade_b_oneway_4_airlocks(state: WorkingState) -> list[Violation]:
    violations = []
    for rid, room in state.rooms.items():
        if room.clean_grade != "B" or not room.one_way_flow:
            continue
        types = {al.type for al in state.airlocks.values() if al.connects_higher == rid}
        required = {"PAL_in", "MAL_in", "PAL_out", "MAL_out"}
        missing = required - types
        if missing:
            violations.append({"id": "C4", "message": f"{rid}(Grade B one-way) AL 누락: {sorted(missing)}"})
    return violations


# C5: 인접 등급 간 ≥ 10 Pa (Room ↔ Room 만. AL은 cascade 중간단계라 제외)
def c5_pressure_diff_min(state: WorkingState) -> list[Violation]:
    violations = []
    min_dp = state.constraints.pressure_differential_min_pa
    for adj in state.adjacency:
        if adj.relationship != "door":
            continue
        # AL이 끼어있는 인접은 skip (Room↔AL은 cascade 자연 흐름, 등급차 룰의 대상이 아님)
        if adj.from_id in state.airlocks or adj.to_id in state.airlocks:
            continue
        ra, rb = _node(state, adj.from_id), _node(state, adj.to_id)
        if ra is None or rb is None:
            continue
        ga, gb = ra["grade"], rb["grade"]
        if ga == gb:
            continue
        diff = abs(ra["dp"] - rb["dp"])
        if diff + 1e-6 < min_dp:
            violations.append({
                "id": "C5",
                "message": f"{adj.from_id}({ra['dp']}Pa,G{ga}) ↔ {adj.to_id}({rb['dp']}Pa,G{gb}) 차이 {diff}Pa < {min_dp}Pa",
            })
    return violations


# C6: 등급 순서 A > B > C > D > CNC > NC (Room↔Room 만)
def c6_grade_pressure_order(state: WorkingState) -> list[Violation]:
    violations = []
    order = {g: i for i, g in enumerate(state.constraints.pressure_grade_order)}
    for adj in state.adjacency:
        if adj.relationship != "door":
            continue
        if adj.from_id in state.airlocks or adj.to_id in state.airlocks:
            continue
        ra, rb = _node(state, adj.from_id), _node(state, adj.to_id)
        if ra is None or rb is None:
            continue
        if ra["grade"] == rb["grade"]:
            continue
        rank_a, rank_b = order.get(ra["grade"], 99), order.get(rb["grade"], 99)
        # 더 깨끗한 등급(rank 작음)이 더 높은 DP를 가져야 함
        if rank_a < rank_b and ra["dp"] <= rb["dp"]:
            violations.append({
                "id": "C6",
                "message": f"{adj.from_id}(G{ra['grade']},{ra['dp']}Pa) > {adj.to_id}(G{rb['grade']},{rb['dp']}Pa) 위반",
            })
        if rank_b < rank_a and rb["dp"] <= ra["dp"]:
            violations.append({
                "id": "C6",
                "message": f"{adj.to_id}(G{rb['grade']},{rb['dp']}Pa) > {adj.from_id}(G{ra['grade']},{ra['dp']}Pa) 위반",
            })
    return violations


# C7: 복도 폭 ≥ 1500mm
def c7_corridor_width_min(state: WorkingState) -> list[Violation]:
    cw = state.constraints.corridor_width_mm
    if cw.min is None or cw.min < 1500:
        return [{"id": "C7", "message": f"corridor_width_mm.min={cw.min} < 1500"}]
    return []


# C8: 장비 간격 룰 (constraints 값 자체 검증)
def c8_equipment_clearance(state: WorkingState) -> list[Violation]:
    ec = state.constraints.equipment_clearance_mm
    violations = []
    if ec.get("between_equipment", 0) < 1000:
        violations.append({"id": "C8", "message": f"between_equipment={ec.get('between_equipment')} < 1000"})
    if ec.get("equipment_to_wall_min", 0) < 600:
        violations.append({"id": "C8", "message": f"equipment_to_wall_min={ec.get('equipment_to_wall_min')} < 600"})
    return violations


# C9: 주공정 Room 합 ∈ [40%, 70%]
def c9_process_area_ratio(state: WorkingState) -> list[Violation]:
    r = state.constraints.process_zone_area_ratio
    cur = r.get("current", 0.0)
    lo, hi = r.get("min", 0.40), r.get("max", 0.70)
    if not (lo <= cur <= hi):
        return [{"id": "C9", "message": f"process zone ratio {cur:.1%} ∉ [{lo:.0%}, {hi:.0%}]"}]
    return []


# C10: 도어 swing = 차압 흐름 방향 (낮은 압력 쪽으로)
def c10_door_swing(state: WorkingState) -> list[Violation]:
    violations = []
    for adj in state.adjacency:
        if adj.relationship != "door":
            continue
        ra, rb = _node(state, adj.from_id), _node(state, adj.to_id)
        if ra is None or rb is None or ra["dp"] == rb["dp"]:
            continue
        low_id = adj.from_id if ra["dp"] < rb["dp"] else adj.to_id
        if adj.door_swing_to is None:
            violations.append({"id": "C10", "message": f"{adj.from_id}↔{adj.to_id} swing 미설정"})
        elif adj.door_swing_to != low_id:
            violations.append({
                "id": "C10",
                "message": f"{adj.from_id}↔{adj.to_id} swing={adj.door_swing_to} (expected={low_id}, 낮은 압력 쪽)",
            })
    return violations


# ---- helpers ----
def _node(state: WorkingState, nid: str) -> dict | None:
    if nid in state.rooms:
        r = state.rooms[nid]
        return {"grade": r.clean_grade, "dp": r.differential_pressure_Pa}
    if nid in state.airlocks:
        a = state.airlocks[nid]
        return {"grade": a.clean_grade, "dp": a.differential_pressure_Pa}
    return None
