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

from src.contract.schemas import (
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


# Process rows 위/아래 정의 (공정 순서 기반) — 우리 default URS 호환용 하드코딩.
# 팀원 룰엔진 같은 외부 출력은 dynamic_rooms=True 로 호출해 동적 분류 사용.
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


# ══════════════════════════════════════════════════════════════════════
# 2026-05-31: 동적 방 분류 (팀원 새 룰엔진 흡수)
# ══════════════════════════════════════════════════════════════════════
import re as _re_dyn

# AL 이중 표현 패턴 — 팀원이 rooms[] 안에 별도 fake room 으로 모델링한 AL.
# (e.g. R_PAL_IN_HARVEST, R_MAL_OUT_PURIFICATION_1, R_CAL_IN_INOCULATION).
# area_m2=0 + 이 패턴이면 layout 에 그리지 않음 (이미 airlocks[] 에 metadata 있음).
_AL_FAKE_ROOM_PATTERN = _re_dyn.compile(r"^R_(?:P|M|C)AL_(?:IN|OUT)_")


def _is_al_fake_room(room) -> bool:
    """AL 이중 표현 fake room 인지. D-003 시점 보류했던 이슈 (2026-05-31)."""
    if _AL_FAKE_ROOM_PATTERN.match(room.id) and room.area_m2 == 0:
        return True
    return False


def _classify_rooms_dynamic(spec: RuleEngineOutput) -> dict:
    """spec.rooms 를 process/aux/nc/corridor 로 동적 분류 (하드코딩 리스트 무시).

    PPO (product_process_order) 가 있으면 process 방은 PPO 순서대로 정렬, 나머지
    process 는 뒤에 붙음. process 가 많으면 top/bottom 2개 row 로 나눔.

    Returns: dict with keys 'top_row', 'bottom_row', 'aux_left', 'nc_right',
             'corridors', 'skipped' (= AL fake rooms).
    """
    by_id = {r.id: r for r in spec.rooms}
    skipped: list[str] = []
    process_ids: list[str] = []
    aux_ids: list[str] = []
    nc_ids: list[str] = []
    corridors: list[str] = []
    # corridor 판별 — is_corridor 필드 + id 패턴 fallback (팀원 spec 호환).
    # `_CORRIDOR` 가 들어간 id 만 잡음 (R_SUPPLY_CORRIDOR, R_RETURN_CORRIDOR,
    # R_CORRIDOR, R_CORRIDOR_VISITOR). R_CIP_SUPPLY 등 SUPPLY 단어 다른 의미는 제외.
    # 단 SUPPLY/RETURN corridor 만 main stripe 로, 나머지 corridor 는 aux/nc 로 흡수.
    _CORRIDOR_ID_PATTERN = _re_dyn.compile(r"_CORRIDOR(?:_|$)", _re_dyn.IGNORECASE)
    _MAIN_CORRIDOR_PATTERN = _re_dyn.compile(r"_(?:SUPPLY|RETURN)_CORRIDOR", _re_dyn.IGNORECASE)
    for r in spec.rooms:
        if _is_al_fake_room(r):
            skipped.append(r.id)
            continue
        if r.is_corridor or _CORRIDOR_ID_PATTERN.search(r.id):
            if _MAIN_CORRIDOR_PATTERN.search(r.id):
                corridors.append(r.id)  # SUPPLY/RETURN — strip-band 중심 stripe
            elif r.category == "NC" or r.clean_grade == "NC":
                nc_ids.append(r.id)     # R_CORRIDOR_VISITOR → NC stripe
            else:
                aux_ids.append(r.id)    # R_CORRIDOR (auxiliary) → aux stripe
            continue
        if r.category == "NC" or r.clean_grade == "NC":
            nc_ids.append(r.id)
        elif r.category == "auxiliary":
            aux_ids.append(r.id)
        else:  # process (또는 default)
            process_ids.append(r.id)

    # process 정렬: PPO 순서 우선 + 나머지 area_m2 내림차순
    ppo = list(getattr(spec.flow_paths, "product_process_order", []) or [])
    seen = set()
    sorted_proc: list[str] = []
    for rid in ppo:
        if rid in process_ids and rid not in seen:
            sorted_proc.append(rid)
            seen.add(rid)
    extras = [rid for rid in process_ids if rid not in seen]
    extras.sort(key=lambda rid: -by_id[rid].area_m2)
    sorted_proc.extend(extras)

    # process 가 많으면 top/bottom 으로 균등 분할. area_m2 합 기준 balance.
    if len(sorted_proc) <= 6:
        top_row = sorted_proc
        bottom_row = []
    else:
        half = (len(sorted_proc) + 1) // 2
        top_row = sorted_proc[:half]
        bottom_row = sorted_proc[half:]

    return {
        "top_row": top_row,
        "bottom_row": bottom_row,
        "aux_left": aux_ids,
        "nc_right": nc_ids,
        "corridors": corridors,
        "skipped": skipped,
    }


def _auto_canvas_for_rooms(spec: RuleEngineOutput, base_w: float, base_h: float) -> tuple[float, float]:
    """방 area 합 기준 캔버스 자동 키움. base 면적의 60% 넘으면 비례 확대."""
    total_area_m2 = sum(
        r.area_m2 for r in spec.rooms if r.area_m2 > 0 and not _is_al_fake_room(r)
    )
    base_area_m2 = base_w * base_h / 1e6
    target_fill = 0.55  # 캔버스의 55% 가 방 면적 (나머지 통로/여백)
    if total_area_m2 <= base_area_m2 * target_fill:
        return base_w, base_h
    scale = (total_area_m2 / (base_area_m2 * target_fill)) ** 0.5
    return base_w * scale, base_h * scale


def solve(
    spec: RuleEngineOutput,
    building_w_mm: float = 78500,
    building_h_mm: float = 42500,
    dynamic_rooms: bool = False,
    auto_canvas: bool = False,
) -> Layout:
    """strip-band 결정론적 배치 솔버.

    Args:
        dynamic_rooms: True 면 하드코딩 TOP_ROW/BOTTOM_ROW/AUX_LEFT/NC_RIGHT 무시,
                       spec.rooms 의 category/zone/is_corridor 로 동적 분류.
                       팀원 새 룰엔진 등 외부 spec 흡수용 (2026-05-31).
        auto_canvas: True 면 spec 의 방 면적 합 기준 캔버스 자동 키움.
    """
    if auto_canvas:
        building_w_mm, building_h_mm = _auto_canvas_for_rooms(
            spec, building_w_mm, building_h_mm
        )

    if dynamic_rooms:
        cls = _classify_rooms_dynamic(spec)
        top_row_ids = cls["top_row"]
        bottom_row_ids = cls["bottom_row"]
        aux_left_ids = cls["aux_left"]
        nc_right_ids = cls["nc_right"]
    else:
        top_row_ids = TOP_ROW
        bottom_row_ids = BOTTOM_ROW
        aux_left_ids = AUX_LEFT_STACK
        nc_right_ids = NC_RIGHT_STACK

    layout = Layout(building_w_mm=building_w_mm, building_h_mm=building_h_mm)
    room_by_id = {r.id: r for r in spec.rooms}

    # ── 영역 분할: Aux(left) + Core(center) + NC(right) ──
    aux_w = building_w_mm * 0.15
    nc_w = building_w_mm * 0.18
    core_x0 = aux_w
    core_x1 = building_w_mm - nc_w
    core_w = core_x1 - core_x0

    # ── Core 내부: 5개 stripe (위→아래). [2026-06-02 v2] 에어록 밴드 제거 —
    # 에어록을 방 *안쪽 가장자리*에 배치해 흰공간 제거 + 참조 도면 구조 일치.
    #   return-top, Process top, Supply corridor(중앙), Process bottom, return-bottom
    stripe_ratios = [0.05, 0.38, 0.12, 0.40, 0.05]
    s = sum(stripe_ratios)
    stripe_ratios = [r / s for r in stripe_ratios]
    y_acc = 0.0
    bands = []
    for ratio in stripe_ratios:
        h = building_h_mm * ratio
        bands.append((y_acc, y_acc + h))
        y_acc += h
    (ret_top, proc_top, supply, proc_bot, ret_bot) = bands

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

    # ── Process rows (full band height) ──
    _place_process_row(
        layout, room_by_id, top_row_ids, core_x0, proc_top[0], core_w, proc_top[1] - proc_top[0]
    )
    _place_process_row(
        layout, room_by_id, bottom_row_ids, core_x0, proc_bot[0], core_w, proc_bot[1] - proc_bot[0]
    )

    # ── Airlocks INSIDE each process room (supply-facing=_in, return-facing=_out) ──
    _place_airlocks_in_rooms(layout, spec, top_row_ids, is_top=True)
    _place_airlocks_in_rooms(layout, spec, bottom_row_ids, is_top=False)
    # 양방향(CAL) AL은 supply에 작은 spot 배치
    _place_both_way_als(layout, spec, core_x0, supply[0], core_w, supply[1] - supply[0])

    # ── Aux stack (left) ──
    _place_left_stack(layout, room_by_id, aux_left_ids, 0, 0, aux_w, building_h_mm)

    # ── NC stack (right) ──
    _place_right_stack(layout, room_by_id, nc_right_ids, core_x1, 0, nc_w, building_h_mm)

    # ── Equipment in each placed process Room ──
    _place_equipment_grid(layout)

    # ── Doors from adjacency (방↔방, 방↔복도 공유 벽) ──
    _place_doors(layout, spec.adjacency)
    # ── Airlock doors: 각 에어록의 복도쪽 + 방쪽 가장자리 (참조 도면) ──
    _place_airlock_doors(layout)

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
    # [2026-05-31] area_m2=0 인 방도 visible 사이즈 보장 (팀원 spec 호환).
    # area 가 0 또는 너무 작으면 min_area_m2=15 로 fallback — 안 그러면 폭 0 으로
    # 그려져서 안 보임.
    MIN_AREA_FALLBACK = 15.0
    areas = [max(room_by_id[r].area_m2, MIN_AREA_FALLBACK) for r in present]
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


# [2026-06-02 v2] 방 안쪽 가장자리 AL 배치 — 참조 도면 구조.
AL_BAND_H_FRAC = 0.18     # AL box 높이 = 방 높이의 18%
AL_BAND_H_MAX_MM = 4500   # 상한
AL_SLOT_W_FRAC = 0.30     # AL box 폭 = slot 의 30%


def _place_airlocks_in_rooms(layout, spec, row_room_ids, is_top: bool):
    """각 process room *안쪽 가장자리*에 _in/_out AL 작은 box 배치.

    top row: supply 가 아래쪽 → _in 은 방 하단, _out 은 방 상단(return 쪽).
    bottom row: supply 가 위쪽 → _in 은 방 상단, _out 은 방 하단(return 쪽).
    같은 변에 여러 AL 이면 좌→우 균등 분할. (흰 에어록 밴드 제거 효과)
    """
    for rid in row_room_ids:
        if rid not in layout.rooms:
            continue
        r = layout.rooms[rid].rect
        ins = [a for a in spec.airlocks if a.connects_higher == rid and a.type.endswith("_in")]
        outs = [a for a in spec.airlocks if a.connects_higher == rid and a.type.endswith("_out")]
        al_h = min(r.h * AL_BAND_H_FRAC, AL_BAND_H_MAX_MM)
        if is_top:
            in_y, out_y = r.y2 - al_h, r.y           # in=하단(supply), out=상단(return)
            in_side, out_side = "south", "north"
        else:
            in_y, out_y = r.y, r.y2 - al_h           # in=상단(supply), out=하단(return)
            in_side, out_side = "north", "south"
        _place_al_edge(layout, ins, rid, r, in_y, al_h, in_side)
        _place_al_edge(layout, outs, rid, r, out_y, al_h, out_side)


def _place_al_edge(layout, als, rid, room_rect, y, h, side):
    """주어진 AL 목록을 방 한 변(y)에 좌→우 균등 분할로 배치."""
    if not als:
        return
    n = len(als)
    slot_w = room_rect.w / n
    aw = min(slot_w * 0.8, room_rect.w * AL_SLOT_W_FRAC * 2)
    for i, al in enumerate(als):
        ax = room_rect.x + i * slot_w + (slot_w - aw) / 2
        layout.airlocks[al.id] = PlacedAirlock(
            airlock=al, rect=Rect(ax, y, aw, h), attached_room_id=rid, side=side
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
    # [2026-05-31] area=0 인 방 fallback (팀원 spec 호환)
    MIN_AREA_FALLBACK = 15.0
    areas = [max(room_by_id[r].area_m2, MIN_AREA_FALLBACK) for r in present]
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
    MIN_AREA_FALLBACK = 15.0
    areas = [max(room_by_id[r].area_m2, MIN_AREA_FALLBACK) for r in present]
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

        # [2026-06-02 v2] 에어록은 이제 방 *안*에 그려지므로 room↔airlock 인접엔
        # 벽 도어를 그리지 않는다 (AL box + flow 화살표가 통로를 표현). 안 그러면
        # 공유 변이 없어 방 한가운데 fallback 도어가 찍힘.
        if adj.from_id in layout.airlocks or adj.to_id in layout.airlocks:
            continue

        a = _lookup_rect(layout, adj.from_id)
        b = _lookup_rect(layout, adj.to_id)
        if a is None or b is None:
            continue

        # 공유 변 추정 — 공유 벽이 없으면 (None) 도어 생략 (fallback 금지)
        pos = _door_pos(a, b)
        if pos is None:
            continue
        x, y, rot = pos

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


def _place_airlock_doors(layout):
    """각 에어록의 *복도쪽 + 방쪽* 가장자리에 도어 2개 생성 (참조 도면).

    in-room AL (side north/south) 은 방 가장자리에 가로로 놓여 있으므로, AL box
    의 위/아래 변에 가로 도어를 둔다 (한쪽=복도↔AL, 다른쪽=AL↔방). 두 도어 모두
    AL 안쪽으로 swing. inline(both-way, supply 안) AL 은 좌우 세로 도어.
    """
    for pa in layout.airlocks.values():
        r = pa.rect
        if pa.side in ("north", "south"):
            cx = r.cx
            dw = min(r.w * 0.65, 2200)
            # 위 변 (swing 안쪽=아래), 아래 변 (swing 안쪽=위)
            layout.doors.append(PlacedDoor(adj=None, x=cx, y=r.y, width_mm=dw,
                                           rotation_deg=0, swing_to_xy=(cx, r.cy)))
            layout.doors.append(PlacedDoor(adj=None, x=cx, y=r.y2, width_mm=dw,
                                           rotation_deg=0, swing_to_xy=(cx, r.cy)))
        else:  # inline — 좌/우 세로 도어
            cy = r.cy
            dh = min(r.h * 0.65, 2200)
            layout.doors.append(PlacedDoor(adj=None, x=r.x, y=cy, width_mm=dh,
                                           rotation_deg=90, swing_to_xy=(r.cx, cy)))
            layout.doors.append(PlacedDoor(adj=None, x=r.x2, y=cy, width_mm=dh,
                                           rotation_deg=90, swing_to_xy=(r.cx, cy)))


def _lookup_rect(layout, node_id) -> Optional[Rect]:
    if node_id in layout.rooms:
        return layout.rooms[node_id].rect
    if node_id in layout.airlocks:
        return layout.airlocks[node_id].rect
    return None


def _door_pos(a: Rect, b: Rect) -> Optional[tuple[float, float, float]]:
    """두 사각형이 공유하는 벽 위 도어 위치 + 회전 (0=수평벽, 90=수직벽).

    공유 벽이 없으면 (겹침/포함/원격) None — 호출자가 도어 생략.
    공유 변에 *겹치는 구간*이 있을 때만 그 구간 중앙에 도어를 둔다.
    """
    TOL = 50  # mm
    # 세로 인접 (a 위 b 아래 또는 반대) — 공유 가로 벽
    if abs(a.y2 - b.y) < TOL or abs(b.y2 - a.y) < TOL:
        ox0, ox1 = max(a.x, b.x), min(a.x2, b.x2)
        if ox1 - ox0 <= TOL:        # x 구간 겹침 없음 → 실제 공유 벽 아님
            return None
        y = (a.y2 + b.y) / 2 if a.y < b.y else (b.y2 + a.y) / 2
        return (ox0 + ox1) / 2, y, 0
    # 가로 인접 — 공유 세로 벽
    if abs(a.x2 - b.x) < TOL or abs(b.x2 - a.x) < TOL:
        oy0, oy1 = max(a.y, b.y), min(a.y2, b.y2)
        if oy1 - oy0 <= TOL:        # y 구간 겹침 없음
            return None
        x = (a.x2 + b.x) / 2 if a.x < b.x else (b.x2 + a.x) / 2
        return x, (oy0 + oy1) / 2, 90
    return None  # 공유 벽 없음 → 도어 없음
