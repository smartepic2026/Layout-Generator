"""L3 Golden file test — 실제 URS xlsx로 회귀 잠금.

한 줄 요약:
    실제 URS_ConceptualDesign for layout_0516.xlsx 로 run_rule_engine 을 돌린
    결과 JSON 을 정답지로 박제. 이후 코드 변경 시 출력이 달라지면 즉시 fail.

골든 파일 위치:
    rule_engine/tests/golden/real_urs_baseline.json

박제 시점 baseline (2026-05-29, Doc Agent #1·#4·#5 반영 후 재박제):
    rooms             : 48
    airlocks          : 18
    adjacency_edges   : 27   (#4: Cell Culture 전실 4개 매칭 성공으로 23→27)
    rationale_entries : 399
    flag_counts       : info=3, suspected_violation=21  (warning 0건)
    └─ suspected_violation 19건은 rule_03_room_size (URS J 컬럼 미입력 →
       KB/Algorithm B fallback). 사용자가 비율을 채우면 줄어듦 — 의도된 변경.
    └─ #4 이름 strip 으로 trailing-space 매칭 실패 warning 4건 제거.
    └─ #1 airlock connects_higher_room 18/18 역채움 (connects_lower 는
       corridor 측이라 Room 모델에 없어 None).
    └─ #5 room_id R_MATEIAL_IN→R_MATERIAL_IN, 장비명/용량 표기 URS 원천 정정.

갱신 방법:
    RULE_ENGINE_REGEN_GOLDEN=1 python3 -m rule_engine.tests._minirunner

설계 원칙 (노션 페이지 §3·§5):
    - golden = "이상적 정답"이 아니라 "현재 합의된 출력 기준선".
    - 의도된 변경은 환경변수로 갱신 + 코드 리뷰에서 diff 검토.
    - meta.generated_at 같은 비결정적 필드는 _golden_helper.normalize() 가 제거.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.rule_engine import run_rule_engine
from src.rule_engine.urs_parser import (
    URS_PATH,
    build_rule_engine_input as _make_input,
    parse_urs_xlsx as _parse_urs,
)
from src.rule_engine.tests._golden_helper import check_against_golden


_GOLDEN_PATH = Path(__file__).parent / "golden" / "real_urs_baseline.json"


def test_real_urs_golden_baseline():
    """실제 URS → run_rule_engine → 출력 JSON 이 정답지와 일치해야 함."""
    if not URS_PATH.exists():
        return  # URS 파일이 없는 환경에서는 skip
    urs_rooms, urs_equipment, building_info = _parse_urs(URS_PATH)
    input_spec = _make_input(urs_rooms, urs_equipment, building_info)
    output = run_rule_engine(input_spec)
    check_against_golden(output.to_dict(), _GOLDEN_PATH)


def test_golden_baseline_file_exists():
    """golden 파일이 박제 후에는 반드시 존재해야 함."""
    if not URS_PATH.exists():
        return
    assert _GOLDEN_PATH.exists(), (
        f"Golden 파일이 없습니다: {_GOLDEN_PATH}. "
        f"최초 생성: test_real_urs_golden_baseline 을 한 번 실행."
    )


# 박제 시점 baseline 수치 — 변경 시 의도적 재박제 필요.
# 2026-05-29 재박제 (Doc Agent #1·#4·#5 반영):
#   - #4 이름 strip → Cell Culture 전실 4개 adjacency 매칭 성공
#     (warning 4→0, adjacency 23→27, suspected_violation 20→21: 전실들이
#      면적-추정-불가 대상에 정확히 포함됨 — URS J열 미입력 기존 현상)
#   - #1 airlock connects_higher 역채움 (18/18)
#   - #5 room_id R_MATEIAL_IN → R_MATERIAL_IN, 장비명 오타·용량 표기 정정
_BASELINE_ROOMS = 48
_BASELINE_AIRLOCKS = 18
_BASELINE_ADJACENCY = 27
_BASELINE_FLAGS = {"info": 3, "suspected_violation": 21}


def test_golden_baseline_stats():
    """박제 시점의 핵심 통계가 보존되었는지 사람 읽기 좋은 형태로 검증.

    바이트 단위 비교(test_real_urs_golden_baseline)와 중복이지만, 통계만
    어긋날 때 실패 메시지가 더 명확하다.
    """
    if not _GOLDEN_PATH.exists():
        return
    data = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    stats = data["meta"]["stats"]
    assert stats["rooms"] == _BASELINE_ROOMS, (
        f"rooms baseline={_BASELINE_ROOMS}, golden={stats['rooms']}"
    )
    assert stats["airlocks"] == _BASELINE_AIRLOCKS, (
        f"airlocks baseline={_BASELINE_AIRLOCKS}, golden={stats['airlocks']}"
    )
    assert stats["adjacency_edges"] == _BASELINE_ADJACENCY, (
        f"adjacency_edges baseline={_BASELINE_ADJACENCY}, golden={stats['adjacency_edges']}"
    )
    assert stats["flag_counts"] == _BASELINE_FLAGS, (
        f"flag_counts baseline={_BASELINE_FLAGS}, golden={stats['flag_counts']}"
    )
