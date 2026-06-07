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
    """AL 이중 표현 fake room 인지. D-003 시점 보류했던 이슈 (2026-05-31).

    [G3] 룰엔진 새 계약의 명시 플래그 `is_airlock` 를 1차 신호로 사용(견고).
    플래그가 없던 구계약/내부 spec 호환을 위해 ID 패턴+area==0 휴리스틱을 폴백.
    """
    if getattr(room, "is_airlock", False):
        return True
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


# ══════════════════════════════════════════════════════════════════════
# [2026-06-02 v3] GMP 청정도 구배 토폴로지 (사용자 도면 피드백 ①②③⑤ 반영)
#
#   ┌─────────────────────────────────────────────────────────────────┐
#   │ NC  │ Grade D    │D│      GRADE C 공정 구역                       │
#   │ 구역│ 구역(저장) │c│  ┌──────────────────────────────────────┐  │
#   │     │            │o│  │  RETURN CORRIDOR (상)                  │  │
#   │ CIP │ storage    │r│  ├──────────────────────────────────────┤  │
#   │ Mon │ IPC        │r│  │ 공정행(상): MEDIA BUFFER INOC CULT HARV │  │
#   │ off │ 창고       │i│  ├──[GOWN(C)]───────────────────────────┤  │
#   │ toil│ gowning F/M│d│  │  SUPPLY CORRIDOR (중앙)                │  │
#   │     │            │o│  ├──────────────────────────────────────┤  │
#   │     │            │r│  │ 공정행(하): PURIF1 PURIF2 PREP WASH     │  │
#   │     │            │ │  ├──────────────────────────────────────┤  │
#   │     │            │ │  │  RETURN CORRIDOR (하)                  │  │
#   └─────────────────────────────────────────────────────────────────┘
#
# 설계 근거(논문/특허 원재료):
#  - 가로 청정도 구배 NC→D→C (cross-contamination 차단, 인접은 한 등급차).
#  - Grade D 세로 복도 = personnel/material 진입 + return 배출의 공용 통로.
#  - 가운룸(C) 은 D복도 ↔ supply 복도 접점 = 입실 게이트(EU GMP Annex 1).
#  - 중앙 supply(공급) → 공정행 통과 → 양측 return(회수) → D복도 배출 = one-way.
#  - 양측 return 을 모두 실제 방으로 배치 → 정제실(하행) 포함 전 공정행이 return 인접.
#  - 방 가로세로비 water-filling 클램프 → 작은 방 슬리버 방지 + 흰공간 없음.
# ══════════════════════════════════════════════════════════════════════

_SUPPLY_CORR = _re_dyn.compile(r"_SUPPLY_CORRIDOR", _re_dyn.IGNORECASE)
_RETURN_CORR = _re_dyn.compile(r"_RETURN_CORRIDOR", _re_dyn.IGNORECASE)
# Grade D 지원 복도 (supply/return/visitor 가 아닌 일반 복도)
_AUX_CORR = _re_dyn.compile(r"^R_CORRIDOR$|_AUX_CORRIDOR$", _re_dyn.IGNORECASE)


def _classify_rooms_gradient(spec: RuleEngineOutput) -> dict:
    """NC→D→C 구배 토폴로지용 방 분류.

    Returns dict: nc[], d[], d_corridor, process_gowning, supply_corridor,
                  return_corridor, top_row[], bottom_row[], skipped[].
    """
    by_id = {r.id: r for r in spec.rooms}
    out = {
        "nc": [], "d": [], "d_corridor": None, "nc_corridor": None,
        "process_gowning": None, "supply_corridor": None, "return_corridor": None,
        "top_row": [], "bottom_row": [], "skipped": [],
    }
    process_ids: list[str] = []
    gowning_candidates: list[str] = []
    # [정렬] 엔진 zones 를 1차 신호로 — 재분류로 덮어쓰지 않음(예: CIP공급·모니터링은
    # NC 등급이지만 엔진이 auxiliary_zone 으로 지정). zones 없으면 category 폴백.
    z = getattr(spec, "zones", None)
    zone_of: dict[str, str] = {}
    if z is not None:
        for rid in (z.auxiliary_zone or []):
            zone_of[rid] = "aux"
        for rid in (z.nc_zone or []):
            zone_of[rid] = "nc"
        for rid in (z.process_zone or []):
            zone_of[rid] = "process"
    for r in spec.rooms:
        if _is_al_fake_room(r):
            out["skipped"].append(r.id)
            continue
        rid = r.id
        if _SUPPLY_CORR.search(rid):
            out["supply_corridor"] = rid
            continue
        if _RETURN_CORR.search(rid):
            out["return_corridor"] = rid
            continue
        if _AUX_CORR.search(rid) or (r.is_corridor and r.category != "NC"):
            out["d_corridor"] = rid
            continue
        # 공정 가운(입실 게이트) — 청정등급(A/B/C) + GOWNING + 공정 카테고리
        if "GOWNING" in rid and r.clean_grade in ("A", "B", "C") and r.category == "process":
            gowning_candidates.append(rid)
            continue
        zone = zone_of.get(rid)            # 엔진 zone 우선
        is_nc = zone == "nc" or (zone is None and (r.category == "NC" or r.clean_grade == "NC"))
        is_aux = zone == "aux" or (zone is None and r.category == "auxiliary")
        if is_nc:
            # NC 구역의 복도 방 → NC↔D 순환 복도(피드백 #1)로 분리 배치
            if "CORRIDOR" in rid and out["nc_corridor"] is None:
                out["nc_corridor"] = rid
            else:
                out["nc"].append(rid)
            continue
        if is_aux:
            out["d"].append(rid)
            continue
        process_ids.append(rid)  # 나머지 = 공정실

    # 가운룸이 여러 개면 하나만 게이트(supply 접점), 나머지는 공정행에 배치(누락 방지)
    if gowning_candidates:
        gate = "R_GOWNING" if "R_GOWNING" in gowning_candidates else gowning_candidates[0]
        out["process_gowning"] = gate
        process_ids.extend(g for g in gowning_candidates if g != gate)

    # 공정실 정렬: PPO 우선 + 나머지 area 내림차순
    ppo = list(getattr(spec.flow_paths, "product_process_order", []) or [])
    seen: set[str] = set()
    sorted_proc: list[str] = []
    for rid in ppo:
        if rid in process_ids and rid not in seen:
            sorted_proc.append(rid)
            seen.add(rid)
    extras = sorted([r for r in process_ids if r not in seen],
                    key=lambda r: -(by_id[r].area_m2 or 0.0))
    sorted_proc.extend(extras)
    if len(sorted_proc) <= 5:
        out["top_row"] = sorted_proc
    else:
        half = (len(sorted_proc) + 1) // 2
        out["top_row"] = sorted_proc[:half]
        out["bottom_row"] = sorted_proc[half:]
    return out


def _alloc_dim(areas: list[float], total: float, cross: float, max_aspect: float) -> list[float]:
    """면적 비례로 total 길이를 분배하되 각 칸이 cross/max_aspect 미만으로
    얇아지지 않게 water-filling 보정. 합 == total 보장 (슬리버 방지 + 흰공간 없음)."""
    n = len(areas)
    if n == 0:
        return []
    floor = min(cross / max_aspect, total / n)
    s = sum(areas) or 1.0
    dims = [total * a / s for a in areas]
    for _ in range(6):
        deficit = sum(floor - x for x in dims if x < floor)
        if deficit <= 1e-6:
            break
        donors = [i for i, x in enumerate(dims) if x > floor]
        excess = sum(dims[i] - floor for i in donors) or 1.0
        for i in donors:
            dims[i] -= deficit * (dims[i] - floor) / excess
        dims = [max(x, floor) for x in dims]
    return dims


# ──────────────────────────────────────────────────────────────────────
# Squarified treemap (Bruls·Huizing·van Wijk 2000) — 면적∝값, 종횡비→정사각.
# [D-024] 고정폭 컬럼 + 종횡비 floor 클램프가 작은 방을 일괄 부풀려 면적 비례를
# 깨뜨리던 문제(alignment_audit #5: Cell bank 20㎡ ≡ Material 100㎡) 해소.
# ──────────────────────────────────────────────────────────────────────
def _sq_worst(row: list, length: float) -> float:
    """행(row) 을 length 변에 깔 때 최악 종횡비 (1 에 가까울수록 좋음)."""
    s = sum(v for _, v in row)
    if s <= 0 or length <= 0:
        return float("inf")
    mx = max(v for _, v in row)
    mn = min(v for _, v in row)
    return max((length * length * mx) / (s * s), (s * s) / (length * length * mn))


def _sq_layout(row: list, x: float, y: float, dx: float, dy: float):
    """row 를 짧은 변에 깔고 (배치들, 남은 사각형) 반환."""
    s = sum(v for _, v in row)
    rects = []
    if dx >= dy:                      # 세로로 쌓는 한 열(폭 width)
        width = s / dy if dy else 0.0
        yy = y
        for i, v in row:
            ht = v / width if width else 0.0
            rects.append((i, Rect(x, yy, width, ht)))
            yy += ht
        return rects, (x + width, y, dx - width, dy)
    else:                             # 가로로 까는 한 행(높이 height)
        height = s / dx if dx else 0.0
        xx = x
        for i, v in row:
            wd = v / height if height else 0.0
            rects.append((i, Rect(xx, y, wd, height)))
            xx += wd
        return rects, (x, y + height, dx, dy - height)


def _squarify_rec(items: list, x: float, y: float, dx: float, dy: float, out: list) -> None:
    if not items:
        return
    if len(items) == 1:
        out.append((items[0][0], Rect(x, y, dx, dy)))
        return
    length = min(dx, dy)
    i = 1
    while i < len(items) and _sq_worst(items[:i], length) >= _sq_worst(items[:i + 1], length):
        i += 1
    rects, (nx, ny, ndx, ndy) = _sq_layout(items[:i], x, y, dx, dy)
    out.extend(rects)
    _squarify_rec(items[i:], nx, ny, ndx, ndy, out)


def _squarify(items: list, x: float, y: float, dx: float, dy: float) -> list:
    """items=[(id, area_value)] 를 (x,y,dx,dy) 안에 면적 비례로 분할.
    반환 [(id, Rect)]. 합 면적 == dx*dy (흰공간 0)."""
    total = sum(max(v, 1e-9) for _, v in items) or 1.0
    scale = (dx * dy) / total
    scaled = [(i, max(v, 1e-9) * scale) for i, v in items]
    out: list = []
    _squarify_rec(scaled, x, y, dx, dy, out)
    return out


def _place_treemap(layout, by_id, ids, x0, y0, w, h, order_desc: bool = True) -> None:
    """ids 를 (x0,y0,w,h) 영역에 squarified treemap 으로 배치 (면적 비례)."""
    present = [r for r in ids if r in by_id]
    if not present:
        return
    items = [(r, max(by_id[r].area_m2 or 0.0, 1.0)) for r in present]
    if order_desc:                    # 종횡비 품질 위해 큰 방부터 (순서 무관 영역)
        items.sort(key=lambda t: -t[1])
    for rid, rect in _squarify(items, x0, y0, w, h):
        layout.rooms[rid] = PlacedRoom(room=by_id[rid], rect=rect)


def _place_d_zone_rows(layout, by_id, ids, x0, y0, w, h) -> dict:
    """[D-034 / 피드백 0607] Grade D 방을 팀장님 지정 배치로 명시 배치.
    위→아래: Material storage / Equipment storage / Gowning F / Gowning M (각 전폭)
             → Monitoring | DS storage (좌우) → CIP supply | IPC(위)/Cell bank(아래)
             → 나머지(전폭). 우측 열(DS·IPC·Cell bank)=Grade D 복도 접촉, 좌측
             열(Monitoring·CIP)=후방 지원실. 반환: {room_id: 'corridor'|'back'} 접촉 힌트.
    """
    pool = [i for i in ids if i in by_id]

    def take(*keys):
        for i in list(pool):
            up = i.upper()
            if any(k in up for k in keys):
                pool.remove(i)
                return i
        return None

    mat_store = take("MATERIAL_STORAGE", "MATERIAL_STORE")
    equip = take("EQUIPMENT")
    gown_f = take("GOWNING_FEMALE", "GOWNING_F")
    gown_m = take("GOWNING_MALE", "GOWNING_M")
    monitoring = take("MONITOR")
    ds = take("DS_STORAGE", "DS_STORE", "DRUG_SUBSTANCE")
    cip = take("CIP")
    ipc = take("IPC")
    cellbank = take("CELL_BANK", "CELLBANK")

    rows = []                                   # ("full", rid) | ("pair", left, [rights])
    for rid in (mat_store, equip, gown_f, gown_m):
        if rid:
            rows.append(("full", rid, None))
    if monitoring or ds:
        rows.append(("pair", monitoring, [r for r in (ds,) if r]))
    if cip or ipc or cellbank:
        rows.append(("pair", cip, [r for r in (ipc, cellbank) if r]))
    for rid in pool:                            # 분류 안 된 나머지 D 방 = 전폭
        rows.append(("full", rid, None))
    if not rows:
        return {}

    def area(rid):
        return max((by_id[rid].area_m2 or 0.0), 10.0) if rid else 0.0

    def row_weight(row):
        if row[0] == "full":
            return area(row[1])
        return max(area(row[1]), sum(area(r) for r in row[2]))

    weights = [row_weight(r) for r in rows]
    tot = sum(weights) or 1.0
    touch = {}                                  # 복도 접촉 힌트
    yy = y0
    for row, wt in zip(rows, weights):
        rh = h * wt / tot
        if row[0] == "full":
            rid = row[1]
            layout.rooms[rid] = PlacedRoom(room=by_id[rid], rect=Rect(x0, yy, w, rh))
            touch[rid] = "corridor"             # 전폭 → 우측 D복도 접촉
        else:
            left, rights = row[1], row[2]
            lw = w * 0.5 if rights else w
            if left:
                layout.rooms[left] = PlacedRoom(room=by_id[left], rect=Rect(x0, yy, lw, rh))
                touch[left] = "back" if rights else "corridor"
            if rights:
                rx, rw = x0 + lw, w - lw
                ra = [area(r) for r in rights]
                rt = sum(ra) or 1.0
                ry = yy
                for rr, a in zip(rights, ra):
                    rhh = rh * a / rt
                    layout.rooms[rr] = PlacedRoom(room=by_id[rr], rect=Rect(rx, ry, rw, rhh))
                    touch[rr] = "corridor"       # 우측 열 → D복도 접촉
                    ry += rhh
        yy += rh
    return touch


def _place_row_aspect(layout, by_id, ids, x0, y0, w, h, max_aspect=1.9):
    """가로 행 배치 — 면적 비례 폭 + 종횡비 클램프(작은 방 세로 슬리버 방지)."""
    present = [r for r in ids if r in by_id]
    if not present:
        return
    areas = [max(by_id[r].area_m2 or 0.0, 15.0) for r in present]
    widths = _alloc_dim(areas, w, h, max_aspect)
    x = x0
    for rid, wd in zip(present, widths):
        layout.rooms[rid] = PlacedRoom(room=by_id[rid], rect=Rect(x, y0, wd, h))
        x += wd


def _place_stack_aspect(layout, by_id, ids, x0, y0, w, h, max_aspect=2.4):
    """세로 스택 배치 — 면적 비례 높이 + 종횡비 클램프."""
    present = [r for r in ids if r in by_id]
    if not present:
        return
    areas = [max(by_id[r].area_m2 or 0.0, 15.0) for r in present]
    heights = _alloc_dim(areas, h, w, max_aspect)
    y = y0
    for rid, ht in zip(present, heights):
        layout.rooms[rid] = PlacedRoom(room=by_id[rid], rect=Rect(x0, y, w, ht))
        y += ht


def _add_synth_door(layout, a: "Rect", b: "Rect", swing_into: "Rect"):
    """adjacency 에 없는 게이트(가운↔복도) 도어를 공유 벽에 합성."""
    pos = _door_pos(a, b)
    if pos is None:
        return
    x, y, rot = pos
    layout.doors.append(PlacedDoor(adj=None, x=x, y=y, width_mm=1500,
                                   rotation_deg=rot, swing_to_xy=(swing_into.cx, swing_into.cy)))


def _ensure_door(layout, room_rect: "Rect", corr_rect: "Rect") -> bool:
    """room↔corridor 가 벽을 공유하면 도어 1개 합성(없을 때만). 공유 벽 없으면 False."""
    pos = _door_pos(room_rect, corr_rect)
    if pos is None:
        return False
    x, y, rot = pos
    for d in layout.doors:                       # 근접 중복 도어 방지
        if abs(d.x - x) < 600 and abs(d.y - y) < 600:
            return True
    layout.doors.append(PlacedDoor(adj=None, x=x, y=y, width_mm=1500,
                                   rotation_deg=rot, swing_to_xy=(room_rect.cx, room_rect.cy)))
    return True


def _ensure_rooms_touch_corridor(layout, room_ids: list, corr_ids: list) -> None:
    """[A6 + containment] room_ids 각 방이 corr_ids 중 인접 복도에 도어를 갖게 보장.
    corr_ids 를 등급 경계에 맞게 제한하면(예: D방→D복도만) 부적절 등급 직결을 차단."""
    corrs = [(cid, layout.rooms[cid].rect) for cid in corr_ids
             if cid and cid in layout.rooms]
    for rid in room_ids:
        if rid not in layout.rooms:
            continue
        rr = layout.rooms[rid].rect
        for _cid, cr in corrs:
            if _ensure_door(layout, rr, cr):
                break


def _normalize_door_widths(layout) -> None:
    """[피드백 2026-06-07] 도어 폭이 제각각(adj.door_size_mm 스펙값 vs 합성 1500 등)
    → 가장 작은 문 기준으로 전체 도어 폭 통일."""
    widths = [d.width_mm for d in layout.doors if d.width_mm and d.width_mm > 0]
    if not widths:
        return
    m = min(widths)
    for d in layout.doors:
        d.width_mm = m


def _synth_corridor_room(rid: str, name_ko: str, name_en: str) -> Room:
    """전용 복도 방이 spec 에 없을 때 쓸 합성 복도 Room (NC, is_corridor)."""
    return Room(
        id=rid, name_ko=name_ko, name_en=name_en,
        category="NC", clean_grade="NC", area_m2=0.0,
        is_corridor=True, corridor_role="auxiliary",
        background_color="#F5F5F5", transparency_pct=0,
    )


def _synth_gate_room(rid: str, name_ko: str, name_en: str, grade: str = "C",
                     area_m2: float = 16.0) -> Room:
    """접경 게이트(반입실 등) 합성 Room (Grade C process)."""
    return Room(
        id=rid, name_ko=name_ko, name_en=name_en,
        category="process", clean_grade=grade, area_m2=area_m2,
        background_color="#FCD34D",
    )


def _solve_gmp_gradient(spec: RuleEngineOutput, W: float, H: float) -> "Layout":
    """NC→D→C 청정도 구배 토폴로지 솔버 (dynamic_rooms 경로)."""
    layout = Layout(building_w_mm=W, building_h_mm=H)
    by_id = {r.id: r for r in spec.rooms}
    cls = _classify_rooms_gradient(spec)

    has_nc = bool(cls["nc"])
    has_d = bool(cls["d"])
    has_dc = bool(cls["d_corridor"])
    # [정렬] 세로 복도 폭 = spec.constraints.corridor_width_mm (preferred_min~max)
    # 로 GMP 규정 폭 적용. 없으면 기본.
    cw = getattr(spec, "constraints", None)
    cwr = getattr(cw, "corridor_width_mm", None) if cw else None
    corr_w = 2748.0
    if cwr is not None:
        pref = cwr.preferred_min or cwr.min or 2000
        cmax = cwr.max or 3000
        corr_w = float(max(cwr.min or 1500, min(pref, cmax)))
    # 장비 이격(mm) — equipment_clearance_mm.between_equipment (GMP 최소 1000)
    ec = getattr(cw, "equipment_clearance_mm", None) if cw else None
    eq_gap_mm = float(ec.get("between_equipment", 800)) if isinstance(ec, dict) and ec else 800.0
    # [D-030 / 피드백 #1] NC↔Grade D 사이 순환 복도. 사람이 NC(Office)→Gowning→
    # Grade D 복도로 이동할 동선 + flow 라우팅이 탈 채널을 제공.
    has_ncc = has_nc and has_d
    w_ncc = corr_w if has_ncc else 0.0
    w_dc = corr_w if has_dc else 0.0
    # NC/D 컬럼 폭 — 복도 폭 차감분 반영
    w_nc = W * 0.13 - (w_ncc * 0.5 if has_ncc else 0.0) if has_nc else 0.0
    w_d = W * 0.16 - (w_ncc * 0.5 if has_ncc else 0.0) if has_d else 0.0
    ncc_x0 = w_nc
    d_x0 = w_nc + w_ncc
    c_x0 = w_nc + w_ncc + w_d + w_dc
    c_w = W - c_x0

    # 1) NC 스택(최좌)  1.5) NC↔D 순환 복도  2) Grade D 스택  3) Grade D 세로 복도
    # [D-024] 단일 스택(고정폭) → squarified treemap 으로 면적 비례 배치.
    if has_nc:
        _place_treemap(layout, by_id, cls["nc"], 0.0, 0.0, w_nc, H)
    if w_ncc > 0:
        ncc_id = cls.get("nc_corridor")
        if not (ncc_id and ncc_id in by_id):           # 전용 복도 방 없으면 합성
            ncc_id = "R_NC_AUX_CORRIDOR"
            by_id[ncc_id] = _synth_corridor_room(ncc_id, "NC 보조복도", "NC aux corridor")
        layout.rooms[ncc_id] = PlacedRoom(
            room=by_id[ncc_id], rect=Rect(ncc_x0, 0.0, w_ncc, H))
    if has_d:
        # [피드백 #3] Material-in(반입·상단 12시) ↔ Waste-out(반출·하단 9시) 를
        # 교차오염 방지 위해 Grade D 컬럼 상/하 극단으로 분리. 나머지는 가운데 treemap.
        d_ids = list(cls["d"])
        mat_in = next((r for r in d_ids if "MATERIAL_IN" in r or "MATERIAL_INLET" in r), None)
        waste_out = next((r for r in d_ids if "WASTE_OUT" in r or "WASTE" in r), None)
        d_y0, d_h = 0.0, H
        if mat_in:
            mh = max(min(H * 0.12, (by_id[mat_in].area_m2 or 0.0) * 1e6 / w_d), H * 0.06)
            layout.rooms[mat_in] = PlacedRoom(room=by_id[mat_in], rect=Rect(d_x0, 0.0, w_d, mh))
            d_y0, d_h = mh, d_h - mh
            d_ids.remove(mat_in)
        if waste_out:
            wh = max(min(H * 0.12, (by_id[waste_out].area_m2 or 0.0) * 1e6 / w_d), H * 0.06)
            layout.rooms[waste_out] = PlacedRoom(room=by_id[waste_out], rect=Rect(d_x0, H - wh, w_d, wh))
            d_h -= wh
            d_ids.remove(waste_out)
        # [D-034 / 피드백 0607] 팀장님 지정 2D 배치(전폭 + 좌우 묶음). treemap·단일열 아님.
        d_touch = _place_d_zone_rows(layout, by_id, d_ids, d_x0, d_y0, w_d, d_h)
        cls["_d_touch"] = d_touch
    if has_dc:
        layout.rooms[cls["d_corridor"]] = PlacedRoom(
            room=by_id[cls["d_corridor"]], rect=Rect(d_x0 + w_d, 0.0, w_dc, H))

    # 4) C 공정 구역 — 5밴드 (return상 / 공정상 / supply중앙 / 공정하 / return하)
    ratios = [0.06, 0.36, 0.14, 0.36, 0.08]
    ssum = sum(ratios)
    ratios = [r / ssum for r in ratios]
    yacc = 0.0
    bands = []
    for rr in ratios:
        hh = H * rr
        bands.append((yacc, yacc + hh))
        yacc += hh
    (ret_t, proc_t, sup, proc_b, ret_b) = bands

    # return 복도 (상·하 모두 실제 방 — 정제실 하행도 return 인접)
    rc = cls["return_corridor"]
    if rc:
        layout.rooms[rc] = PlacedRoom(room=by_id[rc],
                                      rect=Rect(c_x0, ret_t[0], c_w, ret_t[1] - ret_t[0]))
        bc = by_id[rc].model_copy(update={"id": rc + "_S"})
        layout.rooms[bc.id] = PlacedRoom(room=bc,
                                         rect=Rect(c_x0, ret_b[0], c_w, ret_b[1] - ret_b[0]))

    # [피드백 0607] D↔C 진입 게이트 = Gowning(위) / MAL-in(아래) **세로 스택**, C 좌단.
    #   (이전엔 가로 나란히였음 — 팀장님 지정 세로 스택으로 변경.) 우측에 supply 복도.
    sup_y, sup_h = sup[0], sup[1] - sup[0]
    gate_w = min(c_w * 0.15, max(c_w * 0.09, 6500.0))
    gown = cls["process_gowning"]
    mal_id = next((r.id for r in spec.rooms
                   if "MAL_IN" in r.id.upper() and not _is_al_fake_room(r) and r.id in by_id), None)
    if mal_id is None:
        mal_id = "R_SUPPLY_MAL_IN"
        by_id[mal_id] = _synth_gate_room(mal_id, "자재 반입실 (MAL-in)", "Material Air Lock in")
    if gown and gown in by_id:
        # 면적 비례로 상/하 분할 (Gowning 위, MAL-in 아래)
        ga = max(by_id[gown].area_m2 or 0.0, 10.0)
        ma = max(by_id[mal_id].area_m2 or 0.0, 10.0)
        gh = sup_h * ga / (ga + ma)
        layout.rooms[gown] = PlacedRoom(room=by_id[gown],
                                        rect=Rect(c_x0, sup_y, gate_w, gh))
        layout.rooms[mal_id] = PlacedRoom(room=by_id[mal_id],
                                          rect=Rect(c_x0, sup_y + gh, gate_w, sup_h - gh))
    else:
        layout.rooms[mal_id] = PlacedRoom(room=by_id[mal_id],
                                          rect=Rect(c_x0, sup_y, gate_w, sup_h))
    sx = c_x0 + gate_w
    sc = cls["supply_corridor"]
    if sc:
        layout.rooms[sc] = PlacedRoom(room=by_id[sc],
                                      rect=Rect(sx, sup_y, c_x0 + c_w - sx, sup_h))

    # 공정행 (상·하) — 종횡비 클램프 적용
    _place_row_aspect(layout, by_id, cls["top_row"], c_x0, proc_t[0], c_w, proc_t[1] - proc_t[0])
    _place_row_aspect(layout, by_id, cls["bottom_row"], c_x0, proc_b[0], c_w, proc_b[1] - proc_b[0])

    # 에어록(공정행 내측) + 양방향 AL(supply) + 장비
    _place_airlocks_in_rooms(layout, spec, cls["top_row"], is_top=True)
    _place_airlocks_in_rooms(layout, spec, cls["bottom_row"], is_top=False)
    _place_both_way_als(layout, spec, sx, sup[0], c_x0 + c_w - sx, sup[1] - sup[0])
    _place_equipment_grid(layout, eq_gap=eq_gap_mm)

    # 도어: adjacency 기반 + D→C 게이트(Gowning·MAL-in) 합성 도어 = D복도(좌)·supply(우) 양쪽
    _place_doors(layout, spec.adjacency)
    for gid in (gown, mal_id):
        if gid and gid in layout.rooms:
            g = layout.rooms[gid].rect
            if has_dc and cls["d_corridor"] in layout.rooms:
                _ensure_door(layout, g, layout.rooms[cls["d_corridor"]].rect)
            if sc and sc in layout.rooms:
                _ensure_door(layout, g, layout.rooms[sc].rect)
    # [D-034 / 피드백 0607] A6 + containment 보장:
    #   · NC 방 → NC 복도로만 출입
    #   · D 방 → Grade D 복도로만 출입(NC 직결 금지 — CIP/Monitoring 오염차단)
    #   · Gowning M/F 만 NC복도+D복도 양쪽 도어 = NC↔D 인원 게이트(갱의 강제)
    nc_corr_id = cls.get("nc_corridor")
    d_corr_id = cls.get("d_corridor")
    d_touch = cls.get("_d_touch", {})
    d_all = [r for r in cls["d"] if r in layout.rooms]
    gownings = [r for r in d_all if "GOWNING" in r.upper()]
    if d_corr_id and d_corr_id in layout.rooms:
        dcr = layout.rooms[d_corr_id].rect
        for rid in d_all:
            if rid in gownings:
                continue
            rr = layout.rooms[rid].rect
            if d_touch.get(rid) == "back":
                # 후방 지원실(Monitoring·CIP) — 복도 직접 접촉 불가 → 앞(served) 방에 도어
                front = next((layout.rooms[o].rect for o in d_all if o != rid
                              and abs(layout.rooms[o].rect.x - rr.x2) < 60
                              and not (layout.rooms[o].rect.y2 <= rr.y or layout.rooms[o].rect.y >= rr.y2)),
                             None)
                _ensure_door(layout, rr, front if front is not None else dcr)
            else:
                _ensure_door(layout, rr, dcr)        # 전폭·우측열 → D복도 도어
        # Gowning M/F = NC↔D 게이트 → NC복도 + D복도 양쪽 도어
        for g in gownings:
            gr = layout.rooms[g].rect
            _ensure_door(layout, gr, dcr)
            if nc_corr_id and nc_corr_id in layout.rooms:
                _ensure_door(layout, gr, layout.rooms[nc_corr_id].rect)
    if nc_corr_id:
        _ensure_rooms_touch_corridor(layout, cls["nc"], [nc_corr_id])
    _place_airlock_doors(layout)
    return layout


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
        # [2026-06-02 v3] 외부(소연) spec → GMP 청정도 구배 토폴로지(NC→D→C).
        # 사용자 도면 피드백(②③⑤) 반영: D복도 + 가운 게이트 + 양측 return 복도.
        layout = _solve_gmp_gradient(spec, building_w_mm, building_h_mm)
        _normalize_door_widths(layout)        # [피드백 0607] 도어 폭 통일
        return layout

    # ── 하드코딩 strip-band (우리 default URS 전용; baselines/NNE/테스트 보존, 무수정) ──
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
    # [2026-06-02 v3] AL 폭 절대 상한 — 큰 방(정제실 등)에서 에어록이 방의 40%까지
    # 커지던 문제. 실제 전실은 ~3.5m 박스. slot 안에서 중앙 정렬.
    aw = min(slot_w * 0.8, room_rect.w * AL_SLOT_W_FRAC, 3800.0)
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


def _place_equipment_grid(layout, use_actual_mm: bool = False, eq_gap: float = 800.0):
    """Room 내부에 장비를 process_step 순서대로 grid 배치.
    장비가 모두 방 안에 들어가도록 scale 을 자동 조정 (사용자 요청).

    [B-001 / D-018] `use_actual_mm=True` 면 시각 축소 (EQUIPMENT_VISUAL_SCALE)
    적용 안 하고 실제 W_mm/D_mm 사용. CP-SAT 측정 비교용. 기본은 False 로
    기존 strip-band 동작 보존 (baselines.json / B3 NNE 비교 흔들지 않게).

    [정렬] `eq_gap` = 장비간 이격(mm). gradient 경로는 spec.constraints 의
    equipment_clearance_mm.between_equipment 를 넘겨 GMP 컴플라이언스 충족
    (기본 800 은 strip-band 보존용 — baselines 불변).
    """
    wall_margin = 2200    # 좌/우
    top_label = 6000      # 위쪽 — 라벨 3줄 공간
    bottom_pad = 2500     # 아래쪽
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

        # [피드백 #2] 주요 공정실끼리 직접 인접 도어 삭제 — 공정물은 도어가 아니라
        # 벽/CIP 배관으로 이동(규정 Product §2, 예: Purif1↔Purif2 도어 없음).
        # 동일 청정등급 process↔process 인접은 도어를 그리지 않는다.
        ra = layout.rooms.get(adj.from_id)
        rb = layout.rooms.get(adj.to_id)
        if (ra and rb and ra.room.category == "process" and rb.room.category == "process"
                and ra.room.clean_grade == rb.room.clean_grade):
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

        # [정렬] door_count 반영 — 공유 벽을 따라 N개 분산 배치(큰 MAL=2도어 등).
        count = max(1, int(adj.door_count or 1))
        spacing = (adj.door_size_mm or 1000) + 800.0
        for k in range(count):
            shift = (k - (count - 1) / 2.0) * spacing
            dx = shift if rot == 0 else 0.0      # 가로 도어=가로 벽 → x 분산
            dy = shift if rot != 0 else 0.0      # 세로 도어=세로 벽 → y 분산
            layout.doors.append(
                PlacedDoor(
                    adj=adj,
                    x=x + dx,
                    y=y + dy,
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
            # 두 문이 AL 안쪽으로 휘면 반원처럼 합쳐짐 → *바깥쪽*으로 열리게.
            # 위 변 문 = 위로(swing target y < y), 아래 변 문 = 아래로.
            layout.doors.append(PlacedDoor(adj=None, x=cx, y=r.y, width_mm=dw,
                                           rotation_deg=0, swing_to_xy=(cx, r.y - 1000)))
            layout.doors.append(PlacedDoor(adj=None, x=cx, y=r.y2, width_mm=dw,
                                           rotation_deg=0, swing_to_xy=(cx, r.y2 + 1000)))
        else:  # inline — 좌/우 세로 도어 (바깥쪽으로)
            cy = r.cy
            dh = min(r.h * 0.65, 2200)
            layout.doors.append(PlacedDoor(adj=None, x=r.x, y=cy, width_mm=dh,
                                           rotation_deg=90, swing_to_xy=(r.x - 1000, cy)))
            layout.doors.append(PlacedDoor(adj=None, x=r.x2, y=cy, width_mm=dh,
                                           rotation_deg=90, swing_to_xy=(r.x2 + 1000, cy)))


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


# ══════════════════════════════════════════════════════════════════════
# [2026-06-02] 토폴로지 변형 — 중앙 공정 블록 + 좌/우 지원 + 상/하 갤러리
# (참조: ISPE 컨셉 도면 — central process bays + perimeter support/gallery)
# ══════════════════════════════════════════════════════════════════════
def solve_perimeter_ring(
    spec: RuleEngineOutput,
    building_w_mm: float = 78500,
    building_h_mm: float = 42500,
    auto_canvas: bool = True,
) -> Layout:
    """중앙 공정 블록(다행 그리드) + 좌(지원)·우(유틸) 스택 + 상/하 visitor gallery 띠.

    참조 도면형 토폴로지: 가운데에 공정 bay 들이 그리드로 배치되고, 주변을
    warehouse/QC(좌), utilities/waste(우), visitor gallery(상·하)가 ㅁ자로 감싼다.
    strip-band 의 중앙 supply/return 가로 코리도 대신 외곽 갤러리 프레임을 둠.
    """
    import math
    if auto_canvas:
        building_w_mm, building_h_mm = _auto_canvas_for_rooms(spec, building_w_mm, building_h_mm)
    W, H = building_w_mm, building_h_mm
    layout = Layout(building_w_mm=W, building_h_mm=H)
    room_by_id = {r.id: r for r in spec.rooms}
    cls = _classify_rooms_dynamic(spec)

    gallery = H * 0.07           # 상/하 visitor gallery 띠 높이
    side = W * 0.15              # 좌/우 지원 스택 폭
    cx0, cx1 = side, W - side    # 중앙 블록 x 범위
    cw = cx1 - cx0
    cy0 = gallery
    ch = H - 2 * gallery         # 중앙 블록 높이

    # ── 상/하 visitor gallery (전폭 코리도 프레임) ──
    corr_ids = cls["corridors"]
    top_c = corr_ids[0] if corr_ids else None
    bot_c = corr_ids[1] if len(corr_ids) > 1 else top_c
    if top_c:
        layout.rooms[top_c] = PlacedRoom(room=room_by_id[top_c], rect=Rect(0, 0, W, gallery))
    if bot_c:
        bc = room_by_id[bot_c]
        if bot_c == top_c:                       # 코리도 1개면 복제해 하단 갤러리
            bc = bc.model_copy(update={"id": bot_c + "_S"})
        layout.rooms[bc.id] = PlacedRoom(room=bc, rect=Rect(0, H - gallery, W, gallery))

    # ── 좌 지원(warehouse/QC/locker) · 우 유틸(utilities/waste) 스택 ──
    _place_left_stack(layout, room_by_id, cls["aux_left"], 0, cy0, side, ch)
    _place_right_stack(layout, room_by_id, cls["nc_right"], cx1, cy0, side, ch)

    # ── 중앙 공정 블록 — 다행 그리드 (각 행 area 비례 폭) ──
    process = [r for r in (cls["top_row"] + cls["bottom_row"]) if r in room_by_id]
    n_rows = 2 if len(process) <= 8 else 3
    per = max(1, math.ceil(len(process) / n_rows))
    rh = ch / n_rows
    for ri in range(n_rows):
        chunk = process[ri * per:(ri + 1) * per]
        if chunk:
            _place_process_row(layout, room_by_id, chunk, cx0, cy0 + ri * rh, cw, rh)

    # ── 에어록(공정 방 내측) + 장비 + 도어 ──
    _place_airlocks_in_rooms(layout, spec, process, is_top=True)
    _place_equipment_grid(layout)
    _place_doors(layout, spec.adjacency)
    _place_airlock_doors(layout)
    return layout
