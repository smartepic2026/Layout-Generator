"""Rule 4 — 청정등급 부여 (Clean Grade Assignment).

근거: GMP Layout Logic_0510 §4 + EU GMP Annex 1
- A: 무균공정 barrier (Isolator/RABS/Cleanbench/BSC)
- B: A barrier를 둘러싼 Room
- C: 주공정 Room (default)
- D: 주공정 Room이 closed system이거나 보조 구역
- CNC: 자재 보관/세척/갱의/IPC/이동 통로 등
- NC: 동선/제조환경에 영향 없는 구역

이 룰은 KB의 grade_options와 default_grade에서 선택하되:
- URS overrides.grade_overrides가 있으면 강제
- aseptic_filling_onsite=True 면 Inoculation을 Grade B로 격상
- closed_system_main_process=True 면 default가 D로 떨어진 경우 유지

색상/투명도/패턴은 grade_colors KB에서 채움.
"""
from __future__ import annotations

from ..kb_loader import grade_colors_kb, rooms_kb
from ..working_state import WorkingState


def apply(state: WorkingState) -> None:
    modality = state.urs.product.modality
    rooms_data = rooms_kb(modality)["rooms"]
    colors = grade_colors_kb()["grades"]
    rooms_by_id = {r["id"]: r for r in rooms_data}

    overrides = state.urs.overrides.grade_overrides
    aseptic = state.urs.product.aseptic_filling_onsite
    closed = state.urs.product.closed_system_main_process

    for rid, room in state.rooms.items():
        kb_room = rooms_by_id.get(rid)
        if not kb_room:
            continue

        chosen, reason = _decide_grade(rid, kb_room, overrides, aseptic, closed)
        room.clean_grade = chosen  # type: ignore[assignment]

        meta = colors[chosen]
        room.background_color = meta["fill"]
        room.color_pattern = meta["pattern"]
        room.transparency_pct = meta["transparency_pct"]

        state.log(
            rule_id="rule_4_clean_grade",
            target=rid,
            decision=f"Grade {chosen} (color={meta['description']})",
            reason=reason,
            source="GMP Layout Logic_0510 §4 + EU GMP Annex 1",
        )

    # 색상 범례를 constraints에 노출 (Drawing Agent가 범례 박스 그릴 때)
    state.constraints.color_legend = {
        g: f"fill={m['fill']} border={m['border']} ({m['description']}, opacity={m['transparency_pct']}%)"
        for g, m in colors.items()
    }


def _decide_grade(
    rid: str,
    kb_room: dict,
    overrides: dict,
    aseptic: bool,
    closed: bool,
) -> tuple[str, str]:
    if rid in overrides:
        return overrides[rid], f"URS overrides.grade_overrides[{rid}]={overrides[rid]} (사용자 강제)"

    options = kb_room.get("grade_options", [])
    default = kb_room.get("default_grade")

    # Aseptic filling on-site → Inoculation 격상
    if aseptic and rid == "R_INOCULATION" and "B" in options:
        return "B", "aseptic_filling_onsite=True → 접종실 Grade B (층류장치 둘러싼 Room)"

    # closed system → 주공정도 D 허용
    if closed and "D" in options and default == "C":
        return "D", "closed_system_main_process=True → 주공정 Grade D 허용 (밀폐형 장비)"

    if default:
        return default, f"KB default_grade for {rid}={default}"

    return options[0], f"KB grade_options[0]={options[0]} (default 미지정)"
