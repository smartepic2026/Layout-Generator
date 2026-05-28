"""4-tier adapter orchestrator.

각 tier 가 try_fill() 을 노출하고, adapter 가 tier1 → tier2 → tier3 → tier4
순서로 호출. 값이 채워질 때마다 SourceTracker 에 (room_id, eq_idx, field) →
tier_name 매핑을 기록.

A1 (이번 phase) 에서 처리하는 필드:
  - sort_order
  - bbox_m
  - connects_to (same-room chain 만; cross-room 은 Phase B)

이번 phase 에서는 tier2 (URS) / tier4 (manual_stub) 은 호출하지만 실질적으로
빈 stub. process_step 같은 장비-level 데이터는 URS 정책 JSON 에 들어가지
않고, manual_stub 은 P2 수식 만들 때(Phase B) cross-room link 채우기 시작.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from src.drawing_agent.data import (
    tier1_ruleengine,
    tier2_urs,
    tier3_derive,
    tier4_manual_stub,
)
from src.rule_engine.schemas import RuleEngineOutput

# A1 에서 channel 화 할 필드 목록. (B 이후 확장 시 여기 추가)
A1_FIELDS = ("sort_order", "bbox_m", "connects_to")


@dataclass
class SourceTracker:
    """필드별 source 태그 저장소.

    key 형식: f"{room_id}::{eq_idx}::{field_name}"  (또는 room-level 필드는 eq_idx 생략)
    value: tier 이름 (예: "tier1_ruleengine", "tier3_derive")
    """
    sources: dict[str, str] = field(default_factory=dict)
    # tier 별 채워진 (field, count) 통계 — 보고용
    per_tier_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    def record(self, room_id: str, eq_idx: int, field_name: str, tier: str) -> None:
        key = f"{room_id}::{eq_idx}::{field_name}"
        self.sources[key] = tier
        self.per_tier_stats.setdefault(tier, {}).setdefault(field_name, 0)
        self.per_tier_stats[tier][field_name] += 1

    def get(self, room_id: str, eq_idx: int, field_name: str) -> Optional[str]:
        return self.sources.get(f"{room_id}::{eq_idx}::{field_name}")

    def to_json(self) -> str:
        return json.dumps(
            {"sources": self.sources, "per_tier_stats": self.per_tier_stats},
            indent=2,
            ensure_ascii=False,
        )

    def summary(self) -> str:
        """사람용 한 줄 요약: tier 별 채움 카운트."""
        parts = []
        for tier in sorted(self.per_tier_stats.keys()):
            stat = self.per_tier_stats[tier]
            total = sum(stat.values())
            detail = ", ".join(f"{k}={v}" for k, v in sorted(stat.items()))
            parts.append(f"{tier}: {total} ({detail})")
        return " | ".join(parts) if parts else "(no fields enriched)"


def enrich_spec(
    spec: RuleEngineOutput,
    urs_path: Optional[str] = None,
    fields: tuple[str, ...] = A1_FIELDS,
) -> SourceTracker:
    """spec 을 in-place enrich. 모든 tier 를 순서대로 시도.

    Args:
        spec: RuleEngineOutput (in-place 수정됨)
        urs_path: tier2 가 참조할 URS JSON 경로 (옵션 — 없으면 tier2 skip)
        fields: 이번 호출에서 채울 필드 목록 (기본 A1_FIELDS)

    Returns:
        SourceTracker — 어떤 tier 가 어떤 필드를 채웠는지 추적
    """
    tracker = SourceTracker()

    for field_name in fields:
        # tier 1: RuleEngineOutput 자체에 이미 값이 있나
        tier1_ruleengine.try_fill(spec, tracker, field_name)
        # tier 2: URS scenario JSON 에 값이 있나
        if urs_path:
            tier2_urs.try_fill(spec, tracker, field_name, urs_path)
        # tier 3: derive 규칙으로 파생 가능한가
        tier3_derive.try_fill(spec, tracker, field_name)
        # tier 4: drawing_agent/kb/ 의 수기 보충
        tier4_manual_stub.try_fill(spec, tracker, field_name)

    return tracker


def is_field_filled(eq, field_name: str) -> bool:
    """장비의 해당 필드가 이미 의미있는 값을 가지고 있는지.

    None 또는 빈 컨테이너는 미채움으로 간주. False/0/"" 는 채워진 것으로 봄.
    """
    val = getattr(eq, field_name, None)
    if val is None:
        return False
    if isinstance(val, (list, dict, str)) and len(val) == 0:
        return False
    return True
