"""룰 7 — 전실 흐름 타입 (cascade / sink / bubble).

한 줄 요약:
    각 AirLock의 공기 흐름 타입을 flow_policy 기본값과 격리 필요성 기준으로
    결정한다.

왜 필요한가:
    Excel "Layout 설계 원리 §7" 하단부. (1) cascade — 차압 흐름 방향이 한쪽,
    (2) sink — 양쪽에서 전실로 흡입, (3) bubble — 전실에서 양쪽으로 토출.
    flow_policy.biological_safety_isolation=True 면 양방향 공기 차단이 필요해
    sink 또는 bubble을 강제한다.

룰:
    bio_safety_isolation=False → flow_policy.airlock_default_type 사용
    bio_safety_isolation=True  → 무균 영역(B 등급 AL)은 bubble, 그 외는 sink

무엇을 안 하는가:
    차압 수치는 룰 13에서. 여기서는 타입(방향)만 결정.
"""
from __future__ import annotations

import dataclasses

from ..models import AirLock, ALFlowType, Rationale, Room, RuleEngineInput


def apply(
    airlocks: list[AirLock],
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[AirLock]:
    """각 AL에 flow_type 부여."""
    isolation = input_spec.flow_policy.biological_safety_isolation
    default = input_spec.flow_policy.airlock_default_type
    updated: list[AirLock] = []

    for al in airlocks:
        if isolation:
            # 무균(Grade B) 영역 보호 → bubble, 그 외 → sink.
            flow: ALFlowType = "bubble" if al.clean_grade == "B" else "sink"
            logic = (
                f"biological_safety_isolation=True → Grade {al.clean_grade}: "
                f"{flow}"
            )
        else:
            flow = default
            logic = f"flow_policy.airlock_default_type 기본값 사용: {default}"

        new_al = dataclasses.replace(al, flow_type=flow)
        updated.append(new_al)

        rationale.append(Rationale(
            rule_id="rule_07_al_flow_type",
            target_id=al.al_id,
            decision=f"flow_type={flow}",
            input_facts={
                "biological_safety_isolation": isolation,
                "default_type": default,
                "al_grade": al.clean_grade,
            },
            applied_logic=logic,
            source_reference="Excel: Layout 설계 원리 §7 (전실 흐름 타입)",
            flags=[],
        ))
    return updated
