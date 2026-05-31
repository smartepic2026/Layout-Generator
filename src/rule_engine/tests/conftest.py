"""공유 fixture — 모든 테스트가 import 없이 사용 가능.

여기에 모은 fixture들은 작고 결정론적인 mock URS를 만든다. 실제 URS xlsx는
parser 완성 후에 별도 e2e 테스트(golden file)에서 사용한다.
"""
from __future__ import annotations

import pytest

from src.rule_engine.models import (
    BuildingSpec,
    Equipment,
    FlowPolicy,
    OrganizationSpec,
    Overrides,
    ProductSpec,
    Room,
    RuleEngineInput,
)


# ---------------------------------------------------------------------------
# 작은 mock URS — 4개 Room으로 단순화한 시나리오
# ---------------------------------------------------------------------------

@pytest.fixture
def product_spec_mAb() -> ProductSpec:
    return ProductSpec(
        modality="mAb",
        culture_scale_L=8000,
        n_product_types=1,
        virus_filtration_required=True,
        closed_system_main_process=False,
    )


@pytest.fixture
def building_spec_standard() -> BuildingSpec:
    """URS 예시값: 3층, 3340 m², 78.5m × 42.5m, 자재 12시·폐기물 9시."""
    return BuildingSpec(
        total_floor_area_m2=3340.0,
        width_mm=78500,
        depth_mm=42500,
        floor_level=3,
        personnel_entrance="3",
        material_inlet="12",
        waste_outlet="9",
        elevator_for_material_in="12",
        elevator_for_waste_out="9",
    )


@pytest.fixture
def flow_policy_default() -> FlowPolicy:
    return FlowPolicy(
        airlock_default_type="cascade",
        supply_return_corridor_separate=True,
        biological_safety_isolation=False,
    )


@pytest.fixture
def organization_full_onsite() -> OrganizationSpec:
    return OrganizationSpec(
        gender_separated_gowning=True,
        include_office_onsite=True,
        include_toilet_onsite=True,
        include_monitoring_room_onsite=True,
        include_lobby_onsite=True,
    )


@pytest.fixture
def overrides_empty() -> Overrides:
    return Overrides()


@pytest.fixture
def minimal_rooms() -> list[Room]:
    """청정등급 4개 grade가 모두 들어가는 최소 Room 집합.

    Inoculation(B) → Cell Culture(C) → Material storage(D) → Office(NC).
    """
    return [
        Room(
            room_id="R_INOC",
            name_ko="Seed 접종실",
            name_en="Inoculation",
            category="process",
            clean_grade="B",
            room_flow="One-way",
            gowning_type="무균복",
            gowning_method=None,
            equipment=[],
            process_no=["P3-1. Cell bank 접종"],
            area_m2=None, width_mm=None, depth_mm=None,
            ceiling_height_mm=None, volume_m3=None,
            differential_pressure_Pa=None, air_changes_per_hour=None,
            recovery_time_min=None, background_color=None,
            transparency_pct=None, well_type_ceiling=False,
        ),
        Room(
            room_id="R_CC",
            name_ko="배양실",
            name_en="Cell Culture",
            category="process",
            clean_grade="C",
            room_flow="One-way",
            gowning_type="무진복",
            gowning_method=None,
            equipment=[],
            process_no=["P4-5. 생산배양"],
            area_m2=None, width_mm=None, depth_mm=None,
            ceiling_height_mm=None, volume_m3=None,
            differential_pressure_Pa=None, air_changes_per_hour=None,
            recovery_time_min=None, background_color=None,
            transparency_pct=None, well_type_ceiling=False,
        ),
        Room(
            room_id="R_MATSTORE",
            name_ko="자재 보관실",
            name_en="Material storage",
            category="auxiliary",
            clean_grade="D",
            room_flow="Both-way",
            gowning_type="스크럽",
            gowning_method=None,
            equipment=[],
            process_no=[],
            area_m2=None, width_mm=None, depth_mm=None,
            ceiling_height_mm=None, volume_m3=None,
            differential_pressure_Pa=None, air_changes_per_hour=None,
            recovery_time_min=None, background_color=None,
            transparency_pct=None, well_type_ceiling=False,
        ),
        Room(
            room_id="R_OFFICE",
            name_ko="사무실",
            name_en="Office",
            category="NC",
            clean_grade="NC",
            room_flow="Both-way",
            gowning_type="일상복",
            gowning_method=None,
            equipment=[],
            process_no=[],
            area_m2=None, width_mm=None, depth_mm=None,
            ceiling_height_mm=None, volume_m3=None,
            differential_pressure_Pa=None, air_changes_per_hour=None,
            recovery_time_min=None, background_color=None,
            transparency_pct=None, well_type_ceiling=False,
        ),
    ]


@pytest.fixture
def empty_input(
    product_spec_mAb,
    building_spec_standard,
    flow_policy_default,
    organization_full_onsite,
    overrides_empty,
) -> RuleEngineInput:
    """URS Rooms·Equipment가 비어 있는 minimal input."""
    return RuleEngineInput(
        product=product_spec_mAb,
        building=building_spec_standard,
        flow_policy=flow_policy_default,
        organization=organization_full_onsite,
        overrides=overrides_empty,
    )
