"""Adjacency graph construction.

룰 5/6/8 이후, airlocks를 통해 Room↔Room 연결 그래프를 생성한다.
산출은 룰 9 (door 위치/크기/swing)와 룰 13 (DP 검증)에서 소비된다.

원칙:
- 모든 AL은 connects_higher(공정 Room) <-> 복도 사이에 door 2개를 만든다
  · AL ↔ 공정 Room
  · AL ↔ 공급/리턴 복도
- 같은 등급 Room끼리는 직접 door (AL 없이) — 룰 6에서 needs_airlock=False면 인접 허용
- Supply ↔ Return은 직접 연결 금지 (룰 8 C1)
"""
from __future__ import annotations

from .schemas import Adjacency
from .working_state import WorkingState

# AL type → (공정쪽 연결 flow_direction, 복도쪽 flow_direction)
_FLOW_TABLE = {
    "PAL_in":  ("one_way_in",  "one_way_in"),
    "MAL_in":  ("one_way_in",  "one_way_in"),
    "CAL_in":  ("one_way_in",  "one_way_in"),
    "PAL_out": ("one_way_out", "one_way_out"),
    "MAL_out": ("one_way_out", "one_way_out"),
    "CAL_out": ("one_way_out", "one_way_out"),
    "CAL":     ("bidirectional", "bidirectional"),
    "PAL":     ("bidirectional", "bidirectional"),
    "MAL":     ("bidirectional", "bidirectional"),
}


def build(state: WorkingState) -> None:
    supply = "R_SUPPLY_CORRIDOR"
    ret = "R_RETURN_CORRIDOR"

    for al in state.airlocks.values():
        process_room_id = al.connects_higher
        is_out = al.type.endswith("_out")
        corridor_id = ret if is_out else supply

        flow_proc, flow_corr = _FLOW_TABLE.get(al.type, ("bidirectional", "bidirectional"))
        # MAL은 큰 도어 (자재 반입)
        door_size = 1800 if "MAL" in al.type else 1000

        # AL ↔ Process Room
        state.adjacency.append(
            Adjacency(
                from_id=al.id,
                to_id=process_room_id,
                relationship="door",
                door_count=1,
                door_size_mm=door_size,
                flow_direction=flow_proc,
            )
        )
        # AL ↔ Corridor
        if state.has_room(corridor_id):
            state.adjacency.append(
                Adjacency(
                    from_id=corridor_id,
                    to_id=al.id,
                    relationship="door",
                    door_count=1,
                    door_size_mm=door_size,
                    flow_direction=flow_corr,
                )
            )
            # AL의 connects_lower를 corridor로 갱신
            al.connects_lower = corridor_id

    # Both-way Room: AL 없이 supply corridor와 직접 인접 (양방향)
    for rid, room in state.rooms.items():
        if room.is_corridor or room.category != "process":
            continue
        if room.one_way_flow:
            continue
        # 이미 AL로 연결돼 있으면 skip
        if any(adj.to_id == rid and adj.relationship == "door" for adj in state.adjacency):
            continue
        if state.has_room("R_SUPPLY_CORRIDOR"):
            state.adjacency.append(
                Adjacency(
                    from_id="R_SUPPLY_CORRIDOR",
                    to_id=rid,
                    relationship="door",
                    door_count=1,
                    door_size_mm=1000,
                    flow_direction="bidirectional",
                )
            )

    # Wash <-> Return corridor, Prep <-> Supply corridor (룰 11에서 강화)
    # NC 구역은 별도 영역 — 자체 복도/로비 통해 연결 (룰 12에서)

    state.log(
        rule_id="adjacency_build",
        target="adjacency",
        decision=f"{len(state.adjacency)}개 인접 관계 생성",
        reason="AL ↔ 공정 Room ↔ corridor 도어 페어 + both-way Room 직접 연결",
    )
