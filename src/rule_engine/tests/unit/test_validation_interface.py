"""L1 unit test — validation_interface.

회의 안건 #3 (2026-05-26) 결정 반영 사항 검증:
    - JSON 직렬화/역직렬화 round-trip
    - retry 3회 cutoff 동작
    - stub validator의 always_pass / suspected_violation 기반 분기
    - URS 우선 정책: retry 시 input_spec 미변경
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Callable

from src.rule_engine.models import (
    Constraints,
    FlowPaths,
    RuleEngineOutput,
    Zones,
)
from src.rule_engine.validation_interface import (
    MAX_RETRIES_DEFAULT,
    AcknowledgedFlag,
    NewViolation,
    ValidationLoopResult,
    ValidationVerdict,
    deserialize_verdict,
    make_stub_validator,
    run_with_validation_loop,
    serialize_for_validation,
)


# ---------------------------------------------------------------------------
# ValidationVerdict (de)serialization
# ---------------------------------------------------------------------------

def test_verdict_to_json_basic():
    """to_json은 모든 필드를 직렬화해야 함."""
    v = ValidationVerdict(
        status="pass",
        rule_engine_input_hash="abc123",
        timestamp="2026-05-27T00:00:00+00:00",
        retry_count=0,
        summary="all good",
    )
    s = v.to_json()
    data = json.loads(s)
    assert data["status"] == "pass"
    assert data["rule_engine_input_hash"] == "abc123"
    assert data["retry_count"] == 0
    assert data["summary"] == "all good"
    assert data["acknowledged_flags"] == []
    assert data["new_violations"] == []


def test_verdict_roundtrip_with_nested():
    """to_json → from_dict round-trip이 모든 nested dataclass를 보존해야 함."""
    v = ValidationVerdict(
        status="needs_revision",
        rule_engine_input_hash="hash",
        timestamp="2026-05-27T00:00:00+00:00",
        retry_count=1,
        acknowledged_flags=[
            AcknowledgedFlag(
                rule_engine_flag_index=(0, 0),
                rule_id="rule_03_room_size",
                verdict="confirmed_violation",
                rag_citations=["EU GMP Annex 1 §4.29"],
                note="천정 높이 부족",
            ),
        ],
        new_violations=[
            NewViolation(
                target_id="R_INOC",
                rule_reference="WHO TRS 961 Annex 6",
                severity="error",
                note="Grade B 인접 corridor가 Grade D",
                rag_citations=["WHO TRS 961"],
            ),
        ],
        summary="2 issues",
    )
    data = json.loads(v.to_json())
    v2 = ValidationVerdict.from_dict(data)
    assert v2.status == "needs_revision"
    assert len(v2.acknowledged_flags) == 1
    assert v2.acknowledged_flags[0].rule_id == "rule_03_room_size"
    # tuple → JSON list → from_dict 에서 다시 tuple 로 normalize 됨
    assert tuple(v2.acknowledged_flags[0].rule_engine_flag_index) == (0, 0)
    assert len(v2.new_violations) == 1
    assert v2.new_violations[0].severity == "error"


# ---------------------------------------------------------------------------
# serialize_for_validation / deserialize_verdict — file I/O
# ---------------------------------------------------------------------------

def _empty_output() -> RuleEngineOutput:
    """7 블록 모두 빈 RuleEngineOutput."""
    return RuleEngineOutput(
        rooms=[],
        airlocks=[],
        adjacency=[],
        flow_paths=FlowPaths(
            personnel_entry=[], personnel_exit=[],
            material_entry=[], waste_exit=[],
            product_process_order=[],
        ),
        zones=Zones(process_zone=[], auxiliary_zone=[], nc_zone=[]),
        constraints=Constraints(
            corridor_width_mm={},
            airlock_size_mm={},
            ceiling_height_mm={},
            equipment_clearance_mm={},
            process_zone_area_ratio={},
            supply_return_no_direct_connection=True,
            color_legend={},
        ),
        rationale=[],
        meta={
            "engine_version": "0.1.0",
            "input_hash": "test",
            "stats": {
                "rooms": 0,
                "airlocks": 0,
                "adjacency_edges": 0,
                "rationale_entries": 0,
                "flag_counts": {},
            },
        },
    )


def test_serialize_for_validation_writes_valid_json():
    """파일이 생성되고 to_json 결과와 동일한 내용을 담아야 함."""
    out = _empty_output()
    with tempfile.TemporaryDirectory() as tmp:
        p = serialize_for_validation(out, Path(tmp) / "output.json")
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["meta"]["engine_version"] == "0.1.0"
        assert data["zones"]["process_zone"] == []


def test_serialize_creates_parent_dirs():
    """존재하지 않는 부모 디렉토리는 자동 생성되어야 함."""
    out = _empty_output()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "nested" / "deep" / "output.json"
        p = serialize_for_validation(out, target)
        assert p.exists()


def test_deserialize_verdict_roundtrip():
    """verdict → JSON 파일 → deserialize → 동일 객체."""
    v = ValidationVerdict(
        status="pass",
        rule_engine_input_hash="h",
        timestamp="2026-05-27T00:00:00+00:00",
        retry_count=0,
        summary="ok",
    )
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "verdict.json"
        p.write_text(v.to_json(), encoding="utf-8")
        v2 = deserialize_verdict(p)
        assert v2.status == "pass"
        assert v2.rule_engine_input_hash == "h"
        assert v2.summary == "ok"


# ---------------------------------------------------------------------------
# run_with_validation_loop — retry 3회 cutoff (회의 안건 #3)
# ---------------------------------------------------------------------------

def _always_pass_validator() -> Callable[[Path], ValidationVerdict]:
    def _v(path: Path) -> ValidationVerdict:
        return ValidationVerdict(
            status="pass",
            rule_engine_input_hash="x",
            timestamp="2026-05-27T00:00:00+00:00",
            retry_count=0,
            summary="ok",
        )
    return _v


def _always_fail_validator() -> Callable[[Path], ValidationVerdict]:
    def _v(path: Path) -> ValidationVerdict:
        return ValidationVerdict(
            status="needs_revision",
            rule_engine_input_hash="x",
            timestamp="2026-05-27T00:00:00+00:00",
            retry_count=0,
            summary="not ok",
        )
    return _v


def test_loop_passes_on_first_attempt(empty_input):
    """pass 시 1 attempt, escalated_to_user=False."""
    with tempfile.TemporaryDirectory() as tmp:
        result = run_with_validation_loop(
            empty_input,
            _always_pass_validator(),
            output_dir=tmp,
        )
    assert isinstance(result, ValidationLoopResult)
    assert result.attempts == 1
    assert result.escalated_to_user is False
    assert result.final_verdict.status == "pass"


def test_loop_escalates_after_max_retries(empty_input):
    """fail 지속 시 max_retries+1 attempts, escalated_to_user=True."""
    with tempfile.TemporaryDirectory() as tmp:
        result = run_with_validation_loop(
            empty_input,
            _always_fail_validator(),
            output_dir=tmp,
            max_retries=3,
        )
    assert result.attempts == 4  # 첫 시도 1 + retry 3
    assert result.escalated_to_user is True
    assert result.final_verdict.status == "needs_revision"


def test_loop_max_retries_default_is_three():
    """회의 안건 #3: 기본 retry 횟수는 3."""
    assert MAX_RETRIES_DEFAULT == 3


def test_loop_writes_json_per_attempt(empty_input):
    """attempt 마다 별도 JSON 파일이 생성되어야 함."""
    with tempfile.TemporaryDirectory() as tmp:
        run_with_validation_loop(
            empty_input,
            _always_fail_validator(),
            output_dir=tmp,
            max_retries=2,
        )
        files = sorted(Path(tmp).glob("output_attempt*.json"))
    # max_retries=2 → 첫 시도 1 + 추가 2 = 3 attempts → 3 파일
    assert len(files) == 3
    assert files[0].name == "output_attempt0.json"
    assert files[-1].name == "output_attempt2.json"


def test_loop_input_spec_unchanged(empty_input):
    """URS 우선 정책: retry 중에도 input_spec 객체는 변경되지 않아야 함."""
    original_floor_area = empty_input.building.total_floor_area_m2
    original_urs_count = len(empty_input.urs_rooms)
    with tempfile.TemporaryDirectory() as tmp:
        run_with_validation_loop(
            empty_input,
            _always_fail_validator(),
            output_dir=tmp,
            max_retries=2,
        )
    assert empty_input.building.total_floor_area_m2 == original_floor_area
    assert len(empty_input.urs_rooms) == original_urs_count


# ---------------------------------------------------------------------------
# make_stub_validator
# ---------------------------------------------------------------------------

def test_stub_always_pass_flag():
    """always_pass=True 면 violations가 있어도 pass."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "out.json"
        p.write_text(
            json.dumps({
                "meta": {
                    "input_hash": "h",
                    "stats": {"flag_counts": {"suspected_violation": 5}},
                }
            }),
            encoding="utf-8",
        )
        validator = make_stub_validator(always_pass=True)
        verdict = validator(p)
    assert verdict.status == "pass"


def test_stub_needs_revision_when_violations_present():
    """always_pass=False 면 suspected_violation > 0 일 때 needs_revision."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "out.json"
        p.write_text(
            json.dumps({
                "meta": {
                    "input_hash": "h",
                    "stats": {"flag_counts": {"suspected_violation": 3}},
                }
            }),
            encoding="utf-8",
        )
        validator = make_stub_validator(always_pass=False)
        verdict = validator(p)
    assert verdict.status == "needs_revision"


def test_stub_passes_when_no_violations():
    """suspected_violation=0 이면 pass."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "out.json"
        p.write_text(
            json.dumps({
                "meta": {
                    "input_hash": "h",
                    "stats": {"flag_counts": {}},
                }
            }),
            encoding="utf-8",
        )
        validator = make_stub_validator(always_pass=False)
        verdict = validator(p)
    assert verdict.status == "pass"
