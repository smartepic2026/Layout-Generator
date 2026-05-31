"""룰 8 — 복도 배열 (공급 ↔ 리턴 직결 차단).

한 줄 요약:
    Supply corridor와 Return corridor가 직접 인접하면 suspected_violation flag를
    추가한다 (Rule 자체는 엣지를 제거하지 않고 의심만 표시).

왜 필요한가:
    Excel "Layout 설계 원리 §8". 청정등급이 낮은 리턴복도에서 공급복도로의
    교차오염을 원천 차단해야 한다. 두 복도는 직접 연결되지 않고 process Room을
    거쳐서 흐른다.

무엇을 안 하는가:
    엣지를 자동 삭제하지 않는다 — 사용자 URS가 명시한 인접일 수 있어 의심만 표시.
    실제 수정은 Validation Agent의 최종 판정 후.
"""
from __future__ import annotations

from ..models import AdjacencyEdge, Flag, Rationale, Room, RuleEngineInput


def apply(
    adjacency: list[AdjacencyEdge],
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[AdjacencyEdge]:
    """Supply ↔ Return 직결 검출 및 flag."""
    name_by_id = {r.room_id: r.name_en.lower() for r in rooms}
    flags: list[Flag] = []
    violations = 0

    if not input_spec.flow_policy.supply_return_corridor_separate:
        # 정책 자체가 분리 안 함이면 검사 skip.
        rationale.append(Rationale(
            rule_id="rule_08_corridors",
            target_id="LAYOUT",
            decision="skipped — supply/return 분리 정책 OFF",
            input_facts={
                "supply_return_corridor_separate": False,
                "edge_count": len(adjacency),
            },
            applied_logic="flow_policy.supply_return_corridor_separate=False.",
            source_reference="Excel: Layout 설계 원리 §8",
            flags=[],
        ))
        return adjacency

    for edge in adjacency:
        a = name_by_id.get(edge.from_id, "")
        b = name_by_id.get(edge.to_id, "")
        is_supply = "supply corridor" in a or "supply corridor" in b
        is_return = "return corridor" in a or "return corridor" in b
        if is_supply and is_return:
            violations += 1
            flags.append(Flag(
                rule_id="rule_08_corridors",
                severity="suspected_violation",
                note=(
                    f"공급↔리턴 직결 의심: {edge.from_id} ↔ {edge.to_id}"
                ),
            ))

    rationale.append(Rationale(
        rule_id="rule_08_corridors",
        target_id="LAYOUT",
        decision=f"checked {len(adjacency)} edges, {violations} violations",
        input_facts={
            "supply_return_corridor_separate": True,
            "edge_count": len(adjacency),
            "violations": violations,
        },
        applied_logic="Supply corridor와 Return corridor가 직접 연결되는 엣지 검출.",
        source_reference="Excel: Layout 설계 원리 §8 (복도 배열)",
        flags=flags,
    ))
    return adjacency
