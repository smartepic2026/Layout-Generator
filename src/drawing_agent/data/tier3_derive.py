"""Tier 3 — 기존 필드에서 derive 규칙으로 파생.

source 태그: "tier3_derive"

처리 필드:
  - sort_order      ← **D-007**: product_process_order 기반 (1차)
                       + process_no 정규식 (2차, 팀원이 채우면 자동 우선)
  - bbox_m          ← (W_mm, D_mm) → [w_m, d_m]
  - connects_to     ← same-room chain 만 (cross-room 은 Phase B)
  - co_locate_group ← **D-007 신규**: 같은 방 안 장비는 같은 그룹 라벨.
                       "GRP_{phase}_{room_id}" 형식. 같은 방 안에서 병렬
                       공정으로 묶이는 신호. cluster·CP-SAT 그룹 제약에 사용.

D-007 sort_order derive 우선순위:
  1. tier1 이 이미 채움 (rule_engine 출력에 sort_order 있으면)
  2. eq.process_no 파싱 ("P1-2" → 12) — 팀원이 process_no 값을 채워주면
  3. product_process_order (flow_paths) 기반 — 팀원 출력에 명시된 공정순서
     를 1차 신호로. eq 의 room_id 인덱스 * 100 + 같은 방 내 instance 순서
"""
from __future__ import annotations

import re
from typing import Optional

from src.contract.schemas import RuleEngineOutput

TIER_NAME = "tier3_derive"


# process_no 포맷: "P{phase}-{seq}" → sort_order = phase * 10 + seq
_STEP_RE = re.compile(r"P?(\d+)[\-_\.](\d+)")
_FALLBACK_INT = re.compile(r"\d+")


def parse_sort_order(process_no: Optional[str]) -> Optional[int]:
    """'P1-2' → 12, 'P10-3' → 103, 'USP-30' → 30, None/'' → None.

    phase * 10 + seq 가정. 현재 데이터 (P1~P7, 각 phase 5개 이하) 에 안전.
    한 phase 에 10개 이상 장비가 들어오면 sort_order 충돌 발생 가능 →
    그땐 phase * 100 + seq 로 폭 확장.
    """
    if not process_no:
        return None
    m = _STEP_RE.match(process_no)
    if m:
        phase, seq = int(m.group(1)), int(m.group(2))
        return phase * 10 + seq
    m2 = _FALLBACK_INT.search(process_no)
    return int(m2.group()) if m2 else None


def derive_bbox_m(w_mm: int, d_mm: int) -> list[float]:
    """W_mm/D_mm → [width_m, depth_m]. mm → m 환산."""
    return [round(w_mm / 1000.0, 3), round(d_mm / 1000.0, 3)]


def try_fill(spec: RuleEngineOutput, tracker, field_name: str) -> None:
    """tier1/2 가 못 채운 필드를 derive."""
    if field_name == "sort_order":
        _fill_sort_order(spec, tracker)
    elif field_name == "bbox_m":
        _fill_bbox_m(spec, tracker)
    elif field_name == "connects_to":
        _fill_connects_to_same_room(spec, tracker)
    elif field_name == "co_locate_group":
        _fill_co_locate_group(spec, tracker)
    # 그 외 필드는 tier3 가 다루지 않음 → tier4 로 위임


def _ppo_room_rank(spec: RuleEngineOutput) -> dict[str, int]:
    """product_process_order (flow_paths.product_process_order) → room_id → rank.

    D-007: 팀원이 명시한 공정순서를 신뢰가능한 1차 신호로 사용.
    예: [MEDIA_PREP, BUFFER_PREP, INOCULATION, CELL_CULTURE, HARVEST, PURIF_1, PURIF_2]
        → {MEDIA_PREP:1, BUFFER_PREP:2, ..., PURIF_2:7}
    """
    return {rid: i + 1 for i, rid in enumerate(spec.flow_paths.product_process_order)}


def _full_room_rank(spec: RuleEngineOutput) -> dict[str, int]:
    """PPO + 보조 방 모두 rank 부여. PPO 안은 1~N, 밖은 N+1, N+2, ... 등장순서.

    sort_order 와 co_locate_group 두 함수가 공유하는 rank 소스. 모든 방이
    rank 를 받아 None 가드 단순화.
    """
    ppo_rank = _ppo_room_rank(spec)
    next_rank = (max(ppo_rank.values()) if ppo_rank else 0) + 1
    full = dict(ppo_rank)
    for room in spec.rooms:
        if room.id not in full and room.equipment:
            full[room.id] = next_rank
            next_rank += 1
    return full


def _fill_sort_order(spec: RuleEngineOutput, tracker) -> None:
    """sort_order 우선순위 (D-007):
      A) tier1 이 이미 채운 값 (rule_engine 출력) → 보존
      B) eq.process_no 파싱 ("P1-2" → 12) — 팀원이 process_no 채워주면 우선
      C) product_process_order 기반 derive — 팀원 출력 §4 의 공정순서로 폴백
      D) PPO 에 없는 보조방 (Autoclave/Freezer/CIP 등) — PPO rank 다음부터
         spec.rooms 등장 순서대로 rank 부여. 공정 흐름 밖이지만 sort_order
         자체는 모두 부여해 P1 단조성 계산 시 None 가드 단순화.

    rank * 100 + (방내 instance idx + 1) 식 — 방내 99 장비 미만 가정.
    """
    from src.drawing_agent.data.adapter import is_field_filled

    ppo_rank = _full_room_rank(spec)  # 모든 방 (PPO + 보조) rank 부여

    for room in spec.rooms:
        room_rank = ppo_rank.get(room.id)
        for idx, eq in enumerate(room.equipment):
            if is_field_filled(eq, "sort_order"):
                continue  # tier1 우선
            # B) process_no 파싱 시도
            so = parse_sort_order(eq.process_no)
            if so is not None:
                eq.sort_order = so
                tracker.record(room.id, idx, "sort_order", TIER_NAME)
                continue
            # C/D) PPO 기반 (PPO 안 방은 1~N rank, 밖 방은 N+1, N+2, ...)
            if room_rank is not None:
                eq.sort_order = room_rank * 100 + idx + 1
                tracker.record(room.id, idx, "sort_order", TIER_NAME)


def _fill_co_locate_group(spec: RuleEngineOutput, tracker) -> None:
    """같은 방 안 장비는 같은 그룹 라벨. CP-SAT 의 group constraint 입력으로.

    형식: "GRP_{rank:02d}_{room_id}". sort_order 와 같은 rank 소스
    (_full_room_rank) 사용 → PPO 안/밖 일관된 라벨.
    """
    from src.drawing_agent.data.adapter import is_field_filled

    ppo_rank = _full_room_rank(spec)
    for room in spec.rooms:
        rank = ppo_rank.get(room.id)
        if rank is None:
            continue  # 빈 방 (equipment 없는 방) — skip
        label = f"GRP_{rank:02d}_{room.id}"
        for idx, eq in enumerate(room.equipment):
            if is_field_filled(eq, "co_locate_group"):
                continue
            eq.co_locate_group = label
            tracker.record(room.id, idx, "co_locate_group", TIER_NAME)


def _fill_bbox_m(spec: RuleEngineOutput, tracker) -> None:
    from src.drawing_agent.data.adapter import is_field_filled
    for room in spec.rooms:
        for idx, eq in enumerate(room.equipment):
            if is_field_filled(eq, "bbox_m"):
                continue
            eq.bbox_m = derive_bbox_m(eq.W_mm, eq.D_mm)
            tracker.record(room.id, idx, "bbox_m", TIER_NAME)


def _fill_connects_to_same_room(spec: RuleEngineOutput, tracker) -> None:
    """같은 방 내 sort_order 인접 chain. cross-room 은 의도적으로 안 함.

    전제: sort_order 가 이미 채워져 있어야 함 (호출 순서상 OK — fields
    리스트의 sort_order 가 connects_to 보다 앞).
    """
    from src.drawing_agent.data.adapter import is_field_filled
    for room in spec.rooms:
        sorted_eq_with_idx = sorted(
            [(idx, eq) for idx, eq in enumerate(room.equipment) if eq.sort_order is not None],
            key=lambda t: t[1].sort_order,
        )
        for k in range(len(sorted_eq_with_idx) - 1):
            idx, eq = sorted_eq_with_idx[k]
            _, next_eq = sorted_eq_with_idx[k + 1]
            if is_field_filled(eq, "connects_to"):
                continue
            eq.connects_to.append(next_eq.name)
            tracker.record(room.id, idx, "connects_to", TIER_NAME)
