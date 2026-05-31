"""룰 11 — 세척실·준비실 인접 (passthrough COP).

한 줄 요약:
    세척실(Washing)과 준비실(Preparation) 사이에 relationship="passthrough_only",
    door_count=0 엣지를 추가한다. 사람 직접 통행은 차단.

왜 필요한가:
    Excel "Layout 설계 원리 §11". 세척실은 리턴복도, 준비실은 공급복도와 연결되어
    있어 사람 동선이 직접 통하면 교차오염이 발생한다. 그러나 장비는 pass-through
    COP로 공유. 즉 "벽으로는 인접, 도어로는 차단".

무엇을 안 하는가:
    pass-through 자체의 mm 크기는 Documentation Agent에서. 룰 엔진은 그래프 엣지만.
"""
from __future__ import annotations

from ..models import AdjacencyEdge, Flag, Rationale, Room


def apply(
    adjacency: list[AdjacencyEdge],
    rooms: list[Room],
    rationale: list[Rationale],
) -> list[AdjacencyEdge]:
    """Washing ↔ Preparation passthrough_only 엣지 추가."""
    washing = next(
        (r for r in rooms if r.name_en.lower() == "washing"), None
    )
    preparation = next(
        (r for r in rooms if r.name_en.lower() == "preparation"), None
    )
    flags: list[Flag] = []
    new_edges = list(adjacency)

    if washing is None or preparation is None:
        # Room이 둘 다 있어야만 룰 적용.
        rationale.append(Rationale(
            rule_id="rule_11_wash_prep",
            target_id="LAYOUT",
            decision="skipped — Washing 또는 Preparation Room 미존재",
            input_facts={
                "has_washing": washing is not None,
                "has_preparation": preparation is not None,
            },
            applied_logic="Washing·Preparation Room 모두 있어야 passthrough 추가.",
            source_reference="Excel: Layout 설계 원리 §11",
            flags=[],
        ))
        return new_edges

    # 이미 추가됐는지 확인.
    pair = {washing.room_id, preparation.room_id}
    already = any(
        {e.from_id, e.to_id} == pair and e.relationship == "passthrough_only"
        for e in adjacency
    )
    if not already:
        new_edges.append(AdjacencyEdge(
            from_id=washing.room_id,
            to_id=preparation.room_id,
            relationship="passthrough_only",
            door_count=0,
            door_size_mm=None,
            door_swing_target=None,
            flow_direction="bidirectional",
            is_elevator_constraint=False,
        ))

    # 사람 직접 통행을 차단해야 함을 명시.
    flags.append(Flag(
        rule_id="rule_11_wash_prep",
        severity="info",
        note=(
            "Washing ↔ Preparation은 passthrough COP만 공유. "
            "사람 직접 통행을 차단해야 함 (Documentation Agent 처리)."
        ),
    ))

    rationale.append(Rationale(
        rule_id="rule_11_wash_prep",
        target_id="LAYOUT",
        decision=f"passthrough_only edge {'added' if not already else 'already exists'}",
        input_facts={
            "washing_id": washing.room_id,
            "preparation_id": preparation.room_id,
        },
        applied_logic="Washing-Preparation 간 passthrough_only 엣지 + 사람 차단 flag.",
        source_reference="Excel: Layout 설계 원리 §11 (세척·준비실)",
        flags=flags,
    ))
    return new_edges
