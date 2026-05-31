"""L1 unit test — urs_parser.

핸드오프(2026-05-28) 후속: `_demo_run` 내부 파서를 정식 모듈로 승격한 뒤
회귀 방지를 위해 핵심 변환 케이스를 잠가둔다.

실제 URS 파일이 없는 환경(skip) 도 안전하게 처리.
minirunner 호환: autouse / indirect parametrize 사용 안 함.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from src.rule_engine.models import RuleEngineInput
from src.rule_engine.urs_parser import (
    URS_PATH,
    build_rule_engine_input,
    clock_from_text,
    load_urs_as_input,
    parse_urs_xlsx,
)


# ---------------------------------------------------------------------------
# clock_from_text — 자유 형식 → ClockDirection enum 값 정규화
# ---------------------------------------------------------------------------

def test_clock_from_text_extracts_12():
    assert clock_from_text("12시 방향") == "12"


def test_clock_from_text_extracts_3():
    assert clock_from_text("3시") == "3"


def test_clock_from_text_extracts_6():
    assert clock_from_text("6 o'clock") == "6"


def test_clock_from_text_extracts_9():
    assert clock_from_text("9시 방향") == "9"


def test_clock_from_text_none_falls_back_to_12():
    assert clock_from_text(None) == "12"


def test_clock_from_text_empty_falls_back_to_12():
    assert clock_from_text("") == "12"


def test_clock_from_text_invalid_digit_falls_back_to_12():
    """'5시' 같은 비 ClockDirection 값은 12 fallback."""
    assert clock_from_text("5시") == "12"


def test_clock_from_text_no_digits_falls_back_to_12():
    assert clock_from_text("정문 방향") == "12"


# ---------------------------------------------------------------------------
# build_rule_engine_input — dict 결과를 RuleEngineInput 으로 조립
# ---------------------------------------------------------------------------

def test_build_input_uses_defaults_when_dimensions_missing():
    """dimensions 가 비어있으면 default (78500 × 42500) 적용."""
    spec = build_rule_engine_input(
        urs_rooms=[],
        urs_equipment=[],
        building_info={
            "floor_level_str": "3층",
            "total_area_m2": 3340,
            "dimensions": None,
            "personnel": "3시 방향",
            "material_in": "12시 방향",
            "waste_out": "9시 방향",
        },
    )
    assert isinstance(spec, RuleEngineInput)
    assert spec.building.width_mm == 78500
    assert spec.building.depth_mm == 42500


def test_build_input_parses_dimensions_string():
    """'78500mm * 42500mm' → (78500, 42500)."""
    spec = build_rule_engine_input(
        urs_rooms=[], urs_equipment=[],
        building_info={
            "dimensions": "78500mm * 42500mm",
            "total_area_m2": 3340,
            "floor_level_str": "1층",
            "personnel": "3", "material_in": "12", "waste_out": "9",
        },
    )
    assert spec.building.width_mm == 78500
    assert spec.building.depth_mm == 42500


def test_build_input_parses_floor_level_string():
    """'3층' → 3."""
    spec = build_rule_engine_input(
        urs_rooms=[], urs_equipment=[],
        building_info={
            "floor_level_str": "3층",
            "total_area_m2": 3340,
            "dimensions": "78500mm * 42500mm",
            "personnel": "3", "material_in": "12", "waste_out": "9",
        },
    )
    assert spec.building.floor_level == 3


def test_build_input_floor_level_invalid_falls_back_to_1():
    """숫자 없는 floor_level 문자열은 1 fallback."""
    spec = build_rule_engine_input(
        urs_rooms=[], urs_equipment=[],
        building_info={
            "floor_level_str": "지하층",
            "total_area_m2": 3340,
            "dimensions": "78500mm * 42500mm",
            "personnel": "3", "material_in": "12", "waste_out": "9",
        },
    )
    assert spec.building.floor_level == 1


def test_build_input_default_modality_is_mAb():
    """product 인자 None 이면 v1 기본값 (mAb 8000L)."""
    spec = build_rule_engine_input(
        urs_rooms=[], urs_equipment=[], building_info={},
    )
    assert spec.product.modality == "mAb"
    assert spec.product.culture_scale_L == 8000


def test_build_input_passes_through_rooms_and_equipment():
    """urs_rooms / urs_equipment 가 그대로 통과."""
    rooms = [{"name_en": "Inoc", "clean_grade": "B"}]
    equipment = [{"room_en": "Inoc", "instance_id": "EQ_001"}]
    spec = build_rule_engine_input(
        urs_rooms=rooms,
        urs_equipment=equipment,
        building_info={},
    )
    assert spec.urs_rooms == rooms
    assert spec.urs_equipment == equipment


# ---------------------------------------------------------------------------
# parse_urs_xlsx — 실제 URS 파일이 있을 때만 검증
# ---------------------------------------------------------------------------

def test_parse_urs_xlsx_with_real_file_returns_expected_shape():
    """실제 URS xlsx → (rooms, equipment, building_info) 형태와 핵심 수치 확인."""
    if not URS_PATH.exists():
        return  # 파일 없는 환경에선 skip
    rooms, equipment, building = parse_urs_xlsx(URS_PATH)
    assert isinstance(rooms, list) and isinstance(equipment, list)
    assert isinstance(building, dict)
    # 박제 시점 (2026-05-28) baseline 수치
    assert len(rooms) == 48, f"rooms={len(rooms)} (expected 48)"
    assert len(equipment) == 65, f"equipment={len(equipment)} (expected 65)"


def test_parse_urs_xlsx_returns_room_dict_with_expected_keys():
    """파싱된 room dict 가 정해진 key 셋을 모두 포함."""
    if not URS_PATH.exists():
        return
    rooms, _, _ = parse_urs_xlsx(URS_PATH)
    assert rooms
    sample = rooms[0]
    for key in (
        "name_ko", "name_en", "category", "clean_grade",
        "room_flow", "gowning_type", "process_no",
        "air_changes_per_hour", "area_ratio_pct",
    ):
        assert key in sample, f"missing key: {key}"


def test_parse_urs_xlsx_skips_summation_rows():
    """'합계' 가 포함된 행은 결과에서 제외."""
    if not URS_PATH.exists():
        return
    rooms, _, _ = parse_urs_xlsx(URS_PATH)
    for r in rooms:
        assert "합계" not in str(r.get("name_en") or "")


def test_parse_urs_xlsx_grade_normalized():
    """'Grade B' → 'B' 정규화 확인."""
    if not URS_PATH.exists():
        return
    rooms, _, _ = parse_urs_xlsx(URS_PATH)
    grades = {r["clean_grade"] for r in rooms}
    # 'Grade ' prefix 가 제거된 단일 문자만 남아있어야.
    assert all(not g.startswith("Grade ") for g in grades), grades


def test_parse_urs_xlsx_raises_on_missing_file():
    """존재하지 않는 파일은 FileNotFoundError."""
    bogus = Path(tempfile.gettempdir()) / "definitely_not_a_urs_file_xyz.xlsx"
    try:
        parse_urs_xlsx(bogus)
    except FileNotFoundError:
        return
    assert False, "FileNotFoundError 이 발생해야 함"


# ---------------------------------------------------------------------------
# load_urs_as_input — 한 줄 helper
# ---------------------------------------------------------------------------

def test_load_urs_as_input_returns_rule_engine_input():
    """load_urs_as_input 이 RuleEngineInput 을 돌려준다."""
    if not URS_PATH.exists():
        return
    spec = load_urs_as_input()
    assert isinstance(spec, RuleEngineInput)
    assert len(spec.urs_rooms) == 48
    assert len(spec.urs_equipment) == 65


def test_load_urs_as_input_default_building_values():
    """기본 building 값이 회의 #5 기준 (3340 m², 78500 × 42500) 으로 들어감."""
    if not URS_PATH.exists():
        return
    spec = load_urs_as_input()
    # URS xlsx 의 메타가 그대로 통과.
    assert spec.building.total_floor_area_m2 == 3340.0
    assert spec.building.width_mm == 78500
    assert spec.building.depth_mm == 42500
