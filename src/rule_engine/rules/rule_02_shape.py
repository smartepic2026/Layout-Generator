"""Rule 2 — Room 구성 (Shape Constraints).

근거: GMP Layout Logic_0510 §2
- GMP Room은 직사각형(정사각형 포함)
- 필요 시 여러 직사각형의 합 도형 허용
- 하나의 Room = 하나의 오픈 공간 (벽+door로 분리되면 별개 Room)
- 도어는 1~4개 이상 가능

Rule Engine은 도면 좌표를 정하지 않지만, constraints에 도형 제약을 기록하여
Drawing Agent가 직사각형(또는 직사각형 합)만 사용하도록 강제한다.
"""
from __future__ import annotations

from ..working_state import WorkingState


def apply(state: WorkingState) -> None:
    # constraints에 도형 제약 기록 (Drawing Agent가 참조)
    state.constraints.ceiling_height_mm.setdefault("room_shape_allowed", ["rectangle", "rectilinear_union"])

    state.log(
        rule_id="rule_2_shape",
        target="all_rooms",
        decision="Room 도형 = 직사각형 (또는 직사각형 합)",
        reason="청소·동선 관리 용이성. 비직각 형상 금지.",
        source="GMP Layout Logic_0510 §2 Room 구성",
    )
