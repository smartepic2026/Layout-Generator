"""End-to-end 데모 — 실제 URS + 실제 RAG search + RAG validator + retry loop.

2026-05-29 갱신: `rag_interface.search.search` 가 구현되어 mock 을 실제 검색으로
교체했다. percentile calibration 으로 TF-IDF 분포에 맞는 threshold 를 자동 산정
(make_calibrated_rag_validator).

실행:
    python3 -m rule_engine._demo_validation_run

확인 포인트:
    - validation_runs_demo/ 에 output_attemptN.json + verdict_final.json 생성.
    - retry 횟수·escalation 여부·acknowledged_flags 요약·per-rule 분포 콘솔 출력.
    - input_spec 은 attempt 사이에 변경되지 않음 (URS 우선 정책).
    - calibrated threshold 값 출력.
"""
from __future__ import annotations

import sys
from pathlib import Path

from src.rag_interface import search

from src.rule_engine import (
    deserialize_verdict,
    make_stub_validator,
    run_with_validation_loop,
)
from src.rule_engine.urs_parser import (
    URS_PATH,
    build_rule_engine_input,
    parse_urs_xlsx,
)
from src.rule_engine.validation_interface import ValidationVerdict
from src.rule_engine.validators import RagValidatorConfig
from src.rule_engine.validators.rag_validator import (
    calibrate_thresholds,
    make_calibrated_rag_validator,
)


def _summarize_verdict(v: ValidationVerdict) -> None:
    n = len(v.acknowledged_flags)
    n_conf = sum(1 for a in v.acknowledged_flags if a.verdict == "confirmed_violation")
    n_rev = sum(1 for a in v.acknowledged_flags if a.verdict == "needs_user_review")
    n_false = sum(1 for a in v.acknowledged_flags if a.verdict == "false_alarm")
    print(f"  status                  : {v.status}")
    print(f"  rule_engine_input_hash  : {v.rule_engine_input_hash}")
    print(f"  acknowledged_flags      : {n}  "
          f"(confirmed={n_conf}, review={n_rev}, false={n_false})")
    print(f"  new_violations          : {len(v.new_violations)}")
    print(f"  summary                 : {v.summary}")

    by_rule: dict[str, dict[str, int]] = {}
    for a in v.acknowledged_flags:
        slot = by_rule.setdefault(a.rule_id, {"confirmed": 0, "review": 0, "false": 0})
        if a.verdict == "confirmed_violation":
            slot["confirmed"] += 1
        elif a.verdict == "needs_user_review":
            slot["review"] += 1
        else:
            slot["false"] += 1
    if by_rule:
        print("\n  [Per-rule verdict 분포]")
        print(f"  {'rule_id':<28} {'conf':>5} {'rev':>5} {'false':>6}")
        for rid in sorted(by_rule):
            s = by_rule[rid]
            print(f"  {rid:<28} {s['confirmed']:>5d} {s['review']:>5d} {s['false']:>6d}")

    # confirmed/review 의 첫 citation 샘플 (실제 RAG 인용 확인용).
    cited = [a for a in v.acknowledged_flags if a.rag_citations][:3]
    if cited:
        print("\n  [RAG citation 샘플]")
        for a in cited:
            print(f"  {a.rule_id} [{a.verdict}] → {a.rag_citations[0]}")


def main() -> int:
    if not URS_PATH.exists():
        print(f"ERROR: URS 파일 없음 — {URS_PATH}", file=sys.stderr)
        return 1

    urs_rooms, urs_equipment, building_info = parse_urs_xlsx(URS_PATH)
    print(f"URS 파싱: rooms={len(urs_rooms)}, equipment={len(urs_equipment)}")
    input_spec = build_rule_engine_input(urs_rooms, urs_equipment, building_info)

    # 세션 독립 경로 — 레포 루트의 validation_runs_demo/ (gitignore 대상).
    out_dir = Path(__file__).resolve().parents[1] / "validation_runs_demo"
    out_dir.mkdir(parents=True, exist_ok=True)

    # threshold calibration (실제 RAG DB 분포 기준).
    high, medium = calibrate_thresholds(search, high_percentile=95.0, medium_percentile=80.0)
    print(f"\n[Calibration] 실제 RAG DB 분포 → high={high:.4f}, medium={medium:.4f}")

    print("\n" + "=" * 78)
    print("Validation Loop — 실제 RAG search + calibrated threshold × max_retries=2")
    print("=" * 78)

    validator = make_calibrated_rag_validator(
        rag_search=search,
        base_config=RagValidatorConfig(top_k=5),
        high_percentile=95.0,
        medium_percentile=80.0,
    )

    result = run_with_validation_loop(
        input_spec=input_spec,
        validator=validator,
        output_dir=out_dir,
        max_retries=2,
    )

    print(f"\n[Loop result]")
    print(f"  attempts            : {result.attempts}")
    print(f"  escalated_to_user   : {result.escalated_to_user}")
    print(f"\n[Final verdict]")
    _summarize_verdict(result.final_verdict)

    verdict_path = out_dir / "verdict_final.json"
    verdict_path.write_text(result.final_verdict.to_json(), encoding="utf-8")
    rt = deserialize_verdict(verdict_path)
    assert rt.status == result.final_verdict.status
    print(f"\n  verdict_final.json schema round-trip OK → {verdict_path}")

    files = sorted(out_dir.glob("output_attempt*.json"))
    print(f"  attempt JSON files written: {len(files)}")

    print("\n[Stub validator 비교 — 동일 input 으로 always_pass=False]")
    stub_result = run_with_validation_loop(
        input_spec=input_spec,
        validator=make_stub_validator(always_pass=False),
        output_dir=out_dir / "stub_compare",
        max_retries=0,
    )
    print(f"  stub status         : {stub_result.final_verdict.status}")
    print(f"  stub summary        : {stub_result.final_verdict.summary}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
