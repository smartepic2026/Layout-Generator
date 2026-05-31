"""Golden file helper — pytest-regressions 의 data_regression 의 축소판.

샌드박스에 pytest-regressions 설치가 불가하여 자체 구현. 회귀 비교에 필요한
최소 기능만 제공한다.

기능:
    - normalize(data): 비결정적 필드(generated_at) 제거.
    - check_against_golden(data, golden_path, force_regen=False):
        * golden 파일 없으면 새로 생성하고 PASS (최초 생성 모드)
        * 있으면 byte-level diff. 일치 → PASS, 불일치 → AssertionError(상세 diff).
        * force_regen=True 면 무조건 갱신.
    - 환경 변수 RULE_ENGINE_REGEN_GOLDEN=1 로도 강제 갱신 지원.

JSON 직렬화 규칙:
    - sort_keys=True, ensure_ascii=False, indent=2.
    - dict 키 정렬·들여쓰기 통일로 byte-level diff 의미가 있도록 함.
"""
from __future__ import annotations

import copy
import difflib
import json
import os
from pathlib import Path
from typing import Any


# 비결정적이라 마스킹할 필드 경로 (dotted path).
# meta.generated_at: 실행 시각 (매번 달라짐)
# meta 외의 비결정적 필드가 추가되면 여기 추가.
_NON_DETERMINISTIC_PATHS: tuple[tuple[str, ...], ...] = (
    ("meta", "generated_at"),
)


def normalize(data: Any) -> Any:
    """비결정적 필드를 제거한 deep copy를 반환."""
    cleaned = copy.deepcopy(data)
    for path in _NON_DETERMINISTIC_PATHS:
        _delete_nested(cleaned, path)
    return cleaned


def _delete_nested(d: Any, path: tuple[str, ...]) -> None:
    """nested dict에서 path 위치의 키를 삭제 (없으면 무시)."""
    cur = d
    for key in path[:-1]:
        if not isinstance(cur, dict) or key not in cur:
            return
        cur = cur[key]
    if isinstance(cur, dict):
        cur.pop(path[-1], None)


def _serialize(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def check_against_golden(
    data: Any,
    golden_path: Path,
    *,
    force_regen: bool = False,
) -> None:
    """data를 golden_path와 비교. 불일치 시 AssertionError.

    Args:
        data: Rule Engine 출력의 dict 형태 (output.to_dict()).
        golden_path: 정답지 JSON 파일 경로.
        force_regen: True 면 무조건 갱신. 환경변수 RULE_ENGINE_REGEN_GOLDEN=1 도 동일.

    Raises:
        AssertionError: golden 과 불일치할 때, unified diff 메시지 포함.
    """
    if os.environ.get("RULE_ENGINE_REGEN_GOLDEN") == "1":
        force_regen = True

    normalized = normalize(data)
    serialized = _serialize(normalized)

    if not golden_path.exists() or force_regen:
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(serialized + "\n", encoding="utf-8")
        return  # 최초 생성 또는 강제 갱신 — PASS 처리

    expected = golden_path.read_text(encoding="utf-8").rstrip("\n")
    actual = serialized
    if expected == actual:
        return

    diff = "\n".join(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=f"golden:{golden_path.name}",
            tofile="current_run",
            lineterm="",
            n=3,
        )
    )
    # diff가 너무 길면 앞 200줄로 잘라 보여줌.
    diff_lines = diff.splitlines()
    if len(diff_lines) > 200:
        diff = "\n".join(diff_lines[:200]) + f"\n... ({len(diff_lines)-200} more lines)"
    raise AssertionError(
        f"Golden mismatch — {golden_path}\n"
        f"갱신 의도라면: RULE_ENGINE_REGEN_GOLDEN=1 환경변수로 재실행하세요.\n"
        f"--- DIFF ---\n{diff}"
    )
