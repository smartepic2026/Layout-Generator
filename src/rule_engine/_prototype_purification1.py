"""정제실1 면적 계산 prototype — 룰 3 + 룰 10 부분 구현.

목적:
    rule_03_room_size / rule_10_equipment 본문 작성 전에, 가장 복잡한 케이스
    (정제실1, 장비 22개)로 면적 계산 휴리스틱을 검증한다. URS 권장값 300 m²
    에 얼마나 근접하는지 비교한 뒤, 적용할 알고리즘을 결정한다.

세 가지 휴리스틱:
    A. Simple coverage factor   — area = footprint / coverage_ratio
    B. Two-wall layout          — 양쪽 벽면 배치 + 중앙 통로
    C. Perimeter layout         — 4벽 배치 + 중앙 통로 + 정사각형 가정

이 파일은 룰 본문이 아니라 실험용 스크립트다. 결과를 보고 가장 합리적인
알고리즘을 rules/rule_03_room_size.py 의 본문으로 옮긴다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# ---------------------------------------------------------------------------
# 정제실1 장비 데이터 (URS_ConceptualDesign for layout_0516.xlsx 시트3 추출)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EquipItem:
    name: str
    W: int   # mm
    D: int   # mm
    H: int   # mm


PURIFICATION_1_EQUIPMENT: list[EquipItem] = [
    EquipItem("Chromatography system 1", 2000, 1200, 2000),
    EquipItem("Column 1500mm", 2500, 2000, 3000),
    EquipItem("Storage tank-3 4000L", 3500, 2500, 5000),
    EquipItem("Storage tank-4 3000L", 3000, 2500, 4500),
    EquipItem("Buffer tank-1 2000L", 3000, 2500, 4000),
    EquipItem("Buffer tank-2 2000L", 3000, 2500, 4000),
    EquipItem("Buffer tank-3 2000L", 3000, 2500, 4000),
    EquipItem("Buffer tank-4 4000L", 3500, 2500, 5000),
    EquipItem("Buffer tank-5 4000L", 3500, 2500, 5000),
    EquipItem("Buffer tank-6 4000L", 3500, 2500, 5000),
    EquipItem("Reactor 5000L", 3000, 2500, 5000),
    EquipItem("Acid tank 200L", 2000, 2000, 2500),
    EquipItem("Base tank 200L", 2000, 2000, 2500),
    EquipItem("Depth filter system", 2000, 600, 1800),
    EquipItem("Storage tank-5 5000L", 3000, 2500, 5000),
    EquipItem("Chromatography system 2", 2000, 1200, 2000),
    EquipItem("Column 1000mm", 2000, 2000, 2500),
    EquipItem("Storage tank-6 8000L", 3500, 3000, 5500),
    EquipItem("Chromatography system 3", 2000, 1200, 2000),
    EquipItem("Column 800mm", 2000, 2000, 2500),
    EquipItem("Storage tank-7 2000L", 3000, 2500, 4000),
    EquipItem("Nano filtration system", 2000, 800, 1500),
]

URS_REFERENCE_AREA_M2 = 300.0  # URS Room 범례의 권장 면적


# ---------------------------------------------------------------------------
# GMP Layout Logic 룰 3·10에서 추출한 정량 값 (Excel 본문)
# ---------------------------------------------------------------------------

GAP_BETWEEN_EQUIPMENT_MM = 1000        # 룰 10: 장비 간 최소 1000mm
GAP_WALL_TO_EQUIPMENT_MM_MIN = 600     # 룰 10: 장비-벽 600~1200mm
GAP_WALL_TO_EQUIPMENT_MM_MAX = 1200
AISLE_WIDTH_MM = 1500                  # 룰 3·8: 작업 통로, 복도 폭 참고


# ---------------------------------------------------------------------------
# Algorithm A — Simple coverage factor
# ---------------------------------------------------------------------------

def algo_A_coverage_factor(
    equipment: list[EquipItem], coverage_ratio: float = 0.43
) -> dict:
    """전체 풋프린트 / 점유율 가정 = Room 면적.

    coverage_ratio는 URS의 정제실1 (129/300 = 43%) 기준 fitting값.
    일반 GMP cleanroom의 장비 점유율은 25~45% 범위로 알려져 있음.
    """
    footprint_mm2 = sum(eq.W * eq.D for eq in equipment)
    footprint_m2 = footprint_mm2 / 1_000_000
    area_m2 = footprint_m2 / coverage_ratio
    return {
        "algorithm": "A. coverage factor",
        "footprint_m2": footprint_m2,
        "coverage_ratio": coverage_ratio,
        "area_m2": area_m2,
        "trace": (
            f"footprint {footprint_m2:.1f} / ratio {coverage_ratio:.0%} "
            f"= {area_m2:.1f} m²"
        ),
    }


# ---------------------------------------------------------------------------
# Algorithm B — Two-wall layout (양쪽 벽면 1열씩 + 중앙 통로)
# ---------------------------------------------------------------------------

def algo_B_two_wall(equipment: list[EquipItem]) -> dict:
    """장비를 양쪽 벽면을 따라 2열로 배치한다고 가정.

    배치 가정:
        ┌───────────────────────────────┐
        │ wall(1000) ─ equip row 1 ──── │  ← D = max(D)
        │ aisle(1500) ─────────────     │
        │ equip row 2 ─ wall(1000) ──── │  ← D = max(D)
        └───────────────────────────────┘
        ←──── L = ∑W/2 + (n/2 - 1)×1000 + 2×1000 (단부 벽 거리) ────→

    한쪽 벽 길이 = ∑W/2 + (n-2)/2 × gap + 2 × wall_distance
    방 깊이     = 2 × max(D) + aisle + 2 × wall_distance
    """
    n = len(equipment)
    total_W = sum(eq.W for eq in equipment)
    max_D = max(eq.D for eq in equipment)

    # 한쪽 벽에 ceil(n/2) 개, 다른 쪽에 floor(n/2) 개
    n_long_side = (n + 1) // 2
    W_long_side = total_W * n_long_side / n  # 비례 배분 (대략)
    L_mm = (
        W_long_side
        + (n_long_side - 1) * GAP_BETWEEN_EQUIPMENT_MM
        + 2 * GAP_WALL_TO_EQUIPMENT_MM_MIN
    )
    D_room_mm = (
        2 * max_D
        + AISLE_WIDTH_MM
        + 2 * GAP_WALL_TO_EQUIPMENT_MM_MIN
    )
    area_m2 = (L_mm * D_room_mm) / 1_000_000
    return {
        "algorithm": "B. two-wall layout",
        "footprint_m2": sum(eq.W * eq.D for eq in equipment) / 1_000_000,
        "room_width_mm": int(L_mm),
        "room_depth_mm": int(D_room_mm),
        "area_m2": area_m2,
        "trace": (
            f"L={L_mm/1000:.1f}m × D={D_room_mm/1000:.1f}m = {area_m2:.1f} m²"
        ),
    }


# ---------------------------------------------------------------------------
# Algorithm C — Perimeter layout (4벽 배치 + 정사각형 가정)
# ---------------------------------------------------------------------------

def algo_C_perimeter(equipment: list[EquipItem]) -> dict:
    """장비를 4벽 둘레에 배치, 정사각형 Room 가정.

    배치 가정: 모든 장비가 4벽 둘레에 1열로 늘어선다. 정사각형 가정 하에
    한 변 = √area, 둘레 = 4√area = ∑W + (n-1)×gap + 4×wall_distance.

    한 변 길이로부터 area를 역산:
        side = (∑W + (n-1)×gap + 4×wall_distance) / 4 + max(D) + wall_dist + aisle/2
        area = side²

    중앙 정사각형 공간 = side - 2×(max(D) + wall_distance) 가 통로(aisle)
    이상이어야 함.
    """
    n = len(equipment)
    total_W = sum(eq.W for eq in equipment)
    max_D = max(eq.D for eq in equipment)

    perimeter_eq_mm = (
        total_W
        + (n - 1) * GAP_BETWEEN_EQUIPMENT_MM
        + 4 * GAP_WALL_TO_EQUIPMENT_MM_MIN
    )
    # 한 변에 들어가는 장비 길이 분배
    side_from_perimeter = perimeter_eq_mm / 4
    # 깊이 방향으로는 벽-장비 거리 + 장비 D + 중앙 통로 반쪽이 들어가야 함
    side_total = (
        side_from_perimeter
        + 2 * max_D
        + 2 * GAP_WALL_TO_EQUIPMENT_MM_MIN
    )
    area_m2 = (side_total ** 2) / 1_000_000
    central_space_mm = side_total - 2 * (max_D + GAP_WALL_TO_EQUIPMENT_MM_MIN)
    return {
        "algorithm": "C. perimeter layout (square)",
        "footprint_m2": sum(eq.W * eq.D for eq in equipment) / 1_000_000,
        "side_total_mm": int(side_total),
        "central_aisle_mm": int(central_space_mm),
        "area_m2": area_m2,
        "trace": (
            f"side={side_total/1000:.1f}m, central_aisle={central_space_mm/1000:.1f}m, "
            f"area={area_m2:.1f} m²"
        ),
    }


# ---------------------------------------------------------------------------
# 실행 + 결과 비교
# ---------------------------------------------------------------------------

def _pct_diff(value: float, ref: float) -> str:
    diff = (value - ref) / ref * 100
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.1f}%"


def main() -> None:
    print("=" * 78)
    print(f"정제실1 면적 계산 prototype (URS 권장 = {URS_REFERENCE_AREA_M2} m²)")
    print("=" * 78)

    algorithms: list[Callable[[list[EquipItem]], dict]] = [
        lambda e: algo_A_coverage_factor(e, coverage_ratio=0.40),
        lambda e: algo_A_coverage_factor(e, coverage_ratio=0.43),
        algo_B_two_wall,
        algo_C_perimeter,
    ]
    for algo in algorithms:
        result = algo(PURIFICATION_1_EQUIPMENT)
        diff = _pct_diff(result["area_m2"], URS_REFERENCE_AREA_M2)
        print(
            f"\n[{result['algorithm']:<35}] "
            f"area = {result['area_m2']:>6.1f} m²  ({diff} vs URS)"
        )
        print(f"  trace : {result['trace']}")

    # 추가 분석: 풋프린트 점유율
    fp = sum(eq.W * eq.D for eq in PURIFICATION_1_EQUIPMENT) / 1_000_000
    print(
        f"\n* footprint = {fp:.1f} m² → URS 권장 대비 점유율 "
        f"{fp/URS_REFERENCE_AREA_M2:.0%}"
    )
    print(f"* GMP 가이드라인: 작업장 전체에서 공정 zone 면적은 40~70%")
    print(f"* 본 prototype 결과를 토대로 rule_03_room_size 본문 알고리즘 결정")


if __name__ == "__main__":
    main()
