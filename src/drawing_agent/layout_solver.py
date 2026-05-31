"""Layout Solver v1 — 결정론적 좌표 배치.

7-block RuleEngineOutput을 입력받아 각 Room/AL/장비에 실측 mm 좌표를 부여.

기본 토폴로지 (BIG/SOM 컨셉 다이어그램 풍):

    +───── BUILDING bbox (W × D mm) ─────────────────────────────────+
    │                          NC zone (외곽 띠)                    │
    │  +──────────────────────────────────────────────────────────+ │
    │  │                   RETURN CORRIDOR (top)                  │ │
    │  │ ┌────┐┌────┐┌────┐┌────┐┌────┐ ...                      │ │
    │  │ │ALo ││ALo ││ALo ││ALo ││ALo │                          │ │
    │  │ └────┘└────┘└────┘└────┘└────┘                          │ │
    │  │ ┌────┐┌────┐┌────┐┌────┐┌────┐                          │ │
    │  │ │MEDA││BUFF││INOC││CULT││HARV│   ← Process Row (top)    │ │
    │  │ └────┘└────┘└────┘└────┘└────┘                          │ │
    │  │ ┌────┐┌────┐┌────┐┌────┐┌────┐                          │ │
    │  │ │ALin││ALin││ALin││ALin││ALin│                          │ │
    │  │ └────┘└────┘└────┘└────┘└────┘                          │ │
    │  ╠══════════════ SUPPLY CORRIDOR ═══════════════════════════╣ │
    │  │ ┌────┐┌────┐┌────┐┌────┐                                │ │
    │  │ │ALin││ALin││ALin││ALin│   (자유배치 row)                 │ │
    │  │ └────┘└────┘└────┘└────┘                                │ │
    │  │ ┌────┐┌────┐┌────┐┌────┐                                │ │
    │  │ │PUR1││PUR2││PREP││WASH│   ← Process Row (bottom)        │ │
    │  │ └────┘└────┘└────┘└────┘                                │ │
    │  │                   RETURN CORRIDOR (bottom)                │ │
    │  +──────────────────────────────────────────────────────────+ │
    │   Auxiliary zone (좌측, near material inlet)                 │
    └──────────────────────────────────────────────────────────────┘

이건 *초기 토폴로지*. RL이 이걸 시작점으로 더 좋은 배치를 학습.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.rule_engine.schemas import (
    Adjacency,
    Airlock,
    Equipment,
    Room,
    RuleEngineOutput,
)


@dataclass
class Rect:
    """좌상단 (x,y) + 폭/높이 (mm)."""
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float: return self.x + self.w / 2
    @property
    def cy(self) -> float: return self.y + self.h / 2
    @property
    def x2(self) -> float: return self.x + self.w
    @property
    def y2(self) -> float: return self.y + self.h
    @property
    def area_m2(self) -> float: return (self.w * self.h) / 1_000_000


@dataclass
class PlacedEquipment:
    equipment: Equipment
    rect: Rect


@dataclass
class PlacedRoom:
    room: Room
    rect: Rect
    equipment: list[PlacedEquipment] = field(default_factory=list)


@dataclass
class PlacedAirlock:
    airlock: Airlock
    rect: Rect
    attached_room_id: str
    side: str  # "north"|"south"|"east"|"west" (relative to attached room)


@dataclass
class PlacedDoor:
    adj: Adjacency
    x: float
    y: float
    width_mm: float
    rotation_deg: float  # 0=horizontal door, 90=vertical
    swing_to_xy: tuple[float, float] | None


@dataclass
class Layout:
    building_w_mm: float
    building_h_mm: float
    rooms: dict[str, PlacedRoom] = field(default_factory=dict)
    airlocks: dict[str, PlacedAirlock] = field(default_factory=dict)
    doors: list[PlacedDoor] = field(default_factory=list)
    annotations: list[dict] = field(default_factory=list)


# Process rows 위/아래 정의 (공정 순서 기반)
TOP_ROW = ["R_MEDIA_PREP", "R_BUFFER_PREP", "R_INOCULATION", "R_CELL_CULTURE", "R_HARVEST"]
BOTTOM_ROW = ["R_PURIFICATION_1", "R_PURIFICATION_2", "R_PREPARATION", "R_WASHING"]

# Aux zone (좌측 stripe)
AUX_LEFT_STACK = [
    "R_MATERIAL_INLET",
    "R_MATERIAL_STORAGE",
    "R_EQUIPMENT_STORAGE",
    "R_CELL_BANK_STORAGE",
    "R_DS_STORAGE",
    "R_IPC",
    "R_CIP_SUPPLY",
    "R_GOWNING_FEMALE",
    "R_GOWNING_MALE",
    "R_GOWNING_PROCESS",
    "R_WASTE_OUTLET",
    "R_AUX_CORRIDOR",
]

# NC zone (우측 stripe)
NC_RIGHT_STACK = [
    "R_LOBBY",
    "R_OFFICE",
    "R_MONITORING",
    "R_TOILET_FEMALE",
    "R_TOILET_MALE",
    "R_LOUNGE",
    "R_VISITOR_CORRIDOR",
]


def solve(spec: RuleEngineOutput, building_w_mm: float = 78500, building_h_mm: float = 42500) -> Layout:
    layout = Layout(building_w_mm=building_w_mm, building_h_mm=building_h_mm)
    room_by_id = {r.id: r for r in spec.rooms}

    # ── 영역 분할: Aux(left) + Core(center) + NC(right) ──
    aux_w = building_w_mm * 0.15
    nc_w = building_w_mm * 0.18
    core_x0 = aux_w
    core_x1 = building_w_mm - nc_w
    core_w = core_x1 - core_x0

    # ── Core 내부: 위에서부터 [return-top, AL_out row, process top, AL_in row, supply, AL_in row, process bottom, AL_out row, return-bottom] ──
    # 9개 stripe 비율 (위→아래)
    stripe_ratios = [0.06, 0.07, 0.17, 0.07, 0.10, 0.07, 0.22, 0.07, 0.10, 0.07]
    # ↑ return-top, ALo top, Process top, ALi top, supply, ALi bot, Process bot, ALo bot, return-bot, footer (NC strip)
    # normalize
    s = sum(stripe_ratios)
    stripe_ratios = [r / s for r in stripe_ratios]
    y_acc = 0.0
    bands = []
    for ratio in stripe_ratios:
        h = building_h_mm * ratio
        bands.append((y_acc, y_acc + h))
        y_acc += h
    (ret_top, alo_top, proc_top, ali_top, supply, ali_bot,
     proc_bot, alo_bot, ret_bot, footer_band) = bands

    # ── Return corridors (top + bottom) ──
    _place_corridor(layout, room_by_id, "R_RETURN_CORRIDOR",
                    core_x0, ret_top[0], core_w, ret_top[1] - ret_top[0],
                    suffix="(top)")
    _place_corridor(layout, room_by_id, "R_RETURN_CORRIDOR",
                    core_x0, ret_bot[0], core_w, ret_bot[1] - ret_bot[0],
                    suffix="(bottom)", duplicate=True)

    # ── Supply corridor (central) ──
    _place_corridor(layout, room_by_id, "R_SUPPLY_CORRIDOR",
                    core_x0, supply[0], core_w, supply[1] - supply[0])

    # ── Process rows ──
    _place_process_row(
        layout, room_by_id, TOP_ROW, core_x0, proc_top[0], core_w, proc_top[1] - proc_top[0]
    )
    _place_process_row(
        layout, room_by_id, BOTTOM_ROW, core_x0, proc_bot[0], core_w, proc_bot[1] - proc_bot[0]
    )

    # ── Airlocks (top/bottom of each process row) ──
    _place_al_row(
        layout, spec, TOP_ROW, suffix="_out",
        x0=core_x0, y0=alo_top[0], w=core_w, h=alo_top[1] - alo_top[0],
    )
    _place_al_row(
        layout, spec, TOP_ROW, suffix="_in",
        x0=core_x0, y0=ali_top[0], w=core_w, h=ali_top[1] - ali_top[0],
    )
    _place_al_row(
        layout, spec, BOTTOM_ROW, suffix="_in",
        x0=core_x0, y0=ali_bot[0], w=core_w, h=ali_bot[1] - ali_bot[0],
    )
    _place_al_row(
        layout, spec, BOTTOM_ROW, suffix="_out",
        x0=core_x0, y0=alo_bot[0], w=core_w, h=alo_bot[1] - alo_bot[0],
    )
    # 양방향(CAL) AL은 supply에 작은 spot 배치
    _place_both_way_als(layout, spec, core_x0, supply[0], core_w, supply[1] - supply[0])

    # ── Aux stack (left) ──
    _place_left_stack(layout, room_by_id, AUX_LEFT_STACK, 0, 0, aux_w, building_h_mm)

    # ── NC stack (right) ──
    _place_right_stack(layout, room_by_id, NC_RIGHT_STACK, core_x1, 0, nc_w, building_h_mm)

    # ── Equipment in each placed process Room ──
    _place_equipment_grid(layout)

    # ── Doors from adjacency ──
    _place_doors(layout, spec.adjacency)

    return layout


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _place_corridor(layout, room_by_id, rid, x, y, w, h, suffix="", duplicate=False):
    if rid not in room_by_id:
        return
    rect = Rect(x, y, w, h)
    room = room_by_id[rid]
    if duplicate:
        # 이미 배치된 corridor가 있으면 두 번째 표시는 같은 PlacedRoom의 sub-rect로
        # v1에서는 단순화: 같은 ID로 PlacedRoom만 첫 번째 유지하고 두 번째는 annotation으로
        layout.annotations.append({"type": "corridor_mirror", "id": rid, "rect": rect, "label": room.name_en + " " + suffix})
        return
    layout.rooms[rid] = PlacedRoom(room=room, rect=rect)


def _place_process_row(layout, room_by_id, row_ids, x0, y0, w, h):
    present = [r for r in row_ids if r in room_by_id]
    if not present:
        return
    # 면적 비율로 너비 분배
    areas = [room_by_id[r].area_m2 for r in present]
    total = sum(areas)
    x = x0
    for rid, a in zip(present, areas):
        w_room = w * (a / total)
        rect = Rect(x, y0, w_room, h)
        layout.rooms[rid] = PlacedRoom(room=room_by_id[rid], rect=rect)
        x += w_room


def _is_grade_b_four_al(room, all_als) -> bool:
    """C4 rule: Grade B + one-way → exactly 4 ALs (PAL_in/out + MAL_in/out)."""
    if room.clean_grade != "B":
        return False
    als = [a for a in all_als if a.connects_higher == room.id]
    return len(als) == 4


def _place_al_row(layout, spec, row_room_ids, suffix, x0, y0, w, h):
    """주어진 Process row의 각 Room에 대해 _in/_out AL을 상단/하단 stripe에 배치.
    Grade B + 4-AL Room은 좌/우 corner로 분산해 4-AL 룰 시각화 (Phase B).
    """
    for rid in row_room_ids:
        if rid not in layout.rooms:
            continue
        proom = layout.rooms[rid]
        # 이 Room에 붙은 AL 중 suffix(_in/_out) 매칭
        als = [
            al for al in spec.airlocks
            if al.connects_higher == rid and al.type.endswith(suffix)
        ]
        if not als:
            continue

        side = "north" if y0 < proom.rect.y else "south"

        # ─── Phase B: Grade B 4-AL Room — corner placement ───
        if _is_grade_b_four_al(proom.room, spec.airlocks) and len(als) == 2:
            # 2개 AL을 Room 좌측 corner와 우측 corner에 배치
            slot_w = proom.rect.w * 0.30
            # PAL은 좌측 corner, MAL은 우측 corner (personnel/material 분리 시각화)
            sorted_als = sorted(als, key=lambda a: 0 if a.type.startswith("PAL") else 1)
            for i, al in enumerate(sorted_als):
                if i == 0:  # PAL → 좌측 corner
                    ax = proom.rect.x + proom.rect.w * 0.05
                else:        # MAL → 우측 corner
                    ax = proom.rect.x + proom.rect.w * 0.65
                rect = Rect(ax, y0, slot_w, h)
                layout.airlocks[al.id] = PlacedAirlock(
                    airlock=al, rect=rect, attached_room_id=rid, side=side
                )
            continue

        # ─── 기본: 가로 균등 분할 ───
        slot_w = proom.rect.w / len(als)
        for i, al in enumerate(als):
            ax = proom.rect.x + i * slot_w + slot_w * 0.1
            aw = slot_w * 0.8
            rect = Rect(ax, y0, aw, h)
            layout.airlocks[al.id] = PlacedAirlock(
                airlock=al, rect=rect, attached_room_id=rid, side=side
            )


def _place_both_way_als(layout, spec, x0, y0, w, h):
    """양방향 CAL/PAL/MAL은 supply corridor 안쪽 빈자리에 작은 box로."""
    bw_als = [
        al for al in spec.airlocks
        if al.type in ("CAL", "PAL", "MAL")
    ]
    if not bw_als:
        return
    # supply 가운데 줄에 일렬 배치 (작게)
    slot_w = w / max(len(bw_als) + 1, 8)
    al_h = h * 0.55
    for i, al in enumerate(bw_als):
        ax = x0 + (i + 1) * slot_w - slot_w * 0.4
        ay = y0 + (h - al_h) / 2
        layout.airlocks[al.id] = PlacedAirlock(
            airlock=al,
            rect=Rect(ax, ay, slot_w * 0.8, al_h),
            attached_room_id=al.connects_higher,
            side="inline",
        )


def _place_left_stack(layout, room_by_id, ids, x, y, w, h):
    present = [r for r in ids if r in room_by_id]
    if not present:
        return
    # 면적 비율로 세로 분배
    areas = [room_by_id[r].area_m2 for r in present]
    total = sum(areas)
    yy = y
    for rid, a in zip(present, areas):
        room_h = h * (a / total)
        rect = Rect(x, yy, w, room_h)
        layout.rooms[rid] = PlacedRoom(room=room_by_id[rid], rect=rect)
        yy += room_h


def _place_right_stack(layout, room_by_id, ids, x, y, w, h):
    """NC zone — 우측 stripe."""
    present = [r for r in ids if r in room_by_id]
    if not present:
        return
    areas = [room_by_id[r].area_m2 for r in present]
    total = sum(areas)
    yy = y
    for rid, a in zip(present, areas):
        room_h = h * (a / total)
        rect = Rect(x, yy, w, room_h)
        layout.rooms[rid] = PlacedRoom(room=room_by_id[rid], rect=rect)
        yy += room_h


EQUIPMENT_VISUAL_SCALE = 0.80   # 사용자 요청: 박스 시각 표시 기본 20% 축소
                                # (실제 W_mm/D_mm 데이터는 무변경)
EQUIPMENT_MIN_SCALE = 0.25      # 자동 축소 하한 (아래로는 안 줄임)


def _pack_row_major(equips, inner_w, inner_h, scale, eq_gap):
    """row-major 로 패킹 시도. 모두 들어가면 placement 리스트 반환, 못 들어가면 None."""
    placed = []  # [(eq, rel_x, rel_y, ew, eh), ...]
    cx, cy, row_h = 0.0, 0.0, 0.0
    for eq in equips:
        ew = eq.W_mm * scale
        eh = eq.D_mm * scale
        # 한 장비가 가로폭보다 크면 이 scale 로는 불가
        if ew > inner_w:
            return None
        if cx + ew > inner_w:
            cx = 0.0
            cy += row_h + eq_gap
            row_h = 0.0
        if cy + eh > inner_h:
            return None  # 세로 초과 → scale 더 줄여야
        placed.append((eq, cx, cy, ew, eh))
        cx += ew + eq_gap
        row_h = max(row_h, eh)
    return placed


def _place_equipment_grid(layout, use_actual_mm: bool = False):
    """Room 내부에 장비를 process_step 순서대로 grid 배치.
    장비가 모두 방 안에 들어가도록 scale 을 자동 조정 (사용자 요청).

    [B-001 / D-018] `use_actual_mm=True` 면 시각 축소 (EQUIPMENT_VISUAL_SCALE)
    적용 안 하고 실제 W_mm/D_mm 사용. CP-SAT 측정 비교용. 기본은 False 로
    기존 strip-band 동작 보존 (baselines.json / B3 NNE 비교 흔들지 않게).
    """
    wall_margin = 2200    # 좌/우
    top_label = 6000      # 위쪽 — 라벨 3줄 공간
    bottom_pad = 2500     # 아래쪽
    eq_gap = 800
    base_scale = 1.0 if use_actual_mm else EQUIPMENT_VISUAL_SCALE
    min_scale = 1.0 if use_actual_mm else EQUIPMENT_MIN_SCALE
    for proom in layout.rooms.values():
        equips = list(proom.room.equipment)
        if not equips:
            continue

        inner_x = proom.rect.x + wall_margin
        inner_y = proom.rect.y + top_label
        inner_w = max(proom.rect.w - 2 * wall_margin, 1000)
        inner_h = max(proom.rect.h - top_label - bottom_pad, 1000)

        # 기본 scale 부터 시작해, 다 들어갈 때까지 점진 축소
        # use_actual_mm=True 면 scale 고정 1.0 (축소 안 함)
        scale = base_scale
        placed = None
        while scale >= min_scale:
            placed = _pack_row_major(equips, inner_w, inner_h, scale, eq_gap)
            if placed is not None:
                break
            scale *= 0.9   # 10% 씩 줄여가며 재시도
        if placed is None:
            # 하한까지 줄여도 안 들어감 → 강제로 하한 scale 로 packing(잘릴 수 있음)
            scale = min_scale
            placed = []
            cx, cy, row_h = 0.0, 0.0, 0.0
            for eq in equips:
                ew, eh = eq.W_mm * scale, eq.D_mm * scale
                if cx + ew > inner_w:
                    cx, cy, row_h = 0.0, cy + row_h + eq_gap, 0.0
                placed.append((eq, cx, cy, ew, eh))
                cx += ew + eq_gap
                row_h = max(row_h, eh)

        for eq, rx, ry, ew, eh in placed:
            proom.equipment.append(
                PlacedEquipment(eq, Rect(inner_x + rx, inner_y + ry, ew, eh))
            )


def _pressure_of(layout, node_id: str) -> float:
    """Room/AL의 differential_pressure_Pa. 못 찾으면 0."""
    if node_id in layout.rooms:
        return layout.rooms[node_id].room.differential_pressure_Pa
    if node_id in layout.airlocks:
        return layout.airlocks[node_id].airlock.differential_pressure_Pa
    return 0.0


def _resolve_swing(layout, adj: Adjacency) -> tuple[Optional[str], list[dict]]:
    """C10 룰: 도어는 차압 흐름 방향(= 낮은 압력 쪽)으로 열림.

    1. adj.door_swing_to 가 있으면 그대로 사용
    2. 없으면 from/to Room의 차압 차이로 fallback (높은 → 낮은 쪽으로 swing)
    3. 둘 다 같으면 None + annotation 경고
    """
    annotations = []
    if adj.door_swing_to:
        return adj.door_swing_to, annotations

    p_from = _pressure_of(layout, adj.from_id)
    p_to = _pressure_of(layout, adj.to_id)
    if abs(p_from - p_to) < 1e-6:
        annotations.append({
            "type": "door_swing_ambiguous",
            "edge": f"{adj.from_id}↔{adj.to_id}",
            "reason": f"equal pressure ({p_from}Pa) — C10 cannot resolve",
        })
        return None, annotations
    # 차압이 큰 쪽이 → 낮은 쪽으로 도어가 열림
    lower_id = adj.to_id if p_from > p_to else adj.from_id
    return lower_id, annotations


def _place_doors(layout, adjacency: list[Adjacency]):
    """Adjacency 기반으로 도어 위치 + C10 차압 기반 swing 방향 결정 (Phase C)."""
    for adj in adjacency:
        if adj.relationship == "passthrough_only":
            continue  # passthrough는 도어 아님

        a = _lookup_rect(layout, adj.from_id)
        b = _lookup_rect(layout, adj.to_id)
        if a is None or b is None:
            continue

        # 공유 변 추정
        x, y, rot = _door_pos(a, b)

        # Phase C: swing 방향 결정 (adj.door_swing_to → 차압 fallback → 모호 경고)
        swing_target_id, warnings = _resolve_swing(layout, adj)
        layout.annotations.extend(warnings)
        swing_xy = None
        if swing_target_id:
            target = _lookup_rect(layout, swing_target_id)
            if target:
                swing_xy = (target.cx, target.cy)

        layout.doors.append(
            PlacedDoor(
                adj=adj,
                x=x,
                y=y,
                width_mm=adj.door_size_mm,
                rotation_deg=rot,
                swing_to_xy=swing_xy,
            )
        )


def _lookup_rect(layout, node_id) -> Optional[Rect]:
    if node_id in layout.rooms:
        return layout.rooms[node_id].rect
    if node_id in layout.airlocks:
        return layout.airlocks[node_id].rect
    return None


def _door_pos(a: Rect, b: Rect) -> tuple[float, float, float]:
    """두 사각형 사이의 도어 위치 + 회전. 0=수평, 90=수직."""
    # 세로 인접 (a 위, b 아래 또는 반대)
    if abs(a.y2 - b.y) < 50 or abs(b.y2 - a.y) < 50:
        y = (a.y2 + b.y) / 2 if a.y < b.y else (b.y2 + a.y) / 2
        x = max(a.x, b.x) + min(a.x2, b.x2) - max(a.x, b.x)
        x = (max(a.x, b.x) + min(a.x2, b.x2)) / 2
        return x, y, 0
    # 가로 인접
    if abs(a.x2 - b.x) < 50 or abs(b.x2 - a.x) < 50:
        x = (a.x2 + b.x) / 2 if a.x < b.x else (b.x2 + a.x) / 2
        y = (max(a.y, b.y) + min(a.y2, b.y2)) / 2
        return x, y, 90
    # 겹침/포함/원격 — 중심 사이 중간점 fallback
    return (a.cx + b.cx) / 2, (a.cy + b.cy) / 2, 0
