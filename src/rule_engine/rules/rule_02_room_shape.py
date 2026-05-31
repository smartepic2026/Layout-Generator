"""룰 2 — Room 구성 (직사각형 W·D derive).

한 줄 요약:
    Room.area_m2가 채워진 상태에서 width_mm·depth_mm를 직사각형으로 derive한다.

왜 필요한가:
    Excel "Layout 설계 원리 §3". 모든 GMP 관리구역 Room은 직사각형(또는 합)으로
    구성된다. 룰 3에서 area가 정해진 뒤, 룰 2는 그 area를 W·D로 분해한다. 종횡비는
    내부 장비의 W·D 합을 참고해 결정하되 1:1 ~ 1:2 범위로 제약.

무엇을 안 하는가:
    실제 좌표 배치는 안 한다 (Documentation Agent). 복합 형상(여러 직사각형 합)은
    v1에서 다루지 않는다.
"""
from __future__ import annotations

import dataclasses
import math

from ..models import Equipment, Flag, Rationale, Room, RuleEngineInput


# 룰 3에서 가져온 정량값.
_GAP_BETWEEN_EQ_MM = 1000
_GAP_WALL_MM = 600
_ASPECT_MIN = 1.0   # 정사각형 하한
_ASPECT_MAX = 2.0   # 1:2 가로:세로 상한


def _suggest_aspect(equipment: list[Equipment]) -> float:
    """장비 W 합 / D 합을 보고 종횡비를 제안 (1.0~2.0 사이로 clamp)."""
    if not equipment:
        return 1.5  # default
    total_w = sum(eq.width_mm for eq in equipment)
    max_d = max(eq.depth_mm for eq in equipment)
    raw = total_w / max(max_d, 1)
    return max(_ASPECT_MIN, min(_ASPECT_MAX, raw / 2))


def apply(
    rooms: list[Room],
    input_spec: RuleEngineInput,
    rationale: list[Rationale],
) -> list[Room]:
    """area_m2 → width_mm·depth_mm 분해."""
    updated: list[Room] = []
    for room in rooms:
        flags: list[Flag] = []
        new_w = room.width_mm
        new_d = room.depth_mm

        if room.area_m2 is not None and (new_w is None or new_d is None):
            aspect = _suggest_aspect(room.equipment)
            # area = w * d, w/d = aspect → d = sqrt(area / aspect), w = aspect * d.
            area_mm2 = room.area_m2 * 1_000_000
            d_mm = math.sqrt(area_mm2 / aspect)
            w_mm = aspect * d_mm
            new_w = int(round(w_mm))
            new_d = int(round(d_mm))

            # 의심 위반: 가장 큰 장비의 D보다 Room D가 작으면 들어가지 않음.
            if room.equipment:
                max_eq_d = max(eq.depth_mm for eq in room.equipment)
                if new_d < max_eq_d + 2 * _GAP_WALL_MM:
                    flags.append(Flag(
                        rule_id="rule_02_room_shape",
                        severity="suspected_violation",
                        note=(
                            f"Room depth {new_d}mm < 최대 장비 depth {max_eq_d}mm + "
                            f"벽 거리 {2*_GAP_WALL_MM}mm"
                        ),
                    ))

        new_room = dataclasses.replace(room, width_mm=new_w, depth_mm=new_d)
        updated.append(new_room)

        rationale.append(Rationale(
            rule_id="rule_02_room_shape",
            target_id=room.room_id,
            decision=f"width={new_w}, depth={new_d}",
            input_facts={
                "area_m2": room.area_m2,
                "equipment_count": len(room.equipment),
            },
            applied_logic=(
                "area = w * d, 종횡비는 장비 W 합 / max D 기반 1~2 clamp."
            ),
            source_reference="Excel: Layout 설계 원리 §3 (Room 구성)",
            flags=flags,
        ))
    return updated
