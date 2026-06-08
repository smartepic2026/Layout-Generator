"""
Pydantic schemas for Layout-Generator Rule Engine.

URSInput  : 사용자 요구사항 (1단계)
RuleEngineOutput : 7-블록 산출물 (2단계 → 3단계 Drawing Agent 인계)

Source: GMP_Layout_RuleEngine_IO_Spec.md v0.1 + 사용자 정의 7블록 명세
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# ============================================================================
# Common types
# ============================================================================
Grade = Literal["A", "B", "C", "D", "CNC", "NC"]
Direction = Literal["N", "S", "E", "W"]
Modality = Literal["mAb", "vaccine", "ADC", "cell_therapy"]


class StrictModel(BaseModel):
    # extra="ignore" — 모르는 필드는 무시 (D-003 anti-corruption layer 채택).
    # rule_engine 팀원 출력에 우리가 모르는 필드(meta, instance_id, severity,
    # note, elevator 등)가 섞여도 깨지지 않음. 필드명 매핑은 tier1_ruleengine
    # 의 변환 레이어가 따로 담당.
    model_config = ConfigDict(extra="ignore", validate_assignment=True)


# ============================================================================
# 1. INPUT — URS (User Requirements Specification)
# ============================================================================
class ProductSpec(StrictModel):
    """제품/공정 특성. 룰 1, 3, 4의 1차 입력."""
    modality: Modality = "mAb"
    culture_scale_L: int = Field(8000, gt=0, description="배양 규모(L)")
    n_product_types: int = Field(1, ge=1, description="동시 생산 품목 수")
    production_mode: Literal["single_batch", "overlap_batch", "multi_product"] = "single_batch"
    aseptic_filling_onsite: bool = Field(False, description="True면 Grade A/B 필요")
    virus_filtration_required: bool = Field(True, description="One-way flow 종단점")
    closed_system_main_process: bool = Field(False, description="True면 주공정 Grade D 허용")


class BuildingSpec(StrictModel):
    """건축물 제약. 룰 1의 1차 입력."""
    total_floor_area_m2: float = Field(3300, gt=0)
    width_mm: int = Field(78500, gt=0, description="전체 가로(X)")
    depth_mm: int = Field(42500, gt=0, description="전체 세로(Y)")
    floor_level: int = Field(1, ge=1)
    personnel_entry_clock: int = Field(3, ge=1, le=12, description="시계방향 출입구 위치(시)")
    material_inlet_clock: int = Field(12, ge=1, le=12)
    waste_outlet_clock: int = Field(9, ge=1, le=12)
    elevator_position_clock: Optional[int] = Field(None, ge=1, le=12, description="다층일 때 필요")
    support_area_position_preference: Literal["near_material_inlet", "near_personnel_entry", "any"] = "near_material_inlet"


class FlowPolicy(StrictModel):
    """동선/흐름 정책. 룰 6, 7, 8."""
    one_way_flow_required_until: Literal["virus_filtration", "harvest", "none"] = "virus_filtration"
    supply_return_corridor_separate: bool = True
    airlock_default_type: Literal["cascade", "sink", "bubble"] = "cascade"
    biological_safety_isolation: bool = Field(False, description="True면 sink/bubble 강제")


class OrganizationSpec(StrictModel):
    """조직/인적 정책. 룰 12 (NC 포함 여부)."""
    gender_separated_gowning: bool = True
    include_office_onsite: bool = True
    include_toilet_onsite: bool = True
    include_monitoring_room_onsite: bool = True
    include_lobby_onsite: bool = True
    include_lounge_onsite: bool = False


class Overrides(StrictModel):
    """세부 조정. 옵션."""
    force_include_rooms: list[str] = Field(default_factory=list)
    force_exclude_rooms: list[str] = Field(default_factory=list)
    area_overrides_m2: dict[str, float] = Field(default_factory=dict, description="{room_id: area_m2}")
    grade_overrides: dict[str, Grade] = Field(default_factory=dict, description="{room_id: grade}")


class URSInput(StrictModel):
    """전체 URS 입력. Rule Engine의 단일 진입점."""
    project_name: str = "mAb 8000L Conceptual Design"
    product: ProductSpec = Field(default_factory=ProductSpec)
    building: BuildingSpec = Field(default_factory=BuildingSpec)
    flow_policy: FlowPolicy = Field(default_factory=FlowPolicy)
    organization: OrganizationSpec = Field(default_factory=OrganizationSpec)
    overrides: Overrides = Field(default_factory=Overrides)


# ============================================================================
# 2. OUTPUT — 7 Blocks
# ============================================================================

# ---- Block 1: rooms[] ----

# SPEC v0.1 §1.1 + PATCH v0.2 §1·§3·§6 — Equipment 확장 필드용 nested 모델.
# 모두 Optional. 1차 작업에서는 채워지지 않으며 (PATCH §6.2),
# 2차 단계에서 엑셀 `단위공정`/`rule_equipment_layout` 시트 매핑으로 채워진다.
class ClearanceM(StrictModel):
    """장비 4면 청소/유지보수 통로 (m). SPEC §1.1 / PATCH §3."""
    front: Optional[float] = None
    back: Optional[float] = None
    left: Optional[float] = None
    right: Optional[float] = None


class EquipmentNeeds(StrictModel):
    """배치 위치 요구사항. SPEC §1.1 needs{}. 2차 채움(보류)."""
    wall_adjacent: Optional[bool] = None
    near_supply_airlock: Optional[bool] = None
    near_return_airlock: Optional[bool] = None
    downflow_booth: Optional[bool] = None
    biosafety_level: Optional[str] = None  # "BSL-1".."BSL-4"


class Equipment(StrictModel):
    """장비 스펙. SPEC v0.1 §1.1 + PATCH v0.2 §1·§6 확장 필드를 모두 Optional 로 유지.

    [D-005] `process_no` 가 정식 필드명 (팀원 정식 계약). 이전 `process_step`
    명칭은 폐기. Pydantic alias 로 back-compat:
      - JSON {"process_step": ...} 입력도 process_no 로 매핑 (validation_alias).
      - 기존 rule_engine 코드가 `Equipment(process_step="X")` 식 kwarg 으로
        생성하거나 `eq.process_step` 으로 읽는 경우는 본 schema 가 직접 보장
        하지 않음 (팀원 영역 무수정 정책). 깨지면 알려야 함.

    [PATCH §1 #1] sort_order: 공정 순서 정렬용 정수. process_no(문자열)는 라벨.
    """
    name: str
    W_mm: int
    D_mm: int
    H_mm: int
    weight_kg: float = 0
    max_op_weight_kg: float = 0
    # D-005: process_no 정식. process_step (구명) 도 JSON/kwarg 입력 양쪽 허용 (back-compat).
    process_no: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("process_no", "process_step"),
    )
    footprint_m2: float = 0  # computed: W*D / 1e6

    # D-006: rule_engine 코드 (rule_10_equipment.py:44 등) 가 `eq.process_step`
    # 으로 Python 속성 접근. 팀원 영역 무수정 정책상 schema 가 back-compat 제공.
    # 새 코드는 직접 `process_no` 사용.
    @property
    def process_step(self) -> Optional[str]:
        return self.process_no

    # ── PATCH §1 충돌 결정 ──
    sort_order: Optional[int] = None  # 공정 순서 정수 (P1 단조성 계산용)

    # ── 1차 채울 필드 (PATCH §6.2 — 엑셀에서 직접 도출 가능) ──
    grade: Optional[Grade] = None
    bbox_m: Optional[list[float]] = None  # [width_m, depth_m]
    rotatable: Optional[bool] = None
    clearance_m: Optional[ClearanceM] = None
    utilities: list[str] = Field(default_factory=list)
    connects_to: list[str] = Field(default_factory=list)
    incompatible_with: list[str] = Field(default_factory=list)

    # D-007: 같은 방 안 병렬 그룹 — same-room 장비를 같은 sort_order 군집으로
    # 묶는 라벨. tier3 가 product_process_order 기반으로 채움.
    co_locate_group: Optional[str] = None

    # ── 2차 보류 필드 (PATCH §6.2 — 도메인 검수자 부재로 null 유지) ──
    # P3·P5·P8 scoring에서 null이면 skip되도록 scorer가 가드함.
    open_closed: Optional[Literal["open", "closed"]] = None
    contamination_class: list[str] = Field(
        default_factory=list,
        description="raw|crossover|carryover|env (다중). 2차 채움 전엔 빈 리스트.",
    )
    needs: Optional[EquipmentNeeds] = None
    heat_kw: Optional[float] = None
    noise_dba: Optional[float] = None
    flammable: Optional[bool] = None


# SPEC v0.1 §1.2 — Room 확장용 nested 모델. 모두 Optional. 2차 채움.
class RoomAirflow(StrictModel):
    """방 공기 흐름. SPEC §1.2 airflow{}."""
    type: Optional[Literal["unidirectional", "non_unidirectional"]] = None
    supply_points: list[list[float]] = Field(default_factory=list)  # [[x,y], ...]
    return_points: list[list[float]] = Field(default_factory=list)
    direction_vector: Optional[list[float]] = None  # [dx, dy]


class RoomBoundary(StrictModel):
    """방 경계별 인접 zone + 에어록 매핑. SPEC §1.2 boundaries[]."""
    edge: Literal["N", "S", "E", "W"]
    abuts: Optional[str] = None  # 예: "SUPPLY_CORRIDOR" | "RETURN_CORRIDOR" | "PAL"
    airlock: Optional[str] = None  # 예: "MAL_in" | "WAL_out" | "PAL_in"


class Room(StrictModel):
    """방 스펙. 기존 필드는 그대로 두고, SPEC v0.1 §1.2 확장 필드를 Optional 로 추가.
    polygon_m/airflow/boundaries/iso_class 는 PATCH §6.2 기준 2차 채움(보류).
    """
    id: str
    name_ko: str
    name_en: str
    category: Literal["process", "auxiliary", "NC"]
    clean_grade: Grade
    area_m2: float
    area_ratio_pct: Optional[float] = None
    ceiling_height_mm: int = 3000
    has_well_ceiling: bool = False
    volume_m3: float = 0
    background_color: str = "#FFFFFF"
    color_pattern: str = "solid"
    transparency_pct: int = 50
    differential_pressure_Pa: float = 0
    air_changes_per_hour: Optional[int] = None
    recovery_time_min: Optional[int] = None
    gowning_type: Optional[str] = None
    gowning_method: Optional[str] = None
    equipment: list[Equipment] = Field(default_factory=list)
    one_way_flow: bool = False
    is_corridor: bool = False
    corridor_role: Optional[Literal["supply", "return", "auxiliary", "visitor"]] = None
    process_step_ids: list[str] = Field(default_factory=list)
    notes: str = ""

    # ── SPEC v0.1 §1.2 확장 (2차 채움) ──
    polygon_m: Optional[list[list[float]]] = None  # [[x,y], ...] 방 외곽 좌표 (m)
    airflow: Optional[RoomAirflow] = None
    boundaries: list[RoomBoundary] = Field(default_factory=list)
    iso_class: Optional[int] = None  # 5|7|8 (ISO 14644-1 매핑)

    # ── 룰엔진 새 계약 (2026-05-31, Doc Agent #3) — AL 이중표현 dedup ──
    # rooms[] 의 이 항목이 airlocks[] 에도 동일 실체로 존재하는 전실이면 True.
    # 소비자(우리)는 is_airlock=True Room 을 걸러 중복 렌더를 막는다(G3).
    is_airlock: bool = False
    airlock_id: Optional[str] = None  # 대응 AirLock.al_id (is_airlock=True 일 때)


# ---- Block 2: airlocks[] ----
AirlockType = Literal[
    "CAL", "CAL_in", "CAL_out",
    "MAL", "MAL_in", "MAL_out",
    "PAL", "PAL_in", "PAL_out",
]
AirlockPurpose = Literal[
    "personnel_entry", "personnel_exit",
    "material_entry", "material_exit",
    "common", "common_in", "common_out",
]


class Airlock(StrictModel):
    id: str
    type: AirlockType
    clean_grade: Grade
    area_m2: float
    flow_type: Literal["cascade", "sink", "bubble"]
    connects_higher: str = Field(description="더 높은 청정등급 Room id")
    connects_lower: str = Field(description="더 낮은 청정등급 Room id")
    purpose: AirlockPurpose
    differential_pressure_Pa: float = 0


# ---- Block 3: adjacency[] ----
class Adjacency(StrictModel):
    from_id: str
    to_id: str
    relationship: Literal["door", "shared_wall", "passthrough_only"]
    door_count: int = 1
    door_size_mm: int = 1000
    door_swing_to: Optional[str] = Field(None, description="차압 흐름 방향 (= 낮은 압력 쪽 Room id)")
    flow_direction: Literal["one_way_in", "one_way_out", "bidirectional"] = "bidirectional"
    notes: str = ""


# ---- Block 4: flow_paths ----
class FlowPaths(StrictModel):
    personnel_entry: list[str] = Field(default_factory=list)
    personnel_exit: list[str] = Field(default_factory=list)
    material_entry: list[str] = Field(default_factory=list)
    waste_exit: list[str] = Field(default_factory=list)
    product_process_order: list[str] = Field(default_factory=list)


# ---- Block 5: zones ----
class Zones(StrictModel):
    process_zone: list[str] = Field(default_factory=list)
    auxiliary_zone: list[str] = Field(default_factory=list)
    nc_zone: list[str] = Field(default_factory=list)


# ---- Block 6: constraints ----
class RangeMM(StrictModel):
    min: Optional[int] = None
    preferred_min: Optional[int] = None
    preferred_max: Optional[int] = None
    max: Optional[int] = None


class Constraints(StrictModel):
    corridor_width_mm: RangeMM
    airlock_size_mm: dict = Field(default_factory=dict)
    ceiling_height_mm: dict = Field(default_factory=dict)
    equipment_clearance_mm: dict = Field(default_factory=dict)
    process_zone_area_ratio: dict = Field(default_factory=dict)
    supply_return_no_direct_connection: bool = True
    wash_prep_no_personnel_crossing: bool = True
    color_legend: dict[str, str] = Field(default_factory=dict)
    pressure_differential_min_pa: float = 10
    pressure_grade_order: list[Grade] = Field(default_factory=lambda: ["A", "B", "C", "D", "CNC", "NC"])


# ---- Block 7: rationale[] ----
class Rationale(StrictModel):
    rule_id: str = Field(description="e.g. rule_4_clean_grade")
    target: str = Field(description="대상 Room id, Airlock id, Adjacency 등")
    decision: str
    reason: str
    source: str = Field(default="GMP Layout Logic_0510", description="근거 문서/시트")


# ---- Top-level output ----
class RuleEngineOutput(StrictModel):
    """7-블록 산출물. Drawing Agent의 단일 입력."""
    project_name: str
    modality: Modality
    # [W1/E16 2026-06-07] 건물 footprint(전체면적·가로·세로)를 계약에 포함.
    # URS 파서는 읽지만 소연 엔진 출력엔 없어 누락되던 것 → cmd_rule_engine 이 채움.
    # 없으면 기본값(78500x42500)으로 하위호환. drawing 캔버스/면적 스케일의 입력.
    building: BuildingSpec = Field(default_factory=BuildingSpec)
    rooms: list[Room]
    airlocks: list[Airlock]
    adjacency: list[Adjacency]
    flow_paths: FlowPaths
    zones: Zones
    constraints: Constraints
    rationale: list[Rationale] = Field(default_factory=list)
