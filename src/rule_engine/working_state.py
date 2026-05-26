"""Internal working state for the rule engine pipeline.

Rules mutate this object in sequence; at the end the engine converts it
into a strict RuleEngineOutput.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .schemas import (
    Adjacency,
    Airlock,
    Constraints,
    FlowPaths,
    RangeMM,
    Rationale,
    Room,
    URSInput,
    Zones,
)


@dataclass
class WorkingState:
    urs: URSInput
    rooms: dict[str, Room] = field(default_factory=dict)
    airlocks: dict[str, Airlock] = field(default_factory=dict)
    adjacency: list[Adjacency] = field(default_factory=list)
    flow_paths: FlowPaths = field(default_factory=FlowPaths)
    zones: Zones = field(default_factory=Zones)
    constraints: Constraints = field(
        default_factory=lambda: Constraints(
            corridor_width_mm=RangeMM(min=1500, preferred_min=2000, preferred_max=3000, max=3000)
        )
    )
    rationale: list[Rationale] = field(default_factory=list)

    # Rule 1 — axis / direction
    axis: dict = field(default_factory=dict)
    # Cache: ordered process room ids resolved from KB process_order
    process_order_ids: list[str] = field(default_factory=list)

    def log(self, rule_id: str, target: str, decision: str, reason: str, source: str = "GMP Layout Logic_0510") -> None:
        self.rationale.append(
            Rationale(rule_id=rule_id, target=target, decision=decision, reason=reason, source=source)
        )

    def has_room(self, rid: str) -> bool:
        return rid in self.rooms

    def add_room(self, room: Room) -> None:
        self.rooms[room.id] = room

    def add_airlock(self, al: Airlock) -> None:
        self.airlocks[al.id] = al
