"""룰 9 — 도어 위치 (size + swing direction).

한 줄 요약:
    각 adjacency edge의 door_size_mm와 door_swing_target을 채운다.

왜 필요한가:
    Excel "Layout 설계 원리 §9". 도어는 차압이 흐르는 방향으로 열리도록 설치한다.
    크기: 일반 1000mm, MAL 통과 엣지는 1500mm (큰 물품 통과).

룰:
    door_size_mm:
        엣지 한쪽이 MAL → 1500
        그 외 → 1000
    door_swing_target:
        from_room.DP > to_room.DP → "low_pressure_side" (낮은 쪽으로 열림)
        반대 → "high_pressure_side"
        같음 → None
"""
from __future__ import annotations

import dataclasses

from ..models import AdjacencyEdge, AirLock, DoorSwingTarget, Rationale, Room


_DEFAULT_DOOR_SIZE_MM = 1000
_MAL_DOOR_SIZE_MM = 1500


def _pressure_by_id(rooms: list[Room], airlocks: list[AirLock]) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in rooms:
        if r.differential_pressure_Pa is not None:
            out[r.room_id] = r.differential_pressure_Pa
    for a in airlocks:
        if a.differential_pressure_Pa is not None:
            out[a.al_id] = a.differential_pressure_Pa
    return out


def _is_mal_id(node_id: str, airlocks: list[AirLock]) -> bool:
    for a in airlocks:
        if a.al_id == node_id and "MAL" in a.kind:
            return True
    return False


def apply(
    adjacency: list[AdjacencyEdge],
    rooms: list[Room],
    airlocks: list[AirLock],
    rationale: list[Rationale],
) -> list[AdjacencyEdge]:
    """door_size_mm / door_swing_target 채우기."""
    dp = _pressure_by_id(rooms, airlocks)
    updated: list[AdjacencyEdge] = []

    for edge in adjacency:
        # door가 아닌 엣지(passthrough 등)는 그대로.
        if edge.relationship != "door":
            updated.append(edge)
            continue

        size = (
            _MAL_DOOR_SIZE_MM
            if _is_mal_id(edge.from_id, airlocks) or _is_mal_id(edge.to_id, airlocks)
            else _DEFAULT_DOOR_SIZE_MM
        )
        dp_from = dp.get(edge.from_id)
        dp_to = dp.get(edge.to_id)
        swing: DoorSwingTarget | None
        if dp_from is None or dp_to is None or dp_from == dp_to:
            swing = None
        elif dp_from > dp_to:
            swing = "low_pressure_side"
        else:
            swing = "high_pressure_side"

        updated.append(dataclasses.replace(
            edge, door_size_mm=size, door_swing_target=swing,
        ))

    rationale.append(Rationale(
        rule_id="rule_09_doors",
        target_id="LAYOUT",
        decision=f"door props filled for {len(updated)} edges",
        input_facts={
            "edge_count": len(adjacency),
            "default_size_mm": _DEFAULT_DOOR_SIZE_MM,
            "mal_size_mm": _MAL_DOOR_SIZE_MM,
        },
        applied_logic=(
            "MAL 끼면 1500mm, 그 외 1000mm. swing은 더 낮은 차압 쪽으로."
        ),
        source_reference="Excel: Layout 설계 원리 §9 (도어 위치)",
        flags=[],
    ))
    return updated
