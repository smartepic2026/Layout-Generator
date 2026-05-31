"""derive — Rule Engine의 핵심 산출 모듈 3종.

룰 14·15(rule_*)와 달리, derive 모듈들은 단일 GMP 룰에 1:1 대응하지 않고
여러 룰을 종합해 새 객체를 만들어낸다. Rule Engine의 핵심 가치(보고서
v0.2 §3.2)가 이 모듈들에 모여 있다.

모듈:
    rooms_selector   — URS의 Room 리스트를 Room 객체로 통과 (룰 없음, IO만)
    adjacency        — 룰 5·6·7·8을 종합한 Room↔Room 인접 그래프 구축
                       + AirLock connects 역채움 (Doc Agent #1)
    flow_paths       — 룰 1·8을 종합한 4종 동선 산출 (엘리베이터 시작·종료)
"""
from __future__ import annotations

from .adjacency import backfill_airlock_connections, build_adjacency
from .flow_paths import derive_flow_paths
from .rooms_selector import select_required_rooms

__all__ = [
    "build_adjacency",
    "backfill_airlock_connections",
    "derive_flow_paths",
    "select_required_rooms",
]
