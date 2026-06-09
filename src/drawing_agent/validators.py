"""Layout-level validation for Drawing Agent outputs.

Rule Engine/RAG constraints are data contracts; this module checks whether the
rendered coordinates actually honor the important spatial rules.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.contract.schemas import RuleEngineOutput
from src.drawing_agent.layout_solver import Layout, Rect, _is_al_fake_room


@dataclass(frozen=True)
class LayoutViolation:
    rule_id: str
    severity: str
    target: str
    message: str


def _touch(a: Rect, b: Rect, tol: float = 50.0) -> bool:
    vertical_overlap = min(a.y2, b.y2) - max(a.y, b.y) > tol
    horizontal_overlap = min(a.x2, b.x2) - max(a.x, b.x) > tol
    return (
        (abs(a.x2 - b.x) <= tol or abs(b.x2 - a.x) <= tol) and vertical_overlap
    ) or (
        (abs(a.y2 - b.y) <= tol or abs(b.y2 - a.y) <= tol) and horizontal_overlap
    )


def _overlap_area(a: Rect, b: Rect) -> float:
    return max(0.0, min(a.x2, b.x2) - max(a.x, b.x)) * max(0.0, min(a.y2, b.y2) - max(a.y, b.y))


def _is_corridor_id(rid: str) -> bool:
    return "CORRIDOR" in rid.upper()


def _door_touches_rect(door, rect: Rect, tol: float = 700.0) -> bool:
    x_ok = rect.x - tol <= door.x <= rect.x2 + tol
    y_ok = rect.y - tol <= door.y <= rect.y2 + tol
    if not (x_ok and y_ok):
        return False
    return (
        abs(door.x - rect.x) <= tol
        or abs(door.x - rect.x2) <= tol
        or abs(door.y - rect.y) <= tol
        or abs(door.y - rect.y2) <= tol
    )


def _find_room(layout: Layout, *subs: str, exclude: tuple[str, ...] = ()) -> str | None:
    for rid in layout.rooms:
        up = rid.upper()
        if any(s.upper() in up for s in subs) and not any(e.upper() in up for e in exclude):
            return rid
    return None


def _main_corridors(layout: Layout) -> dict[str, str | None]:
    return {
        "nc": _find_room(layout, "CORRIDOR_VISITOR") or _find_room(layout, "NC_AUX_CORRIDOR"),
        "d": next((rid for rid in layout.rooms if rid == "R_CORRIDOR" or rid.endswith("_AUX_CORRIDOR")), None),
        "supply": _find_room(layout, "SUPPLY_CORRIDOR"),
    }


def validate_layout(spec: RuleEngineOutput, layout: Layout) -> list[LayoutViolation]:
    out: list[LayoutViolation] = []
    corr = _main_corridors(layout)
    d_corr = corr["d"]
    nc_corr = corr["nc"]
    supply = corr["supply"]
    spec_by_id = {r.id: r for r in spec.rooms}

    if d_corr and d_corr in layout.rooms:
        d_rect = layout.rooms[d_corr].rect
        for rid, pr in layout.rooms.items():
            room = pr.room
            if rid == d_corr or _is_corridor_id(rid) or _is_al_fake_room(room):
                continue
            if room.clean_grade == "D" and not _touch(pr.rect, d_rect):
                out.append(LayoutViolation(
                    "D_ADJ_001", "error", rid,
                    "Grade D room does not directly abut Grade D corridor.",
                ))

    gate_ids = [
        rid for rid in layout.rooms
        if "GOWNING_FEMALE" in rid.upper()
        or "GOWNING_MALE" in rid.upper()
        or ("MATERIAL_IN" in rid.upper() and "STORAGE" not in rid.upper())
    ]
    if nc_corr and d_corr and nc_corr in layout.rooms and d_corr in layout.rooms:
        for rid in gate_ids:
            rr = layout.rooms[rid].rect
            if not (_touch(rr, layout.rooms[nc_corr].rect) and _touch(rr, layout.rooms[d_corr].rect)):
                out.append(LayoutViolation(
                    "GATE_NC_D_001", "error", rid,
                    "NC-D gateway must abut both NC corridor and Grade D corridor.",
                ))

    dc_gates = [
        rid for rid in layout.rooms
        if rid == "R_GOWNING" or "SUPPLY_MAL_IN" in rid.upper()
    ]
    if d_corr and supply and d_corr in layout.rooms and supply in layout.rooms:
        for rid in dc_gates:
            rr = layout.rooms[rid].rect
            if not (_touch(rr, layout.rooms[d_corr].rect) and _touch(rr, layout.rooms[supply].rect)):
                out.append(LayoutViolation(
                    "GATE_D_C_001", "error", rid,
                    "D-C gateway must abut both Grade D corridor and Grade C/Supply corridor.",
                ))

    for door in layout.doors:
        adj = door.adj
        if adj is None:
            continue
        a = layout.rooms.get(adj.from_id)
        b = layout.rooms.get(adj.to_id)
        if a is None or b is None:
            continue
        if not _is_corridor_id(adj.from_id) and not _is_corridor_id(adj.to_id):
            out.append(LayoutViolation(
                "DOOR_001", "error", f"{adj.from_id}->{adj.to_id}",
                "Non-airlock room-to-room personnel door is not allowed; use a corridor.",
            ))

    for rid, pr in layout.rooms.items():
        if _is_corridor_id(rid) or pr.room.is_airlock or _is_al_fake_room(pr.room):
            continue
        has_door = any(_door_touches_rect(d, pr.rect) for d in layout.doors)
        if not has_door:
            attached_als = [pa for pa in layout.airlocks.values() if pa.attached_room_id == rid]
            has_door = any(_door_touches_rect(d, pa.rect) for pa in attached_als for d in layout.doors)
        if not has_door:
            out.append(LayoutViolation(
                "DOOR_002", "error", rid,
                "Room has no visible access door to a corridor or owned airlock.",
            ))

    for aid, pa in layout.airlocks.items():
        proom = layout.rooms.get(pa.attached_room_id)
        if proom is None:
            continue
        for pe in proom.equipment:
            if _overlap_area(pa.rect, pe.rect) > 1.0:
                out.append(LayoutViolation(
                    "EQ_AL_OVERLAP_001", "error", f"{pa.attached_room_id}/{aid}",
                    f"Equipment {pe.equipment.name} overlaps its airlock.",
                ))

    ratios = []
    for rid, pr in layout.rooms.items():
        room = spec_by_id.get(rid)
        if room is None or room.area_m2 <= 0 or _is_corridor_id(rid) or _is_al_fake_room(room):
            continue
        ratios.append((rid, pr.rect.area_m2, room.area_m2))
    for i, (ra, draw_a, spec_a) in enumerate(ratios):
        for rb, draw_b, spec_b in ratios[i + 1:]:
            spec_ratio = max(spec_a, spec_b) / max(min(spec_a, spec_b), 1e-9)
            draw_ratio = max(draw_a, draw_b) / max(min(draw_a, draw_b), 1e-9)
            if spec_ratio >= 1.8 and draw_ratio < 1.3:
                out.append(LayoutViolation(
                    "AREA_RATIO_001", "warning", f"{ra}/{rb}",
                    "Room visual areas are too similar despite materially different URS area ratios.",
                ))
                break
    return out
