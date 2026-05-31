"""rule_engine — GMP Layout Rule Engine (v1 prototype).

이 패키지는 URS 입력을 받아 Documentation Agent에 넘길 7 블록의 도면
사양을 산출한다. 보고서 `Layout_RuleEngine_Report_v0.2.docx` 의 I/O
스펙을 그대로 구현한다.

v1 스코프 (보고서 v0.2 §5.5):
    - Modality: mAb only
    - 공정 범위: DS 제조라인까지 (fill-finish 제외)
    - 시설: 건물 내부 layout (옥외 시설 제외)
    - 라인 수: 단일 라인, 단일층
    - 엘리베이터: 외부 위치 정보로만 반영
"""
from __future__ import annotations

from .engine import run_rule_engine
from .models import (
    AirLock,
    AdjacencyEdge,
    Constraints,
    Equipment,
    Flag,
    FlowPaths,
    Overrides,
    OrganizationSpec,
    ProductSpec,
    BuildingSpec,
    FlowPolicy,
    Rationale,
    Room,
    RuleEngineInput,
    RuleEngineOutput,
    Zones,
)
from .urs_parser import (
    URS_PATH,
    build_rule_engine_input,
    clock_from_text,
    load_urs_as_input,
    parse_urs_xlsx,
)
from .validation_interface import (
    AcknowledgedFlag,
    NewViolation,
    ValidationLoopResult,
    ValidationVerdict,
    deserialize_verdict,
    make_stub_validator,
    run_with_validation_loop,
    serialize_for_validation,
)
from .validators import (
    RagValidatorConfig,
    make_rag_validator,
)

__all__ = [
    "run_rule_engine",
    "RuleEngineInput",
    "RuleEngineOutput",
    "ProductSpec",
    "BuildingSpec",
    "FlowPolicy",
    "OrganizationSpec",
    "Overrides",
    "Equipment",
    "Room",
    "AirLock",
    "AdjacencyEdge",
    "FlowPaths",
    "Zones",
    "Constraints",
    "Rationale",
    "Flag",
    "ValidationVerdict",
    "AcknowledgedFlag",
    "NewViolation",
    "ValidationLoopResult",
    "serialize_for_validation",
    "deserialize_verdict",
    "run_with_validation_loop",
    "make_stub_validator",
    "make_rag_validator",
    "RagValidatorConfig",
    "URS_PATH",
    "parse_urs_xlsx",
    "build_rule_engine_input",
    "load_urs_as_input",
    "clock_from_text",
]

__version__ = "0.1.0-skeleton"
