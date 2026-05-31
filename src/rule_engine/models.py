"""Data models for the rule_engine layer.

이 파일은 Rule Engine이 주고받는 모든 데이터 구조를 정의한다.
보고서 v0.2 §3 (I/O 스펙) + 2026-05-26 회의 결정 그대로 따른다.
**로직은 두지 않는다** — IO·검증·변환 없음. 직렬화 메서드만 제공.

Public types (5 input groups + 7 output blocks + 보조):
    ProductSpec, BuildingSpec, FlowPolicy, OrganizationSpec, Overrides
    RuleEngineInput
    Room, AirLock, AdjacencyEdge, FlowPaths, Zones, Constraints, Rationale
    Flag, Equipment
    RuleEngineOutput  — to_dict() / to_json() 직렬화 메서드 제공 (회의 안건 #3·#4)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CleanGrade = Literal["A", "B", "C", "D", "CNC", "NC"]
RoomCategory = Literal["process", "auxiliary", "NC"]
GowningType = Literal["무균복", "무진복", "스크럽", "일상복"]
GowningMethod = Literal["over gowning", "degowning and gowning", "regular"]
ClockDirection = Literal["12", "3", "6", "9"]
RoomFlow = Literal["One-way", "Both-way"]
FlowDirection = Literal["one_way_in", "one_way_out", "bidirectional"]
ALKind = Literal[
    "CAL", "CAL_in", "CAL_out",
    "MAL", "MAL_in", "MAL_out",
    "PAL", "PAL_in", "PAL_out",
]
ALFlowType = Literal["cascade", "sink", "bubble"]
RelationshipType = Literal["door", "shared_wall", "passthrough_only"]
DoorSwingTarget = Literal["high_pressure_side", "low_pressure_side"]
FlagSeverity = Literal["suspected_violation", "info", "warning"]


@dataclass(frozen=True, slots=True)
class Equipment:
    """Room 내 장비 한 점."""
    instance_id: str
    name: str
    width_mm: int
    depth_mm: int
    height_mm: int
    weight_kg: float | None
    max_operating_weight_kg: float | None
    process_no: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProductSpec:
    """제품·공정 특성. v1은 mAb DS 한정."""
    modality: Literal["mAb"]
    culture_scale_L: int
    n_product_types: int
    virus_filtration_required: bool
    closed_system_main_process: bool


@dataclass(frozen=True, slots=True)
class BuildingSpec:
    """건축물 제약. v0.2에서 elevator 필드 추가 (보고서 §5.4)."""
    total_floor_area_m2: float
    width_mm: int
    depth_mm: int
    floor_level: int
    personnel_entrance: ClockDirection
    material_inlet: ClockDirection
    waste_outlet: ClockDirection
    elevator_for_material_in: ClockDirection | None
    elevator_for_waste_out: ClockDirection | None


@dataclass(frozen=True, slots=True)
class FlowPolicy:
    """동선·흐름 정책."""
    airlock_default_type: ALFlowType
    supply_return_corridor_separate: bool
    biological_safety_isolation: bool


@dataclass(frozen=True, slots=True)
class OrganizationSpec:
    """조직·인원 정책."""
    gender_separated_gowning: bool
    include_office_onsite: bool
    include_toilet_onsite: bool
    include_monitoring_room_onsite: bool
    include_lobby_onsite: bool


@dataclass(frozen=True, slots=True)
class Overrides:
    """사용자 명시 override."""
    force_include_rooms: list[str] = field(default_factory=list)
    force_exclude_rooms: list[str] = field(default_factory=list)
    area_overrides: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuleEngineInput:
    """Rule Engine 입력 컨테이너."""
    product: ProductSpec
    building: BuildingSpec
    flow_policy: FlowPolicy
    organization: OrganizationSpec
    overrides: Overrides
    urs_rooms: list[dict] = field(default_factory=list)
    urs_equipment: list[dict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Room:
    """Room 한 점. URS 통과 필드 + Rule Engine derive 필드 + 회의 #5 area_ratio_pct."""
    room_id: str
    name_ko: str
    name_en: str
    category: RoomCategory
    clean_grade: CleanGrade
    room_flow: RoomFlow
    gowning_type: GowningType
    gowning_method: GowningMethod | None
    equipment: list[Equipment]
    process_no: list[str]
    # 룰 엔진 derive
    area_m2: float | None
    width_mm: int | None
    depth_mm: int | None
    ceiling_height_mm: int | None
    volume_m3: float | None
    differential_pressure_Pa: float | None
    air_changes_per_hour: float | None
    recovery_time_min: float | None
    background_color: str | None
    transparency_pct: int | None
    well_type_ceiling: bool
    # 회의 안건 #5 (2026-05-26): URS 면적 비율 (%).
    # 모든 Room의 area_ratio_pct 합은 100±0.5% 이내여야 함 (rule_03 검증).
    area_ratio_pct: float | None = None


@dataclass(frozen=True, slots=True)
class AirLock:
    """전실 (Air Lock)."""
    al_id: str
    kind: ALKind
    clean_grade: CleanGrade
    area_m2: float | None
    flow_type: ALFlowType
    connects_higher_room: str | None
    connects_lower_room: str | None
    purpose: Literal["personnel", "material", "common"]
    differential_pressure_Pa: float | None


@dataclass(frozen=True, slots=True)
class AdjacencyEdge:
    """Room ↔ Room (또는 Room ↔ AL) 인접 관계."""
    from_id: str
    to_id: str
    relationship: RelationshipType
    door_count: int
    door_size_mm: int | None
    door_swing_target: DoorSwingTarget | None
    flow_direction: FlowDirection
    is_elevator_constraint: bool = False


@dataclass(frozen=True, slots=True)
class FlowPaths:
    """4종 동선."""
    personnel_entry: list[str]
    personnel_exit: list[str]
    material_entry: list[str]
    waste_exit: list[str]
    product_process_order: list[str]


@dataclass(frozen=True, slots=True)
class Zones:
    """구역 그룹핑."""
    process_zone: list[str]
    auxiliary_zone: list[str]
    nc_zone: list[str]


@dataclass(frozen=True, slots=True)
class Constraints:
    """정량 룰 번들."""
    corridor_width_mm: dict[str, int]
    airlock_size_mm: dict[str, list[int]]
    ceiling_height_mm: dict[str, int]
    equipment_clearance_mm: dict[str, int]
    process_zone_area_ratio: dict[str, float]
    supply_return_no_direct_connection: bool
    color_legend: dict[CleanGrade, str]


@dataclass(frozen=True, slots=True)
class Flag:
    """의심 위반 마킹."""
    rule_id: str
    severity: FlagSeverity
    note: str


@dataclass(frozen=True, slots=True)
class Rationale:
    """룰 적용 추적 한 줄."""
    rule_id: str
    target_id: str
    decision: str
    input_facts: dict
    applied_logic: str
    source_reference: str
    flags: list[Flag] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RuleEngineOutput:
    """Rule Engine 출력 컨테이너 — 7 블록 + meta.

    회의 안건 #3·#4 결정(2026-05-26) 반영: to_dict / to_json 직렬화 메서드 제공.
    """
    rooms: list[Room]
    airlocks: list[AirLock]
    adjacency: list[AdjacencyEdge]
    flow_paths: FlowPaths
    zones: Zones
    constraints: Constraints
    rationale: list[Rationale]
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """7 블록 + meta를 표준 dict로 변환 (안건 #3·#4 결정)."""
        import dataclasses as _dc
        return _dc.asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """7 블록을 JSON 문자열로 직렬화 (안건 #3 결정)."""
        import json
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=indent if indent > 0 else None,
            default=str,
        )
