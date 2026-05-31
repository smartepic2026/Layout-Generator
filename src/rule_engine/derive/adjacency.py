"""adjacency — Room ↔ Room 인접 그래프 빌드 (Rule Engine 핵심 가치).

한 줄 요약:
    process Room의 공정 순서, AL Room의 대상 매칭, 엘리베이터 가상 노드를
    종합해 AdjacencyEdge 리스트(그래프)를 만든다.

왜 필요한가:
    보고서 v0.2 §3.2에 따르면 URS는 인접 정보가 없고 Rule Engine만이 derive한다.
    이 그래프가 있어야 Documentation Agent가 좌표 배치를 시작할 수 있다. v1
    prototype은 다음 3종의 엣지를 만든다.

엣지 3종:
    1. process flow 인접 — process Room을 process_no 오름차순으로 정렬한 뒤,
       인접한 두 Room 사이에 door 엣지 (bidirectional). process_no가 비어 있는
       Room(예: Gowning)은 흐름에서 제외.
    2. AL 인접 — AL Room의 영문명에서 대상 Room 명을 추출해 그 Room과 door
       엣지로 연결.
    3. 엘리베이터 가상 노드 — building.elevator_for_material_in / waste_out이
       None이 아니면 가상 노드를 Material-in / Waste-out Room과 인접시킨다.

무엇을 안 하는가:
    좌표 배치 안 함. 도어 크기·swing은 룰 9에서. 공급/리턴 직결 검증은 룰 8.
"""
from __future__ import annotations

import re

from ..models import (
    AdjacencyEdge,
    AirLock,
    FlowDirection,
    Flag,
    Rationale,
    RelationshipType,
    Room,
    RuleEngineInput,
)


ELEVATOR_MATERIAL_NODE = "ELEVATOR_MATERIAL_IN"
ELEVATOR_WASTE_NODE = "ELEVATOR_WASTE_OUT"

_AL_PATTERN = re.compile(
    r"\b(PAL|MAL|CAL)\b[-_ ]?(in|out)?\b",
    re.IGNORECASE,
)


def _room_id_from_al_id(al_id: str) -> str:
    """AL ID에서 대응 Room ID를 prefix만 교체해 derive.

    str.replace는 substring을 모두 치환하므로 "AL_PAL_IN_CC" 안의 "AL_"가
    두 번 매치되어 잘못 변환된다. 여기서는 prefix만 절단.
    """
    if al_id.startswith("AL_"):
        return "R_" + al_id[len("AL_"):]
    return al_id


def _extract_target_room(al_name_en: str) -> str:
    """AL 영문명 → 대상 Room 영문명 추출."""
    cleaned = _AL_PATTERN.sub("", al_name_en)
    cleaned = re.sub(r"[\(\)]", " ", cleaned)
    return " ".join(cleaned.split())


def _is_al_room(name_en: str) -> bool:
    return _AL_PATTERN.search(name_en) is not None


def _process_no_key(process_no_list: list[str]) -> tuple[int, int]:
    """process_no 리스트의 최소값을 (major, minor)로 반환."""
    if not process_no_list:
        return (999, 999)
    keys: list[tuple[int, int]] = []
    for p in process_no_list:
        head = p.split(".")[0].strip()
        try:
            major = int(head[1])
            minor = int(head[3]) if len(head) > 3 else 0
            keys.append((major, minor))
        except (ValueError, IndexError):
            continue
    return min(keys) if keys else (999, 999)


def _make_edge(
    from_id: str,
    to_id: str,
    relationship: RelationshipType,
    flow_direction: FlowDirection,
    is_elevator: bool = False,
) -> AdjacencyEdge:
    return AdjacencyEdge(
        from_id=from_id,
        to_id=to_id,
        relationship=relationship,
        door_count=1 if relationship == "door" else 0,
        door_size_mm=None,
        door_swing_target=None,
        flow_direction=flow_direction,
        is_elevator_constraint=is_elevator,
    )


def build_adjacency(
    rooms: list[Room],
    airlocks: list[AirLock],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[AdjacencyEdge]:
    """Room·AL·엘리베이터를 종합한 그래프 빌드."""
    edges: list[AdjacencyEdge] = []
    flags: list[Flag] = []

    name_to_room = {r.name_en: r for r in rooms}

    # 1) process flow 인접 — process_no가 있는 process Room만 포함.
    process_rooms = [
        r for r in rooms
        if r.category == "process"
        and not _is_al_room(r.name_en)
        and r.process_no
    ]
    process_rooms_sorted = sorted(
        process_rooms, key=lambda r: _process_no_key(r.process_no)
    )
    for a, b in zip(process_rooms_sorted, process_rooms_sorted[1:]):
        edges.append(_make_edge(a.room_id, b.room_id, "door", "bidirectional"))

    # 2) AL 인접 — al_id에서 prefix만 절단해 대응 Room ID 매칭.
    al_id_by_room_id = {_room_id_from_al_id(al.al_id): al for al in airlocks}
    for r in rooms:
        if not _is_al_room(r.name_en):
            continue
        target_name = _extract_target_room(r.name_en)
        target_room = name_to_room.get(target_name)
        al = al_id_by_room_id.get(r.room_id)
        if target_room is None or al is None:
            flags.append(Flag(
                rule_id="adjacency",
                severity="warning",
                note=(
                    f"AL '{r.name_en}'의 대상 Room {target_name!r} 매칭 실패"
                ),
            ))
            continue
        if al.kind.endswith("_in"):
            flow: FlowDirection = "one_way_in"
            edges.append(_make_edge(al.al_id, target_room.room_id, "door", flow))
        elif al.kind.endswith("_out"):
            flow = "one_way_out"
            edges.append(_make_edge(target_room.room_id, al.al_id, "door", flow))
        else:
            flow = "bidirectional"
            edges.append(_make_edge(al.al_id, target_room.room_id, "door", flow))

    # 3) 엘리베이터 가상 노드.
    bld = input_spec.building
    if bld.elevator_for_material_in is not None:
        for r in rooms:
            n = r.name_en.lower()
            if (
                ("material" in n and "in" in n and "storage" not in n)
                or "mateial-in" in n
            ):
                edges.append(_make_edge(
                    ELEVATOR_MATERIAL_NODE, r.room_id, "door", "one_way_in",
                    is_elevator=True,
                ))
                break
    if bld.elevator_for_waste_out is not None:
        for r in rooms:
            n = r.name_en.lower()
            if "waste" in n and "out" in n:
                edges.append(_make_edge(
                    r.room_id, ELEVATOR_WASTE_NODE, "door", "one_way_out",
                    is_elevator=True,
                ))
                break

    rationale.append(Rationale(
        rule_id="adjacency",
        target_id="LAYOUT",
        decision=f"built {len(edges)} edges",
        input_facts={
            "room_count": len(rooms),
            "airlock_count": len(airlocks),
            "process_rooms": len(process_rooms),
            "elevator_material": bld.elevator_for_material_in,
            "elevator_waste": bld.elevator_for_waste_out,
        },
        applied_logic="process flow + AL 대상 매칭 + 엘리베이터 가상 노드.",
        source_reference="보고서 v0.2 §3.2 (adjacency 그래프) + §5.4 (엘리베이터)",
        flags=flags,
    ))
    return edges


# ---------------------------------------------------------------------------
# AirLock connects 역채움 (2026-05-29, Doc Agent #1 요청)
# ---------------------------------------------------------------------------

_GRADE_RANK = {"A": 6, "B": 5, "C": 4, "D": 3, "CNC": 2, "NC": 1}


def backfill_airlock_connections(
    airlocks: list[AirLock],
    adjacency: list[AdjacencyEdge],
    rooms: list[Room],
    rationale: list[Rationale],
) -> list[AirLock]:
    """adjacency 결과로 각 AirLock의 connects_higher/lower_room 을 채운다.

    배경:
        Doc Agent 팀 확인 결과 airlocks[]의 connects_higher_room /
        connects_lower_room 이 18개 전부 None 이었다. adjacency 그래프에는
        AL↔Room 엣지가 이미 있으므로, 그 정보를 AirLock 필드로 역채움해서
        양쪽 블록의 데이터를 일치시킨다. (Doc Agent 가 adjacency 에서 역산하던
        작업을 엔진이 대신 해 줌.)

    로직:
        - 각 AL 이 adjacency 에서 연결된 Room 들을 수집 (AL/elevator 노드 제외).
        - 2개 이상이면 clean_grade 등급 순위로 higher/lower 배정 (동률은 room_id
          정렬로 결정론적).
        - 1개면 그 Room 을 connects_higher_room (AL 이 서비스하는 cleanroom),
          connects_lower_room 은 corridor 측이라 Room 모델에 없으므로 None 유지.
        - area_m2 는 별도 산출 로직이 없어 건드리지 않음 (None 유지) — #1 답변
          참조: 면적은 adjacency 로도 안 나오므로 추후 별도 룰 필요.

    Returns:
        connects 필드가 채워진 새 AirLock 리스트 (frozen 이라 replace).
    """
    import dataclasses

    room_by_id = {r.room_id: r for r in rooms}
    updated: list[AirLock] = []
    for al in airlocks:
        connected_room_ids: list[str] = []
        for e in adjacency:
            other = None
            if e.from_id == al.al_id:
                other = e.to_id
            elif e.to_id == al.al_id:
                other = e.from_id
            if (
                other is not None
                and other in room_by_id
                and other not in connected_room_ids
            ):
                connected_room_ids.append(other)

        higher = al.connects_higher_room
        lower = al.connects_lower_room
        if len(connected_room_ids) >= 2:
            ranked = sorted(
                connected_room_ids,
                key=lambda rid: (
                    -_GRADE_RANK.get(room_by_id[rid].clean_grade, 0), rid
                ),
            )
            higher, lower = ranked[0], ranked[-1]
        elif len(connected_room_ids) == 1:
            higher = connected_room_ids[0]
            lower = None

        updated.append(dataclasses.replace(
            al, connects_higher_room=higher, connects_lower_room=lower,
        ))

    return updated
