"""룰 1 — 전체 배열 컨셉 (Layout axis).

한 줄 요약:
    원자재 반입구·폐기물 반출구·인원 출입구의 시계방향 표기를 직교 벡터로
    변환해 rationale에 기록한다.

왜 필요한가:
    Excel "Layout 설계 원리 §2"의 첫 단계. 모든 동선 룰(5·6·8·11)이 이 axis를
    참고한다. 시계방향(12/3/6/9시)을 (dx, dy) 벡터로 변환해 후속 룰이 쉽게 쓸
    수 있게 한다.

무엇을 안 하는가:
    개별 Room의 좌표 배치는 안 한다 (Documentation Agent의 책임). 엘리베이터
    위치는 derive/flow_paths.py에서 별도 처리.
"""
from __future__ import annotations

from typing import Final

from ..models import ClockDirection, Flag, Rationale, RuleEngineInput


# 시계방향 → (dx, dy) 단위 벡터 (화면 좌표계: 위=+y).
# 12시 = 북쪽(+y), 3시 = 동(+x), 6시 = 남(-y), 9시 = 서(-x).
_CLOCK_TO_VECTOR: Final[dict[ClockDirection, tuple[int, int]]] = {
    "12": (0, 1),
    "3": (1, 0),
    "6": (0, -1),
    "9": (-1, 0),
}


def apply(input_spec: RuleEngineInput, rationale: list[Rationale]) -> None:
    """Layout axis 결정 후 rationale에 기록.

    Args:
        input_spec: 현재 룰 엔진 입력 (building 참조).
        rationale: 룰 적용 추적용 리스트.

    Note:
        반환값이 없는 이유는 axis가 좌표 배치에 직접 쓰이지 않고, 후속 룰
        평가 시 참고하는 "메타 정보"이기 때문. 결과는 rationale에 기록되어
        Documentation Agent와 Validation Agent에게 전달된다.
    """
    building = input_spec.building
    material_v = _CLOCK_TO_VECTOR[building.material_inlet]
    waste_v = _CLOCK_TO_VECTOR[building.waste_outlet]
    personnel_v = _CLOCK_TO_VECTOR[building.personnel_entrance]

    # 동선 axis: 자재 반입구 → 폐기물 반출구 방향.
    axis_dx = waste_v[0] - material_v[0]
    axis_dy = waste_v[1] - material_v[1]

    flags: list[Flag] = []
    # 의심 위반: 자재 반입구와 폐기물 반출구가 같은 위치이면 동선 분리가 안 됨.
    if (axis_dx, axis_dy) == (0, 0):
        flags.append(Flag(
            rule_id="rule_01_layout_axis",
            severity="suspected_violation",
            note=(
                f"material_inlet({building.material_inlet}시)과 "
                f"waste_outlet({building.waste_outlet}시)이 같음 — "
                "동선 분리 불가"
            ),
        ))

    rationale.append(Rationale(
        rule_id="rule_01_layout_axis",
        target_id="LAYOUT",
        decision=f"axis_vector=({axis_dx}, {axis_dy})",
        input_facts={
            "material_inlet": building.material_inlet,
            "waste_outlet": building.waste_outlet,
            "personnel_entrance": building.personnel_entrance,
            "material_vector": material_v,
            "waste_vector": waste_v,
            "personnel_vector": personnel_v,
        },
        applied_logic=(
            "시계방향(12/3/6/9시)을 단위 벡터로 변환. axis = waste - material."
        ),
        source_reference="Excel: Layout 설계 원리 §2 (전체 배열 컨셉)",
        flags=flags,
    ))
