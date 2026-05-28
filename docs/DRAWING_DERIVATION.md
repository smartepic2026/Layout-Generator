# Drawing 도출 원리 — Drawing Agent v1

> Rule Engine이 만든 7-블록 명세(spec)를 받아 실측 좌표 도면(SVG)으로 변환하는 모듈의 작동 원리.
> 1부는 입문자/심사위원용, 2부는 논문/엔지니어 리뷰용.

---

# 1부 — 개요

## 1.1 Drawing Agent가 하는 일

Rule Engine 단계에서 결정되는 것:
- 어떤 Room이 있는가 (예: 배지조제실, 발효실, 정제실 1/2)
- 각 Room의 청정등급, 면적, 차압, 환기횟수
- Room 간 인접 관계, 어디에 도어가 있는가
- Airlock 종류 (PAL/MAL/CAL), 어느 두 방을 연결하는가
- 4종 동선 (인원·자재·폐기물·제품)

Rule Engine 단계에서 결정되지 않는 것:
- 각 Room이 건물의 어느 위치에 있는가 (좌표)
- Room의 정확한 크기·모양 (가로·세로 mm)
- 장비가 Room 안 어느 위치에 있는가
- 도어가 벽의 어느 지점에 있는가
- 그 모든 것을 어떻게 그릴 것인가

**Drawing Agent는 두 번째 목록의 문제를 푼다.** 입력은 추상 명세, 출력은 mm 단위 좌표가 박힌 SVG 도면이다.

## 1.2 입력 / 출력

**입력**:
- `RuleEngineOutput` (Pydantic 모델, JSON 직렬화 가능)
- 건물 크기 (width_mm × depth_mm)

**출력**:
- 단일 SVG 텍스트 (외부 라이브러리 의존성 없음)
- 내부적으로 `Layout` 객체 — 모든 Room/Airlock/Door의 실측 좌표를 담은 데이터구조 (RL 단계 또는 후속 채점에서 재사용)

## 1.3 그림은 어떻게 만들어지나 — 기술 스택

이 코드는 **그림을 그리지 않는다**. 텍스트를 쓴다.

### 1.3.1 SVG는 텍스트 파일이다

출력 도면 `floorplan_v2.svg` 의 실체는 그림이 아니라 글자 묶음이다. 파일을 텍스트 에디터로 열면 이런 내용이 들어 있다.

```xml
<svg viewBox="0 0 1400 720" xmlns="http://www.w3.org/2000/svg">
  <rect x="80" y="108" width="160" height="120"
        fill="#FCD34D" fill-opacity="0.5"
        stroke="#000" stroke-width="3.2"/>
  <text x="160" y="127" text-anchor="middle"
        font-size="12" font-weight="700">Media &amp; Buffer Prep.</text>
</svg>
```

각 줄은 "어떤 도형을 어디에 어떻게 그릴지"를 적은 설명서다.
- `<rect>` = 사각형 (Room)
- `<line>` = 직선 (벽, 화살표)
- `<path>` = 임의의 경로 (L자형 벽, 호)
- `<polygon>` = 다각형 (Airlock의 검은 삼각형)
- `<text>` = 문자 (Room 이름, 장비 라벨)
- `fill="#FCD34D"` = 채움 색 (Grade C 앰버)
- `stroke="#000"` = 테두리 검정
- `stroke-width="3.2"` = 테두리 두께

이런 명령어가 한 SVG 파일에 약 **2,000~3,000 줄** 들어가서 도면 하나가 완성된다.

### 1.3.2 Python이 SVG 텍스트를 직접 작성한다

`renderer.py` 가 하는 일은 **문자열을 이어붙이는 것**뿐이다. 그래픽 라이브러리(matplotlib, PIL/Pillow, OpenCV, Cairo 등)를 일절 쓰지 않는다.

```python
# src/drawing_agent/renderer.py — Room 하나를 그리는 핵심 코드
def _emit_z4_room_fills(s: StringIO, ox, oy, layout):
    for pr in layout.rooms.values():
        x, y, w, h = _r(pr.rect, ox, oy)   # mm → SVG unit 변환
        fill = T.GRADE[pr.room.clean_grade]["fill"]  # KB에서 Grade 색
        s.write(
            f'<rect x="{x:.2f}" y="{y:.2f}" '
            f'width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" fill-opacity="0.5"/>\n'
        )
```

`StringIO` 객체에 SVG 태그 문자열을 한 줄씩 `.write()` 로 쌓는다. 마지막에 `s.getvalue()` 로 전체 문자열을 꺼내 `.svg` 파일로 저장한다.

즉 "도형을 그린다"가 아니라 **"도형을 그리라는 명령어를 텍스트로 쓴다"**.

### 1.3.3 픽셀로 바꾸는 건 누구인가

생성된 `.svg` 파일을 더블클릭하면 **OS 또는 브라우저가 SVG 파서를 호출해서** 텍스트의 좌표·색·두께를 읽어 화면 픽셀로 그린다.

| 환경 | SVG → 픽셀 변환 주체 |
|---|---|
| macOS Finder Quick Look | macOS 내장 SVG 렌더러 (CoreGraphics) |
| 브라우저 (Chrome/Safari/Firefox) | 브라우저 내장 SVG 엔진 |
| VSCode 미리보기 | VSCode 확장 (브라우저 엔진 기반) |
| Inkscape / Adobe Illustrator | 각자의 vector 렌더러 |
| 인쇄 | 프린터 드라이버 + OS 렌더러 |

같은 SVG 파일을 어디서 열든 동일한 도면이 보이는 이유다. 본 프로젝트는 SVG 텍스트만 만들고, 픽셀로의 변환은 외부 도구에 위임한다.

### 1.3.4 왜 이 방식인가 — vector vs raster

이미지 생성에는 크게 두 방식이 있다.

| 방식 | 예시 라이브러리 | 저장 형태 | 확대 시 |
|---|---|---|---|
| **Raster (픽셀 기반)** | PIL/Pillow, OpenCV, matplotlib (기본) | 픽셀 격자 (PNG, JPG) | 깨짐 |
| **Vector (수식 기반)** | SVG, PDF, DXF | 좌표 + 도형 명령어 (텍스트) | 무한 확대 가능 |

GMP 도면은 다음 이유로 vector가 적합하다.

1. **무한 확대**: A0 출력부터 모니터 줌인까지 깨짐 없음
2. **편집 가능**: 텍스트라 좌표·색·라벨을 사후에 수정 가능 (Inkscape에서 열어 도면 손보기)
3. **CAD 호환**: SVG → DXF 변환이 텍스트 변환 수준으로 단순 (실제로 본 프로젝트 `scripts/svg_to_dxf.py` 가 30줄)
4. **의존성 0**: PIL이나 matplotlib을 설치할 필요 없음 — Python 표준 라이브러리만 사용
5. **버전 관리**: 텍스트라 git diff로 도면 변경점 추적 가능

### 1.3.5 한 줄 요약

> Drawing Agent는 그림을 그리는 프로그램이 아니라, **"여기에 직사각형, 저기에 글자"라고 적은 설명서(SVG 텍스트)를 작성하는 프로그램**이다. 그 설명서를 픽셀로 바꾸는 일은 OS/브라우저가 한다.

이 구조 덕분에 본 모듈은 외부 그래픽 라이브러리 의존성이 0이고, 어떤 환경에서도 동일한 도면을 재현할 수 있으며, 후속 CAD 변환이 단순하다.

## 1.4 처리 단계

크게 두 모듈, 여덟 단계.

```
solve()  ─ layout_solver.py ──── 좌표 계산 (Layout 객체 생성)
  ├ Stage A. 건물 영역 분할 (Aux 좌 / Process 중앙 / NC 우)
  ├ Stage B. Y축 9-stripe 분할 (복도·AL·공정대 띠)
  ├ Stage C. Process Row Room들의 폭 할당 (면적 비율 기반)
  ├ Stage D. Aux/NC 좌·우 stack 할당
  ├ Stage E. Airlock 배치 (위/아래 행 + 4-AL 코너)
  ├ Stage F. Equipment 그리드 packing
  └ Stage G. Door 좌표·회전·swing 결정

render() ─ renderer.py ──────── SVG 텍스트 생성
  └ Stage H. 13-layer Z-order 렌더링
```

## 1.5 결정론적 v1 — 그 다음은 RL

현재 구현은 **결정론적(deterministic)**이다. 동일한 입력에 대해 항상 동일한 출력을 낸다. 알고리즘적으로는 다음 두 가정을 따른다.

1. **strip-band 토폴로지**: 공정실은 가운데 두 줄, Auxiliary는 왼쪽 띠, NC는 오른쪽 띠.
2. **공정 순서 하드코딩**: mAb 공정의 표준 순서 (배지조제 → 시드 → 배양 → 수확 → 정제1 → 정제2)가 코드에 명시되어 있다.

이 두 가정 덕분에 v1은 단순하고 검증 가능하지만, modality가 바뀌면(예: 백신, ADC) 적용되지 않는다. 향후 강화학습(RL) 단계에서는 이 v1의 출력을 시작점(baseline)으로 두고 더 나은 좌표 배치를 탐색하게 된다.

---

# 2부 — 기술 상세

## 2.1 전체 데이터 흐름

```
URS (.json) ──► Rule Engine ──► RuleEngineOutput (= spec, 7-block)
                                       │
                                       ▼
                         floorplan.generate_floorplan(spec, W, H)
                                       │
                  ┌────────────────────┴────────────────────┐
                  ▼                                         ▼
         layout_solver.solve(spec, W, H)         renderer.render(spec, layout)
                  │                                         │
                  └──────► Layout (in-memory) ──────────────┘
                                       │
                                       ▼
                                 SVG (str) → 파일 저장
```

`Layout`은 dataclass다. RL 환경의 state·step에서 직접 참조할 수 있도록 plain Python 객체로 유지한다.

## 2.2 좌표계 및 단위

- **내부 작업 단위**: mm. `solve()`는 실측 mm로만 계산한다.
- **렌더 단위**: SVG user unit. `design_tokens.SCALE_MM_TO_UNIT = 0.016` 으로 변환 (`1 mm = 0.016 unit`).
- **원점**: 좌상단. SVG의 자연 좌표계와 일치 (y는 아래로 증가).
- **회전**: layout_solver는 `θ` 회전을 사용하지 않는다 (모든 직사각형 axis-aligned).
- **캔버스 패딩**: `CANVAS_PAD = 64` SVG unit. 건물 외곽선과 SVG viewBox 경계 사이의 여유.

## 2.3 Stage A — 건물 영역 분할

3분할 strip 토폴로지를 고정한다.

| 영역 | X 범위 (mm) | 비율 | 담는 Room |
|---|---|---|---|
| **Aux strip** (왼쪽) | `0 ~ 0.15W` | 15 % | Material Inlet, Material Storage, Gowning, IPC, CIP Supply, Waste Outlet 등 |
| **Core** (중앙) | `0.15W ~ 0.82W` | 67 % | Supply/Return Corridor, Process Rooms, Airlocks |
| **NC strip** (오른쪽) | `0.82W ~ W` | 18 % | Lobby, Office, Monitoring, Toilet, Visitor Corridor |

```python
aux_w = building_w_mm * 0.15
nc_w  = building_w_mm * 0.18
core_x0, core_x1 = aux_w, building_w_mm - nc_w
core_w = core_x1 - core_x0
```

## 2.4 Stage B — Y축 9-stripe band

`Core` 영역의 Y축을 10개 비정형 stripe로 분할한다.

| index | 영역 이름 | 비율 |
|---|---|---|
| 0 | Return Corridor (top) | 0.06 |
| 1 | AL-out row (top) | 0.07 |
| 2 | **Process Row (top)** | 0.17 |
| 3 | AL-in row (top) | 0.07 |
| 4 | **Supply Corridor (central)** | 0.10 |
| 5 | AL-in row (bottom) | 0.07 |
| 6 | **Process Row (bottom)** | 0.22 |
| 7 | AL-out row (bottom) | 0.07 |
| 8 | Return Corridor (bottom) | 0.10 |
| 9 | Footer band (NC strip 연동) | 0.07 |

비율의 합은 1.0이며 정규화되어 있다. 각 stripe의 Y 좌표는 누적합으로 결정된다.

```python
y_acc = 0.0
bands = []
for ratio in stripe_ratios:
    h = building_h_mm * ratio
    bands.append((y_acc, y_acc + h))
    y_acc += h
```

핵심 설계 의도:
- **Supply Corridor가 중앙 (band 4)**: 양압 공기가 위·아래 process row로 동시에 공급되도록 함.
- **AL-in row가 process row 안쪽**: 인원·자재 입구 AL이 supply corridor와 직접 인접.
- **AL-out row가 process row 바깥쪽**: 사용 후 공기·물자가 return corridor로 빠지는 경로.

## 2.5 Stage C — Process Row Room 폭 할당

각 Process Row에 들어가는 Room들은 **면적 비율로 가로폭을 자동 분배**한다.

```python
def _place_process_row(layout, room_by_id, row_ids, x0, y0, w, h):
    present = [r for r in row_ids if r in room_by_id]
    areas = [room_by_id[r].area_m2 for r in present]
    total = sum(areas)
    x = x0
    for rid, a in zip(present, areas):
        w_room = w * (a / total)         # 면적 비율로 가로폭 할당
        rect = Rect(x, y0, w_room, h)
        layout.rooms[rid] = PlacedRoom(room=room_by_id[rid], rect=rect)
        x += w_room
```

공정 순서 (좌→우)는 두 상수로 하드코딩되어 있다.

```python
TOP_ROW    = ["R_MEDIA_PREP", "R_BUFFER_PREP", "R_INOCULATION",
              "R_CELL_CULTURE", "R_HARVEST"]
BOTTOM_ROW = ["R_PURIFICATION_1", "R_PURIFICATION_2",
              "R_PREPARATION", "R_WASHING"]
```

**제약**: 두 Row 모두 같은 높이 stripe를 공유하므로, 각 Room의 세로 폭은 stripe 높이로 고정된다. 세로 폭 변동은 향후 작업 영역.

## 2.6 Stage D — Aux / NC 좌·우 stack

좌측 Aux strip과 우측 NC strip은 **면적 비율로 세로 분배**한다. (Stage C와 대칭, 축만 다름)

```python
AUX_LEFT_STACK = ["R_MATERIAL_INLET", "R_MATERIAL_STORAGE",
                  "R_EQUIPMENT_STORAGE", "R_CELL_BANK_STORAGE",
                  "R_DS_STORAGE", "R_IPC", "R_CIP_SUPPLY",
                  "R_GOWNING_FEMALE", "R_GOWNING_MALE",
                  "R_GOWNING_PROCESS", "R_WASTE_OUTLET",
                  "R_AUX_CORRIDOR"]

NC_RIGHT_STACK = ["R_LOBBY", "R_OFFICE", "R_MONITORING",
                  "R_TOILET_FEMALE", "R_TOILET_MALE", "R_LOUNGE",
                  "R_VISITOR_CORRIDOR"]
```

## 2.7 Stage E — Airlock 배치

3가지 케이스를 처리한다.

### Case E1 — 표준 케이스 (대부분의 AL)
AL의 in/out suffix(`_in` / `_out`)에 따라 어느 band에 들어갈지 결정.

```
PAL_in / MAL_in   → AL-in row (process row 안쪽)
PAL_out / MAL_out → AL-out row (process row 바깥쪽)
```

각 Process Room에 붙은 AL들을 그 Room의 폭 안에서 균등 분할한다.

```python
slot_w = proom.rect.w / len(als)
for i, al in enumerate(als):
    ax = proom.rect.x + i * slot_w + slot_w * 0.1
    aw = slot_w * 0.8
    layout.airlocks[al.id] = PlacedAirlock(
        airlock=al, rect=Rect(ax, y0, aw, h),
        attached_room_id=rid, side=side
    )
```

### Case E2 — Grade B + 4-AL 룸 (C4 Hard Constraint 시각화)

EU GMP Annex 1에 따라 Grade B + one-way Room은 4개 AL을 갖는다 (PAL/MAL × in/out). 이 경우 좌·우 **corner placement**로 분산한다.

```python
def _is_grade_b_four_al(room, all_als) -> bool:
    if room.clean_grade != "B":
        return False
    als = [a for a in all_als if a.connects_higher == room.id]
    return len(als) == 4

# corner placement (4-AL Grade B Room):
#   PAL 종류 → Room 좌측 1/3 (x = room.x + 0.05w)
#   MAL 종류 → Room 우측 1/3 (x = room.x + 0.65w)
```

이로써 인원/자재 동선 분리가 시각적으로 명확해진다.

### Case E3 — 양방향 AL (CAL/PAL/MAL without in/out suffix)

`_in`/`_out` 접미사가 없는 양방향 AL은 Supply Corridor 안의 작은 spot에 inline 배치한다.

```python
def _place_both_way_als(layout, spec, x0, y0, w, h):
    bw_als = [a for a in spec.airlocks if a.type in ("CAL","PAL","MAL")]
    slot_w = w / max(len(bw_als) + 1, 8)
    al_h = h * 0.55
    for i, al in enumerate(bw_als):
        ax = x0 + (i + 1) * slot_w - slot_w * 0.4
        ay = y0 + (h - al_h) / 2
        layout.airlocks[al.id] = PlacedAirlock(
            airlock=al, rect=Rect(ax, ay, slot_w * 0.8, al_h),
            attached_room_id=al.connects_higher, side="inline",
        )
```

## 2.8 Stage F — Equipment 그리드 packing

각 Process Room 내부에 장비를 packing한다. 알고리즘은 **first-fit row-major**다.

```python
def _place_equipment_grid(layout):
    wall_margin = 1500   # mm — 라벨 공간 포함
    eq_gap = 1000        # mm — Rule 10 장비 간격

    for proom in layout.rooms.values():
        equips = list(proom.room.equipment)
        if not equips:
            continue

        # 사용 가능 inner 영역 (Room - wall margin - 라벨용 4m 상단 여백)
        inner_x = proom.rect.x + wall_margin
        inner_y = proom.rect.y + wall_margin + 4000
        inner_w = max(proom.rect.w - 2 * wall_margin, 1000)
        inner_h = max(proom.rect.h - 2 * wall_margin - 4000, 1000)

        # row-major packing
        cx, cy, row_h = inner_x, inner_y, 0.0
        for eq in equips:
            ew, eh = eq.W_mm, eq.D_mm
            if cx + ew > inner_x + inner_w:    # 줄 끝 → 줄바꿈
                cx = inner_x
                cy += row_h + eq_gap
                row_h = 0.0
            if cy + eh > inner_y + inner_h:    # 영역 초과 → 마지막 장비 1개만 marker
                proom.equipment.append(PlacedEquipment(eq, Rect(cx, cy, ew, eh)))
                break
            proom.equipment.append(PlacedEquipment(eq, Rect(cx, cy, ew, eh)))
            cx += ew + eq_gap
            row_h = max(row_h, eh)
```

장비 순서는 `rule_10_equipment.py`에서 `process_step` 오름차순으로 정렬된 후 도착한다. 즉 첫 번째 장비가 좌상단, 공정 순서대로 우→하로 packing 된다.

**제약**: 회전 미지원, 장비 간 1000 mm gap 만 보장 (Rule 10), 벽과의 거리는 1500 mm 단일 값 (4방위 차등 없음).

## 2.9 Stage G — Door 좌표·회전·swing

각 `Adjacency` (relationship == "door") 에 대해:

### G1 — 공유 변 추정

```python
def _door_pos(a: Rect, b: Rect) -> tuple[float, float, float]:
    # 세로 인접 (a 위, b 아래) — 50 mm tolerance
    if abs(a.y2 - b.y) < 50 or abs(b.y2 - a.y) < 50:
        y = (a.y2 + b.y) / 2 if a.y < b.y else (b.y2 + a.y) / 2
        x = (max(a.x, b.x) + min(a.x2, b.x2)) / 2
        return x, y, 0       # rot = 0 (수평 도어)
    # 가로 인접
    if abs(a.x2 - b.x) < 50 or abs(b.x2 - a.x) < 50:
        x = (a.x2 + b.x) / 2 if a.x < b.x else (b.x2 + a.x) / 2
        y = (max(a.y, b.y) + min(a.y2, b.y2)) / 2
        return x, y, 90      # rot = 90 (수직 도어)
    # fallback: 중심 사이 중간점
    return (a.cx + b.cx) / 2, (a.cy + b.cy) / 2, 0
```

도어 폭은 `adjacency.door_size_mm` (기본 1000 mm).

### G2 — Swing 방향 (C10 Hard Constraint)

C10: 도어는 차압 흐름 방향(= 낮은 압력 쪽)으로 열려야 한다.

```python
def _resolve_swing(layout, adj: Adjacency) -> tuple[Optional[str], list[dict]]:
    # 1. Rule Engine이 결정한 값이 있으면 그대로
    if adj.door_swing_to:
        return adj.door_swing_to, []

    # 2. 없으면 차압 차이로 fallback
    p_from = _pressure_of(layout, adj.from_id)
    p_to   = _pressure_of(layout, adj.to_id)
    if abs(p_from - p_to) < 1e-6:
        # 3. 둘 다 같으면 모호 — annotation 경고
        return None, [{"type": "door_swing_ambiguous", ...}]
    # 차압이 큰 쪽 → 낮은 쪽으로 swing
    return (adj.to_id if p_from > p_to else adj.from_id), []
```

## 2.10 Stage H — SVG 13-layer Z-order

렌더링은 13개 Z-layer를 위→아래로 쌓는다. (DESIGN.md §5)

| Z | layer | 내용 |
|---|---|---|
| z0 | 배경 | 캔버스 fill |
| z1 | 마이너 그리드 | 1m 간격 가는 선 |
| z2 | 메이저 그리드 | 5m 간격 굵은 선 |
| z2b | **축선** | X/Y 축 marker + 실측 치수 chain (Room 경계에서 자동 추출) |
| z3 | 건물 외곽선 | 굵은 검정 |
| z4 | Room 채움 | Grade 색상 (KB 기반) |
| z5 | Room 테두리 | 벽 (3.5 stroke) |
| z6 | 도어 | 90° arc + door leaf |
| z7 | Airlock | 단일 대각선 + 검은 채움 삼각형 + 타입 라벨 |
| z8 | Equipment | 빨간 박스 + 2줄 라벨 (name / area) |
| z9 | **Flow arrows** | Personnel/Material/Waste 색상 코딩 (Phase 0 추가) |
| z10 | Room 라벨 | 평문 텍스트 + 흰색 halo |
| z11 | Boundary flow 라벨 | 외곽 4방위 Visitors/Material/Waste 색상 |
| z12 | 범례 + 타이틀블록 | 우측 legend / 하단 title |

`<g clip-path="url(#clip_R_xxx)">`로 각 Room별 clipPath를 정의해 장비 라벨이 Room 밖으로 새지 않게 보장한다.

## 2.11 알고리즘 복잡도

| Stage | 복잡도 | 비고 |
|---|---|---|
| A · B | O(1) | 고정 비율 분할 |
| C | O(\|TOP_ROW\| + \|BOTTOM_ROW\|) ≈ O(9) | 면적 비율 정렬 |
| D | O(\|AUX\|+\|NC\|) ≈ O(20) | 세로 분배 |
| E | O(\|AL\|) | AL 개수에 선형 |
| F | O(N_eq) | 각 Room의 장비 수 합 |
| G | O(\|adjacency\|) | 도어 = 인접 관계 수 |
| H | O(\|rooms\| + \|AL\| + \|eq\| + \|doors\|) | SVG 텍스트 누적 |

전체적으로 spec 크기에 선형. 단일 시나리오 처리 시간은 < 100 ms (M1 측정).

## 2.12 결정론 보장

다음이 모두 충족되면 같은 입력 → 항상 같은 출력:
1. `RuleEngineOutput`이 결정론적 (rule_engine의 모든 `apply()`가 무작위성 없음)
2. `dict` 순회 순서가 보존됨 (Python 3.7+ 보장)
3. 부동소수 연산이 동일 architecture에서 reproducible (mm → SVG unit 변환에 사소한 round 차이는 있을 수 있으나 시각 차이 없음)

테스트 `test_drawing_agent.py`의 smoke 테스트가 이 결정론을 확인한다.

## 2.13 현재의 한계 (논문에서 솔직하게 다룰 부분)

| # | 한계 | 영향 | 향후 작업 |
|---|---|---|---|
| 1 | Room 모양 = axis-aligned rectangle만 | 비정형 (L자, 다각형) 표현 불가 | polygon 지원 + path 기반 wall 렌더 |
| 2 | 공정 순서 하드코딩 (`TOP_ROW`/`BOTTOM_ROW`) | mAb 외 modality 적용 불가 | adjacency graph → topology 자동 산출 |
| 3 | Room 간 면적 합 ≠ 건물 면적 | 강제 fit으로 압축 또는 gap 발생 | 우선순위 기반 압축 정책 |
| 4 | 장비 회전 (θ) 미지원 | 가로/세로 footprint 고정 | (x, y, θ) 3-tuple action space (RL) |
| 5 | 4방위 clearance 차등 없음 | 청소·유틸리티 접근 모델링 못함 | Equipment.clearance_m 데이터 보강 |
| 6 | 다층 (floor > 1) 무시 | 단층 평면만 | floor별 Layout 분리 + 엘리베이터 연결 |
| 7 | 동선이 4종 (Sample/Equipment 없음) | ISPE 6종 표준 미충족 | FlowPaths schema 확장 |
| 8 | 동선 polyline 미생성 → shapely 교차 검사 불가 | clean ↔ dirty 공간 교차 자동 검증 불가 | flow_paths를 (x,y) polyline으로 렌더 + intersect 검사 |

## 2.14 RL과의 인터페이스

`Layout` 객체는 reward·RL env의 직접 입력으로 쓰인다.

```python
# src/reward/scorer.py
def score(spec: RuleEngineOutput, layout: Optional[Layout] = None) -> ScoreReport:
    # layout None  → Hard/Soft constraint 만 평가
    # layout 있음 → Geometric quality 추가
```

RL env (`src/rl/env.py`)는 `solve()`를 매 episode 시작 시 호출해 baseline Layout을 얻고, agent의 action으로 일부 Room/Equipment의 (x, y)를 수정한 뒤 reward를 다시 계산한다. v1 결정론적 Layout이 RL의 "초기 정책 = baseline policy" 역할을 한다.

---

## 부록 — 코드 진입점

- 시작 함수: `src/drawing_agent/floorplan.py::generate_floorplan(spec, W_mm, H_mm)`
- 좌표 결정: `src/drawing_agent/layout_solver.py::solve()`
- SVG 렌더: `src/drawing_agent/renderer.py::render()`
- 색상·치수 토큰: `src/drawing_agent/design_tokens.py`
- CLI 진입점: `python -m src.cli draw spec.json out.svg --width W --height H`

---

## 부록 — 인용 가능한 핵심 알고리즘 요약

> Drawing Agent v1은 3-band horizontal partition (Aux 0.15 : Core 0.67 : NC 0.18)과 Core 영역의 10-stripe vertical partition (return-AL-process-AL-supply-AL-process-AL-return-footer)을 결정론적으로 적용한 strip-band topology를 채택한다. Room 폭은 area_m2 비율로 분배되고, Airlock은 in/out suffix를 기준으로 process row 안쪽/바깥쪽 band에 자동 배치된다. 단, Grade B + 4-AL Room에는 corner placement (PAL 좌측·MAL 우측)가 적용된다. Equipment는 first-fit row-major packing으로 Room 내부 (wall_margin = 1.5 m, eq_gap = 1.0 m) 영역에 process_step 순서대로 배치한다. Door 좌표는 인접한 두 Room의 공유 변에서 ±50 mm tolerance로 자동 추출되며, swing 방향은 adjacency.door_swing_to를 우선하고 부재 시 차압 차이로 fallback한다 (EU GMP Annex 1 C10).

---

*문서 버전: v1 (2026-05-29). 다음 개정 트리거: layout_solver 알고리즘 변경 시 또는 RL이 v1을 대체할 때.*
