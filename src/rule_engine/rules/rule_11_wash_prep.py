"""Rule 11 — 세척실 / 준비실 (Wash & Preparation).

근거: GMP Layout Logic_0510 §11
- 세척실 → Return corridor 연결
- 준비실 → Supply corridor 연결
- 세척실 ↔ 준비실: Pass-through COP 공유 (인접 배치)
- 세척실 ↔ 준비실: 사람 직접 왕래 물리적 차단 (HARD constraint C2)
"""
from __future__ import annotations

from ..schemas import Adjacency
from ..working_state import WorkingState


def apply(state: WorkingState) -> None:
    has_wash = state.has_room("R_WASHING")
    has_prep = state.has_room("R_PREPARATION")
    has_supply = state.has_room("R_SUPPLY_CORRIDOR")
    has_return = state.has_room("R_RETURN_CORRIDOR")

    if not (has_wash and has_prep):
        state.log(
            rule_id="rule_11_wash_prep",
            target="wash_prep",
            decision="SKIP: 세척실 또는 준비실 미존재",
            reason=f"R_WASHING={has_wash}, R_PREPARATION={has_prep}",
        )
        return

    # 1. 세척실 ↔ 리턴복도
    if has_return:
        _ensure_door(state, "R_RETURN_CORRIDOR", "R_WASHING")
    # 2. 준비실 ↔ 공급복도
    if has_supply:
        _ensure_door(state, "R_SUPPLY_CORRIDOR", "R_PREPARATION")

    # 3. 세척실 ↔ 준비실: passthrough_only (사람 왕래 금지, 장비만 통과)
    state.adjacency.append(
        Adjacency(
            from_id="R_WASHING",
            to_id="R_PREPARATION",
            relationship="passthrough_only",
            door_count=1,
            door_size_mm=1200,
            flow_direction="bidirectional",
            notes="Pass-through COP: 장비 통과만, 사람 왕래 물리 차단 (HARD C2)",
        )
    )

    state.constraints.wash_prep_no_personnel_crossing = True

    state.log(
        rule_id="rule_11_wash_prep",
        target="wash_prep",
        decision="세척실↔리턴, 준비실↔공급, 세척실⇌준비실=passthrough(장비만)",
        reason="Pass-through COP 공유, 사람 직접 왕래 물리 차단 (HARD constraint C2).",
        source="GMP Layout Logic_0510 §11 세척실과 준비실",
    )


def _ensure_door(state: WorkingState, a: str, b: str) -> None:
    """이미 존재하면 skip, 아니면 양방향 door 추가."""
    for adj in state.adjacency:
        if adj.relationship == "door" and {adj.from_id, adj.to_id} == {a, b}:
            return
    state.adjacency.append(
        Adjacency(
            from_id=a, to_id=b,
            relationship="door",
            door_count=1, door_size_mm=1000,
            flow_direction="bidirectional",
        )
    )
