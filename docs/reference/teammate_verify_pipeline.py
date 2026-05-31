"""verify_pipeline — 설치 후 전 구간이 정상 동작하는지 확인하는 스크립트.

비전공자도 실행 후 마지막 줄에 '모든 단계 통과'가 보이면 성공이다.

실행:
    python verify_pipeline.py
"""
from __future__ import annotations

import sys


def main() -> int:
    print("=" * 60)
    print("Biopharm Layout System — 설치 검증")
    print("=" * 60)

    # 0) 의존성 import
    try:
        import numpy        # noqa: F401
        import openpyxl     # noqa: F401
        import yaml         # noqa: F401
    except ImportError as e:
        print(f"[실패] 의존성 누락: {e}")
        print("       → pip install -r requirements.txt 를 먼저 실행하세요.")
        return 1
    print("[1/5] 의존성(numpy/openpyxl/PyYAML) ............. OK")

    # 1) URS 로드
    try:
        from rule_engine.urs_parser import load_urs_as_input, URS_PATH
        if not URS_PATH.exists():
            print(f"[실패] URS 파일이 없습니다: {URS_PATH}")
            return 1
        inp = load_urs_as_input()
    except Exception as e:
        print(f"[실패] URS 로드: {e}")
        return 1
    print(f"[2/5] URS 로드 (방 {len(inp.urs_rooms)}개, 장비 {len(inp.urs_equipment)}개) .... OK")

    # 2) Rule Engine
    try:
        from rule_engine import run_rule_engine
        out = run_rule_engine(inp)
        st = out.meta["stats"]
    except Exception as e:
        print(f"[실패] Rule Engine: {e}")
        return 1
    print(f"[3/5] Rule Engine (방 {st['rooms']} / 전실 {st['airlocks']} / 인접 {st['adjacency_edges']}) .. OK")

    # 3) RAG 검색 (실제 DB)
    try:
        from rag_interface import search
        from rag_interface.models import SearchQuery
        q = SearchQuery(
            text="cleanroom Grade B differential pressure",
            collection="regulatory_docs", top_k=3,
            calling_agent="ValidationAgent",
        )
        r = search(q)
    except Exception as e:
        print(f"[실패] RAG 검색 (DB가 RAG_DB_build/data/ 에 있는지 확인): {e}")
        return 1
    print(f"[4/5] RAG 검색 (결과 {len(r.chunks)}건, 상태 {r.status}) ......... OK")

    # 4) 전 구간 validation loop
    try:
        from rule_engine import run_with_validation_loop
        from rule_engine.validators.rag_validator import make_calibrated_rag_validator
        validator = make_calibrated_rag_validator(rag_search=search)
        res = run_with_validation_loop(
            input_spec=inp, validator=validator,
            output_dir="validation_runs_demo", max_retries=1,
        )
        v = res.final_verdict
        nconf = sum(1 for a in v.acknowledged_flags if a.verdict == "confirmed_violation")
        nrev = sum(1 for a in v.acknowledged_flags if a.verdict == "needs_user_review")
        nfalse = sum(1 for a in v.acknowledged_flags if a.verdict == "false_alarm")
    except Exception as e:
        print(f"[실패] Validation loop: {e}")
        return 1
    print(f"[5/5] 전 구간 검증 (판정 {v.status}; "
          f"확정 {nconf} / 검토 {nrev} / 오탐 {nfalse}) .. OK")

    print("=" * 60)
    print("✅ 모든 단계 통과 — 시스템이 정상 동작합니다.")
    print("   결과 파일: validation_runs_demo/verdict_final.json")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
