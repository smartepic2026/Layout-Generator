"""룰 12 — NC 구역 (organization 정책으로 onsite Room 필터).

한 줄 요약:
    organization 옵션에 따라 onsite=False인 NC Room들을 zones.nc_zone에서 제거한다.

왜 필요한가:
    Excel "Layout 설계 원리 §12". 사무실·화장실·로비·휴게실은 별도 층 또는 건물에
    있을 수도 있다. URS에 명시되어 있어도 organization 정책이 False면 onsite에서
    제외하는 게 일관됨.

매칭 규칙: name_en이 다음 키워드를 포함하면 해당 옵션과 매핑.
    "Office"             → include_office_onsite
    "Toilet"             → include_toilet_onsite
    "Monitoring"         → include_monitoring_room_onsite
    "Lobby" / "Lounge"   → include_lobby_onsite

무엇을 안 하는가:
    Room을 삭제하지 않는다. zones.nc_zone에서만 제거 (rooms 리스트는 유지).
"""
from __future__ import annotations

from ..models import Flag, OrganizationSpec, Rationale, Room, RuleEngineInput, Zones


def _is_excluded(name_en: str, org: OrganizationSpec) -> bool:
    """name_en이 organization 정책상 onsite=False인지 판정."""
    n = name_en.lower()
    if "office" in n and not org.include_office_onsite:
        return True
    if "toilet" in n and not org.include_toilet_onsite:
        return True
    if "monitoring" in n and not org.include_monitoring_room_onsite:
        return True
    if ("lobby" in n or "lounge" in n) and not org.include_lobby_onsite:
        return True
    return False


def apply(
    zones: Zones,
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> Zones:
    """organization 정책에 맞게 nc_zone을 필터링."""
    org = input_spec.organization
    id_to_room = {r.room_id: r for r in rooms}
    filtered: list[str] = []
    removed: list[str] = []
    flags: list[Flag] = []

    for room_id in zones.nc_zone:
        room = id_to_room.get(room_id)
        if room is None:
            filtered.append(room_id)
            continue
        if _is_excluded(room.name_en, org):
            removed.append(room.name_en)
            flags.append(Flag(
                rule_id="rule_12_nc_rooms",
                severity="info",
                note=(
                    f"'{room.name_en}' is offsite per organization policy — "
                    f"removed from nc_zone"
                ),
            ))
        else:
            filtered.append(room_id)

    rationale.append(Rationale(
        rule_id="rule_12_nc_rooms",
        target_id="LAYOUT",
        decision=f"nc_zone size: {len(zones.nc_zone)} → {len(filtered)}",
        input_facts={
            "include_office_onsite": org.include_office_onsite,
            "include_toilet_onsite": org.include_toilet_onsite,
            "include_monitoring_room_onsite": org.include_monitoring_room_onsite,
            "include_lobby_onsite": org.include_lobby_onsite,
            "removed_rooms": removed,
        },
        applied_logic="organization onsite 플래그 기반 NC Room 필터링.",
        source_reference="Excel: Layout 설계 원리 §12 (NC 구역)",
        flags=flags,
    ))

    return Zones(
        process_zone=list(zones.process_zone),
        auxiliary_zone=list(zones.auxiliary_zone),
        nc_zone=filtered,
    )
