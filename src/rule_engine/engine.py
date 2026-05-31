"""Orchestrator — Rule Engine 본체 호출 순서.

이 파일은 입력(RuleEngineInput)을 받아 14개 룰 함수와 3개 derive 함수를
정해진 순서로 호출하고, 결과 7 블록(RuleEngineOutput)을 조립한다.
**룰 평가 자체는 두지 않는다** — 각 룰의 본문은 rules/*.py 에 있다.

설계 원칙 (보고서 v0.2 §4):
    - URS 우선: assign_clean_grade / compute_acph / assign_gowning은
      passthrough + flag checker로만 동작한다.
    - Rule Engine 핵심 산출: adjacency 그래프 + flow paths + 면적·DP·AL타입.
    - 자동 수정 안 함. 룰 위반 의심은 Rationale.flags에 마킹만.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .models import (
    AirLock,
    AdjacencyEdge,
    Constraints,
    FlowPaths,
    Rationale,
    Room,
    RuleEngineInput,
    RuleEngineOutput,
    Zones,
)


_ENGINE_VERSION = "0.1.0"
_KB_VERSION = "GMP_Layout_Logic_0510.xlsx"


def run_rule_engine(input_spec: RuleEngineInput) -> RuleEngineOutput:
    """입력 1개 → 7 블록 출력. v1 prototype.

    호출 순서는 룰 간 데이터 의존성을 따른다:
        1) Room 리스트 확보 (URS 통과)
        2) Room별 derive (면적/천정고/체적/색상)
        3) AL 객체 생성 + 흐름 타입 결정
        4) 차압 cascade 계산
        5) Adjacency 그래프 빌드 (엘리베이터 인접 제약 포함)
        6) Flow paths 산출
        7) Zone 그룹핑
        8) Constraints 번들
        9) Rationale 수집

    Args:
        input_spec: RuleEngineInput. URS Parser가 채워서 넘긴 컨테이너.

    Returns:
        RuleEngineOutput. 7 블록 + 메타데이터.
    """
    from .derive import (
        backfill_airlock_connections,
        build_adjacency,
        derive_flow_paths,
        select_required_rooms,
    )
    from .rules import (
        rule_01_layout_axis,
        rule_02_room_shape,
        rule_03_room_size,
        rule_04_clean_grade,
        rule_05_zones,
        rule_06_airlocks,
        rule_07_al_flow_type,
        rule_08_corridors,
        rule_09_doors,
        rule_10_equipment,
        rule_11_wash_prep,
        rule_12_nc_rooms,
        rule_13_pressure,
        rule_14_acph,
        rule_15_gowning,
    )

    rationale: list[Rationale] = []

    # 1) Room 리스트 확보.
    rooms: list[Room] = select_required_rooms(input_spec, rationale)

    # 2) Room별 derive.
    rooms = rule_10_equipment.apply(rooms, input_spec, rationale)
    rooms = rule_03_room_size.apply(rooms, input_spec, rationale)
    rooms = rule_02_room_shape.apply(rooms, input_spec, rationale)
    rooms = rule_04_clean_grade.apply(rooms, input_spec, rationale)
    rooms = rule_14_acph.apply(rooms, input_spec, rationale)
    rooms = rule_15_gowning.apply(rooms, input_spec, rationale)

    # 3) AL 객체 + 흐름 타입.
    airlocks: list[AirLock] = rule_06_airlocks.apply(rooms, input_spec, rationale)
    airlocks = rule_07_al_flow_type.apply(airlocks, rooms, input_spec, rationale)

    # 4) 차압 cascade.
    rooms, airlocks = rule_13_pressure.apply(rooms, airlocks, input_spec, rationale)

    # 5) Adjacency.
    rule_01_layout_axis.apply(input_spec, rationale)
    adjacency: list[AdjacencyEdge] = build_adjacency(
        rooms, airlocks, input_spec, rationale
    )
    adjacency = rule_08_corridors.apply(adjacency, rooms, input_spec, rationale)
    adjacency = rule_09_doors.apply(adjacency, rooms, airlocks, rationale)
    adjacency = rule_11_wash_prep.apply(adjacency, rooms, rationale)

    # 5b) AL connects 역채움 — adjacency 완성 후 airlock 필드 채움 (Doc Agent #1).
    airlocks = backfill_airlock_connections(
        airlocks, adjacency, rooms, rationale
    )

    # 6) Flow paths.
    flow_paths: FlowPaths = derive_flow_paths(
        rooms, adjacency, input_spec, rationale
    )

    # 7) Zones.
    zones: Zones = rule_05_zones.apply(rooms, rationale)
    zones = rule_12_nc_rooms.apply(zones, rooms, input_spec, rationale)

    # 8) Constraints.
    constraints: Constraints = _bundle_constraints()

    # 9) Meta.
    meta = _build_meta(input_spec, rooms, airlocks, adjacency, rationale)

    return RuleEngineOutput(
        rooms=rooms,
        airlocks=airlocks,
        adjacency=adjacency,
        flow_paths=flow_paths,
        zones=zones,
        constraints=constraints,
        rationale=rationale,
        meta=meta,
    )


def _bundle_constraints() -> Constraints:
    """GMP Layout Logic의 정량값을 Constraints 객체로 번들.

    v1은 룰 본문에서 추출한 기본값을 하드코딩. v2부터는 GMP_Layout_Logic.xlsx
    파서로 동적 로드.
    """
    return Constraints(
        corridor_width_mm={"min": 1500, "preferred_min": 2000, "max": 3000},
        airlock_size_mm={
            "preferred": [3000, 3000],
            "min": [1500, 1500],
        },
        ceiling_height_mm={"default_min": 2700, "default_max": 3000},
        equipment_clearance_mm={
            "between_equipment": 1000,
            "to_wall_min": 600,
            "to_wall_max": 1200,
        },
        process_zone_area_ratio={"min": 0.40, "max": 0.70},
        supply_return_no_direct_connection=True,
        color_legend={
            "A": "Green-diagonal-black",
            "B": "Green",
            "C": "yellow",
            "D": "Blue",
            "CNC": "Gray-dotted-black",
            "NC": "Gray",
        },
    )


def _build_meta(
    input_spec: RuleEngineInput,
    rooms: list[Room],
    airlocks: list[AirLock],
    adjacency: list[AdjacencyEdge],
    rationale: list[Rationale],
) -> dict[str, Any]:
    """엔진 버전·KB 버전·입력 해시·실행 통계를 묶는다.

    Validation Agent가 어떤 KB·엔진 버전으로 만들어진 결과인지 확인하기 위한
    추적 메타데이터. 실행 통계는 가시화·로깅에도 활용된다.
    """
    # 입력 fingerprint — 같은 URS로 두 번 실행 시 같은 해시가 나옴 (결정론적 재현성 확인).
    serializable = {
        "modality": input_spec.product.modality,
        "culture_scale_L": input_spec.product.culture_scale_L,
        "urs_room_count": len(input_spec.urs_rooms),
        "urs_equipment_count": len(input_spec.urs_equipment),
    }
    input_hash = hashlib.sha256(
        json.dumps(serializable, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]

    # 실행 통계.
    flag_counts: dict[str, int] = {}
    for r in rationale:
        for f in r.flags:
            flag_counts[f.severity] = flag_counts.get(f.severity, 0) + 1

    return {
        "engine_version": _ENGINE_VERSION,
        "knowledge_base_version": _KB_VERSION,
        "input_hash": input_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "rooms": len(rooms),
            "airlocks": len(airlocks),
            "adjacency_edges": len(adjacency),
            "rationale_entries": len(rationale),
            "flag_counts": flag_counts,
        },
    }
