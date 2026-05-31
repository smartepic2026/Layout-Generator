"""flow_paths — 4종 동선 (personnel/material/waste/product).

한 줄 요약:
    Room·AL·adjacency 그래프를 종합해 사람·자재·폐기물·제품 4종 동선을 ID
    시퀀스로 산출한다.

왜 필요한가:
    URS는 동선의 일부 단서(One-way/Both-way, 세부 공정 No.)만 제공하고, 실제
    시퀀스는 룰 1·8을 종합해 derive해야 한다. 보고서 v0.2 §5.4에 따라
    material_entry는 엘리베이터(material)에서 시작, waste_exit는 엘리베이터
    (waste)에서 종료된다.

product flow 포함 기준:
    category=="process" + AL이 아님 + process_no 비어 있지 않음.
    (Gowning 같은 보조 process Room은 process flow에 포함되지 않음)

무엇을 안 하는가:
    mm 단위 거리·곡선은 Documentation Agent. 룰 엔진은 ID 시퀀스만.
"""
from __future__ import annotations

import re

from ..models import (
    AdjacencyEdge,
    FlowPaths,
    Rationale,
    Room,
    RuleEngineInput,
)
from .adjacency import ELEVATOR_MATERIAL_NODE, ELEVATOR_WASTE_NODE


_AL_PATTERN = re.compile(
    r"\b(PAL|MAL|CAL)\b[-_ ]?(in|out)?\b",
    re.IGNORECASE,
)


def _process_no_key(process_no_list: list[str]) -> tuple[int, int]:
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


def _find_first(rooms: list[Room], predicate) -> Room | None:
    for r in rooms:
        if predicate(r):
            return r
    return None


def derive_flow_paths(
    rooms: list[Room],
    adjacency: list[AdjacencyEdge],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> FlowPaths:
    """4종 동선 산출."""
    # product_process_order: process_no가 있는 process Room만 정렬.
    process_rooms = [
        r for r in rooms
        if r.category == "process"
        and not _AL_PATTERN.search(r.name_en)
        and r.process_no
    ]
    process_sorted = sorted(
        process_rooms, key=lambda r: _process_no_key(r.process_no)
    )
    product_path = [r.room_id for r in process_sorted]

    # 시작·끝 앵커 Room들.
    lobby = _find_first(rooms, lambda r: "lobby" in r.name_en.lower())
    gowning = _find_first(
        rooms,
        lambda r: r.name_en.lower().startswith("gowning"),
    )
    supply = _find_first(
        rooms, lambda r: "supply corridor" in r.name_en.lower()
    )
    return_corridor = _find_first(
        rooms, lambda r: "return corridor" in r.name_en.lower()
    )
    material_in = _find_first(
        rooms,
        lambda r: (
            ("material" in r.name_en.lower() and "in" in r.name_en.lower()
             and "storage" not in r.name_en.lower())
            or "mateial-in" in r.name_en.lower()
        ),
    )
    waste_out = _find_first(
        rooms,
        lambda r: "waste" in r.name_en.lower() and "out" in r.name_en.lower(),
    )

    first_process = process_sorted[0] if process_sorted else None
    last_process = process_sorted[-1] if process_sorted else None

    personnel_entry: list[str] = []
    for room in (lobby, gowning, supply, first_process):
        if room is not None:
            personnel_entry.append(room.room_id)

    personnel_exit: list[str] = []
    for room in (last_process, return_corridor, gowning, lobby):
        if room is not None:
            personnel_exit.append(room.room_id)

    material_entry: list[str] = []
    if input_spec.building.elevator_for_material_in is not None:
        material_entry.append(ELEVATOR_MATERIAL_NODE)
    for room in (material_in, supply, first_process):
        if room is not None:
            material_entry.append(room.room_id)

    waste_exit: list[str] = []
    for room in (last_process, return_corridor, waste_out):
        if room is not None:
            waste_exit.append(room.room_id)
    if input_spec.building.elevator_for_waste_out is not None:
        waste_exit.append(ELEVATOR_WASTE_NODE)

    rationale.append(Rationale(
        rule_id="flow_paths",
        target_id="LAYOUT",
        decision=(
            f"personnel_entry={len(personnel_entry)}, "
            f"material_entry={len(material_entry)}, "
            f"waste_exit={len(waste_exit)}, "
            f"product_order={len(product_path)}"
        ),
        input_facts={
            "process_room_count": len(process_sorted),
            "has_lobby": lobby is not None,
            "has_supply_corridor": supply is not None,
            "has_return_corridor": return_corridor is not None,
            "has_material_in": material_in is not None,
            "has_waste_out": waste_out is not None,
            "elevator_material": input_spec.building.elevator_for_material_in,
            "elevator_waste": input_spec.building.elevator_for_waste_out,
        },
        applied_logic=(
            "Lobby → Gowning → Supply → process / 역방향 + 엘리베이터 anchor."
        ),
        source_reference="보고서 v0.2 §3.2 (flow_paths) + §5.4 (엘리베이터)",
        flags=[],
    ))

    return FlowPaths(
        personnel_entry=personnel_entry,
        personnel_exit=personnel_exit,
        material_entry=material_entry,
        waste_exit=waste_exit,
        product_process_order=product_path,
    )
