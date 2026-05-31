"""validation_interface — Validation Agent 와의 인터페이스 헬퍼.

회의 안건 #3 결정 (2026-05-26):
    - Rule Engine 출력 (7 블록 + rationale + flag) → **JSON 파일**로 Validation 전달
    - Validation 판정 결과 (pass/fail + 이유) → **JSON**으로 회수
    - 최대 retry **3회** cutoff. 3회 후에도 fail이면 사용자 escalate.

설계 원칙:
    - Rule Engine은 Validation Agent의 내부 구현(LLM, RAG)을 모름.
    - Validator는 callback 함수로 추상화 (`Callable[[Path], ValidationVerdict]`).
    - retry 시 사용자 의도를 보존하기 위해 revision_hints는 input_spec에 반영하지 않고
      별도 채널로 사용자에게 escalate (URS 우선 정책 일관).

Public API:
    ValidationVerdict      — Validation Agent의 판정 결과 dataclass
    AcknowledgedFlag       — flag에 대한 Validation 판정
    NewViolation           — Validation이 새로 발견한 위반
    serialize_for_validation(output, path) -> Path
    deserialize_verdict(path) -> ValidationVerdict
    run_with_validation_loop(input_spec, validator, output_dir, max_retries=3)

Example — RAG validator 와 결합 (2026-05-28 핸드오프 후속 구현):

    >>> from rule_engine import (
    ...     run_with_validation_loop, make_rag_validator, RagValidatorConfig
    ... )
    >>> from rag_interface.search import search  # 구현되면 그대로 import
    >>> validator = make_rag_validator(
    ...     rag_search=search,
    ...     config=RagValidatorConfig(top_k=5),
    ... )
    >>> result = run_with_validation_loop(
    ...     input_spec, validator, output_dir="./runs", max_retries=3
    ... )
    >>> result.final_verdict.status  # "pass" | "needs_revision"
    'needs_revision'
    >>> result.escalated_to_user
    True

    rag_interface.search.search 가 아직 미구현인 시점에는
    `rule_engine._demo_validation_run` 에 있는 `_mock_rag_search` 같은
    deterministic callable 을 주입하면 인터페이스만 검증할 수 있다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from .engine import run_rule_engine
from .models import RuleEngineInput, RuleEngineOutput


VerdictStatus = Literal["pass", "fail", "needs_revision"]


@dataclass(frozen=True, slots=True)
class AcknowledgedFlag:
    """Rule Engine이 마킹한 flag에 대한 Validation 판정.

    rule_engine_flag_index: 원본 rationale 내 flag의 위치 (rationale_idx, flag_idx)
    """
    rule_engine_flag_index: tuple[int, int]
    rule_id: str
    verdict: Literal["confirmed_violation", "false_alarm", "needs_user_review"]
    rag_citations: list[str] = field(default_factory=list)
    note: str = ""


@dataclass(frozen=True, slots=True)
class NewViolation:
    """Validation Agent가 Rule Engine flag 외에 새로 발견한 위반."""
    target_id: str
    rule_reference: str
    severity: Literal["error", "warning"]
    note: str
    rag_citations: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ValidationVerdict:
    """Validation Agent의 판정 결과 (전체)."""
    status: VerdictStatus
    rule_engine_input_hash: str
    timestamp: str
    retry_count: int
    acknowledged_flags: list[AcknowledgedFlag] = field(default_factory=list)
    new_violations: list[NewViolation] = field(default_factory=list)
    summary: str = ""

    def to_json(self, indent: int = 2) -> str:
        import dataclasses as _dc
        return json.dumps(
            _dc.asdict(self),
            ensure_ascii=False,
            indent=indent if indent > 0 else None,
            default=str,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationVerdict":
        """dict → ValidationVerdict."""
        ack = [AcknowledgedFlag(**a) for a in data.get("acknowledged_flags", [])]
        nv = [NewViolation(**v) for v in data.get("new_violations", [])]
        return cls(
            status=data["status"],
            rule_engine_input_hash=data["rule_engine_input_hash"],
            timestamp=data["timestamp"],
            retry_count=data["retry_count"],
            acknowledged_flags=ack,
            new_violations=nv,
            summary=data.get("summary", ""),
        )


# ---------------------------------------------------------------------------
# Serialization helpers — 회의 안건 #3 결정 반영
# ---------------------------------------------------------------------------

def serialize_for_validation(
    output: RuleEngineOutput, path: str | Path
) -> Path:
    """Rule Engine output을 JSON 파일로 저장하여 Validation Agent에 전달.

    Args:
        output: Rule Engine 결과 (7 블록 + meta).
        path: 저장할 파일 경로.

    Returns:
        실제 저장된 파일 경로 (Path 객체).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(output.to_json(indent=2), encoding="utf-8")
    return p


def deserialize_verdict(path: str | Path) -> ValidationVerdict:
    """Validation Agent가 작성한 verdict JSON을 객체로 변환.

    Args:
        path: Validation Agent의 결과 파일 경로.

    Returns:
        ValidationVerdict 객체.
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return ValidationVerdict.from_dict(data)


# ---------------------------------------------------------------------------
# Retry orchestration — 회의 안건 #3: max 3회 cutoff
# ---------------------------------------------------------------------------

MAX_RETRIES_DEFAULT = 3


@dataclass(frozen=True, slots=True)
class ValidationLoopResult:
    """run_with_validation_loop의 최종 결과."""
    final_output: RuleEngineOutput
    final_verdict: ValidationVerdict
    attempts: int
    escalated_to_user: bool


def run_with_validation_loop(
    input_spec: RuleEngineInput,
    validator: Callable[[Path], ValidationVerdict],
    output_dir: str | Path = "./validation_runs",
    max_retries: int = MAX_RETRIES_DEFAULT,
) -> ValidationLoopResult:
    """Rule Engine → Validation 반복 호출. 회의 안건 #3 retry 3회 cutoff 적용.

    한 줄 요약:
        Rule Engine output → JSON → Validation Agent → verdict. fail이면 retry.

    Args:
        input_spec: Rule Engine 입력.
        validator: Validation Agent를 호출하는 callback. JSON 파일 경로를 받아
            ValidationVerdict를 반환.
        output_dir: 매 attempt의 JSON 파일을 저장할 디렉토리.
        max_retries: 최대 추가 시도 횟수. 기본 3 (회의 결정).

    Returns:
        ValidationLoopResult — 최종 output·verdict·시도 횟수·escalation 여부.

    Note:
        - retry 시 input_spec은 변경하지 않는다 (URS 우선 정책 일관).
        - max_retries 도달 후에도 fail이면 escalated_to_user=True로 반환만 한다.
          실제 UI 알림은 호출자가 담당.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    last_output: RuleEngineOutput | None = None
    last_verdict: ValidationVerdict | None = None

    for attempt in range(max_retries + 1):  # 첫 시도 + max_retries 추가
        last_output = run_rule_engine(input_spec)
        json_path = serialize_for_validation(
            last_output, out_dir / f"output_attempt{attempt}.json"
        )
        last_verdict = validator(json_path)
        if last_verdict.status == "pass":
            return ValidationLoopResult(
                final_output=last_output,
                final_verdict=last_verdict,
                attempts=attempt + 1,
                escalated_to_user=False,
            )
        # fail or needs_revision → 재시도. (input_spec은 그대로 — URS 우선)
        # 실제 변경은 사용자 검토 후 다음 라운드에 새 input_spec으로.

    # max_retries 도달.
    assert last_output is not None and last_verdict is not None
    return ValidationLoopResult(
        final_output=last_output,
        final_verdict=last_verdict,
        attempts=max_retries + 1,
        escalated_to_user=True,
    )


def make_stub_validator(
    *, always_pass: bool = False
) -> Callable[[Path], ValidationVerdict]:
    """테스트·개발용 stub validator.

    실제 Validation Agent가 연동되기 전까지 사용. 실제 RAG 검증 없음.
    """
    def _stub(json_path: Path) -> ValidationVerdict:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        flag_counts = data.get("meta", {}).get("stats", {}).get("flag_counts", {})
        violations = flag_counts.get("suspected_violation", 0)
        status: VerdictStatus = (
            "pass" if (always_pass or violations == 0) else "needs_revision"
        )
        return ValidationVerdict(
            status=status,
            rule_engine_input_hash=data.get("meta", {}).get("input_hash", "unknown"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            retry_count=0,
            summary=f"stub validator — suspected_violations={violations}",
        )
    return _stub
