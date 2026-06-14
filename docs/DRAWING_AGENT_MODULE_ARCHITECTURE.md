# Drawing Agent 세부 모듈 아키텍처

> 목적: Rule Engine이 생성한 7-block spec을 받아 좌표 기반 GMP 도면 SVG로 변환하는
> Drawing Agent의 내부 모듈, 책임, 원리를 설명한다.  
> 5분 설명 영상, 팀장님 질의 대응, 논문 방법론 서술에 함께 사용할 수 있도록 작성했다.

---

## 1. 팀장님 질문에 대한 짧은 답변

질문:

> Layout의 좌표를 만들어내는 것은 Coordinate Planner라 할 수 있나요?  
> 좌표를 만들어 벡터적으로 표현하는 것, flow 화살표를 표시하는 것은 각각 어떤 모듈에서 작동하나요?

답변:

> 네. 개념적으로는 `Coordinate Planner`라고 불러도 됩니다.  
> 다만 현재 코드에서 독립 파일명이 `coordinate_planner.py`로 존재하는 것은 아니고,
> 그 역할은 주로 `src/drawing_agent/layout_solver.py`가 수행합니다.
> 즉 논문이나 발표에서는 **"Coordinate Planning layer is implemented inside the Layout Solver"**
> 또는 **"Layout Solver, including the coordinate planner"**라고 표현하는 것이 가장 정확합니다.
>
> 좌표를 벡터 도면으로 표현하는 작업은 `src/drawing_agent/renderer.py`의 `render()`가 담당합니다.
> 이 모듈은 `Layout` 객체의 mm 좌표를 SVG user coordinate로 변환하고, Room, 장비, 도어,
> 전실, 라벨, 범례, flow 화살표를 SVG 태그로 기록합니다.
>
> Flow 화살표는 `renderer.py` 안의 flow rendering 계층, 특히 `_emit_z9_flow_arrows()`가 담당합니다.
> 이 함수는 Rule Engine이 준 `spec.flow_paths`를 실제 배치 좌표에 매핑하여
> personnel, material, product, waste 동선을 색상별 SVG polyline/path로 표시합니다.

한 문장으로 요약하면:

> **Rule Engine은 "무엇을 배치해야 하는지"를 정의하고, Drawing Agent는 "그것을 어디에 놓고, 어떻게 벡터 도면으로 표현할지"를 해결한다.**

---

## 2. 전체 파이프라인에서 Drawing Agent의 위치

```text
URS
  |
  v
Rule Engine
  |
  | 7-block RuleEngineOutput
  | rooms, airlocks, adjacency, flow_paths, zones, constraints, rationale
  v
Drawing Agent
  |
  | Layout object with mm coordinates
  v
SVG Renderer
  |
  v
floorplan.svg
```

Rule Engine의 출력은 아직 도면이 아니다. 이 출력은 "도면에 들어가야 하는 설계 의미"를 담은
추상 명세다. 예를 들어 다음 정보는 들어 있다.

- 어떤 Room이 필요한가
- 각 Room의 면적, 청정등급, 차압, 장비 목록은 무엇인가
- 어떤 Room끼리 인접하거나 도어로 연결되어야 하는가
- PAL/MAL/CAL 전실은 어떤 Room에 연결되는가
- personnel, material, product, waste 동선은 어떤 순서인가
- process, auxiliary, NC 구역은 어떻게 나뉘는가

그러나 다음 정보는 Rule Engine 출력에 직접 들어 있지 않다.

- 각 Room의 실제 좌상단 좌표 `(x, y)`
- 각 Room의 실제 폭과 높이 `(w, h)`
- 장비가 Room 내부 어디에 놓이는지
- 도어가 벽의 어느 지점에 표시되는지
- flow 화살표가 SVG 좌표계에서 어떤 선분으로 그려지는지
- 이 모든 요소가 어떤 순서와 스타일로 SVG에 출력되는지

이 두 번째 목록을 해결하는 계층이 Drawing Agent다.

---

## 3. 모듈 책임 지도

| 개념적 모듈 | 현재 코드 위치 | 입력 | 출력 | 핵심 책임 |
|---|---|---|---|---|
| Drawing Orchestrator | `src/drawing_agent/floorplan.py` | `RuleEngineOutput` | `(svg, layout)` | enrich, building size resolve, solve, render 순서 제어 |
| Spec Adapter / Enricher | `src/drawing_agent/data/` | Rule Engine output, URS, fallback KB | 보강된 spec | 누락된 장비 치수, 정렬 순서, building dimension 보강 |
| Building Dimension Resolver | `src/drawing_agent/data/building.py` | spec, URS path | `width_mm`, `depth_mm` | 건물 실제 캔버스 크기 결정 |
| Layout Solver | `src/drawing_agent/layout_solver.py` | spec, building size | `Layout` | Room, corridor, airlock, door, equipment의 mm 좌표 생성 |
| Coordinate Planner | 현재는 `layout_solver.py` 내부 역할 | rooms, zones, adjacency, constraints | `Rect(x,y,w,h)` 집합 | 추상 배치 문제를 좌표 배치 문제로 변환 |
| Constraint Compiler | `src/drawing_agent/constraint_compiler.py` | spec, target rooms, canvas | CP-SAT model | hard/soft constraint를 정수 최적화 모델로 컴파일 |
| CP-SAT Solver | `src/drawing_agent/cpsat_solver.py` | compiled CP-SAT model | `Layout`, `SolveReport` | 최적화 기반 좌표 후보 생성 |
| SVG Renderer | `src/drawing_agent/renderer.py` | spec, `Layout` | SVG text | Layout 좌표를 벡터 도면 명령으로 변환 |
| Flow Renderer | `renderer.py`의 `_emit_z9_flow_arrows()` | `spec.flow_paths`, `Layout` | SVG flow paths | 4종 동선을 실제 좌표에 연결해 화살표로 표시 |
| Layout Validator | `src/drawing_agent/validators.py` | spec, `Layout` | violation list | 좌표 결과가 도면 레벨 제약을 지키는지 검증 |
| Design Token System | `src/drawing_agent/design_tokens.py` | style constants | colors, scale, stroke | 색상, 축척, 선 두께, 폰트, flow palette 단일화 |

---

## 4. 핵심 데이터 구조: `Layout`

Drawing Agent 내부에서 가장 중요한 중간 산출물은 SVG가 아니라 `Layout` 객체다.

`Layout`은 다음을 담는다.

- `building_w_mm`, `building_h_mm`: 건물 실제 크기
- `rooms`: Room id별 `PlacedRoom`
- `airlocks`: Airlock id별 `PlacedAirlock`
- `doors`: 도어 좌표와 회전 정보
- `annotations`: 모호한 door swing 등 진단 메타데이터

각 `PlacedRoom`은 다음과 같은 실제 좌표 사각형을 가진다.

```python
Rect(
    x=...,  # 좌상단 x, mm
    y=...,  # 좌상단 y, mm
    w=...,  # 폭, mm
    h=...,  # 높이, mm
)
```

따라서 Drawing Agent의 핵심 변환은 다음과 같이 정의할 수 있다.

```text
RuleEngineOutput
  -> semantic layout specification
  -> Layout
  -> metric coordinate representation
  -> SVG
  -> vector drawing representation
```

논문 문장으로는 다음처럼 표현할 수 있다.

> The Drawing Agent transforms the symbolic 7-block output of the Rule Engine into a metric `Layout` object, where each room, airlock, door, and equipment item is assigned a physical coordinate in millimeters. The SVG renderer then converts this coordinate-level representation into a vector drawing.

---

## 5. `floorplan.py`: Drawing Orchestrator

`floorplan.generate_floorplan()`은 Drawing Agent의 entrypoint다.

역할은 알고리즘 자체를 직접 수행하는 것이 아니라, 하위 모듈을 올바른 순서로 호출하는 것이다.

처리 순서:

```text
generate_floorplan(spec)
  |
  | 1. enrich_spec()
  |    Rule Engine output 보강
  |
  | 2. resolve_building_dims()
  |    건물 width/depth 결정
  |
  | 3. layout_solver.solve()
  |    좌표 기반 Layout 생성
  |
  | 4. renderer.render()
  |    SVG 텍스트 생성
  v
(svg, layout)
```

이 모듈은 발표에서 "Drawing Agent Controller" 또는 "Drawing Orchestrator"라고 설명하면 좋다.

---

## 6. `data/`: Spec Adapter와 4-tier Enrichment

Rule Engine의 출력은 추상 명세이므로, 도면 생성에 필요한 세부 값이 비어 있을 수 있다.
예를 들어 장비의 `bbox_m`, 공정 순서 `sort_order`, 연결 정보 `connects_to`,
건물 크기 등이 항상 동일한 출처에서 오지는 않는다.

그래서 Drawing Agent는 값을 찾을 때 다음 우선순위를 따른다.

```text
Tier 1. RuleEngineOutput
Tier 2. examples/URS
Tier 3. derive logic
Tier 4. manual fallback / drawing_agent KB
```

이 구조의 장점:

- Rule Engine이 나중에 더 많은 필드를 채우면 자동으로 그것을 우선 사용한다.
- 현재 Rule Engine이 아직 제공하지 않는 값은 Drawing Agent가 보수적으로 보강한다.
- 데이터 출처를 추적할 수 있어 논문과 검증 보고서에서 설명이 가능하다.

즉 이 계층은 좌표를 직접 만들지는 않지만, Coordinate Planner가 쓸 수 있는 입력을 완성한다.

---

## 7. `layout_solver.py`: Layout Solver와 Coordinate Planner

### 7.1 이 모듈을 Coordinate Planner라 불러도 되는가

개념적으로는 가능하다. 이 모듈의 핵심 기능이 바로 추상 spec을 실제 좌표로 변환하는 것이기 때문이다.

다만 코드 구조상 공식 파일명은 `layout_solver.py`다. 그러므로 용어를 구분하면 가장 정확하다.

| 표현 | 권장 여부 | 이유 |
|---|---:|---|
| Layout Solver | 강력 권장 | 코드 파일명과 역할이 일치 |
| Coordinate Planner | 권장 | 좌표 생성 역할을 설명하는 개념명 |
| Coordinate Planner module | 조건부 | 독립 파일은 아니므로 "module"보다 "layer/role"이 정확 |
| Drawing Agent's coordinate planner | 권장 | Drawing Agent 내부 역할로 설명할 때 자연스러움 |

가장 좋은 표현:

> **The coordinate planning role is implemented in the Layout Solver.**

한국어 표현:

> **좌표 계획기(Coordinate Planner)는 독립 파일로 분리되어 있지는 않지만, 현재 `layout_solver.py` 내부에서 Layout Solver의 핵심 기능으로 구현되어 있다.**

### 7.2 Layout Solver가 하는 일

Layout Solver는 다음 문제를 푼다.

```text
입력:
  - rooms: 면적, 등급, 카테고리, 장비 목록
  - zones: process / auxiliary / NC
  - adjacency: 도어와 인접 관계
  - airlocks: PAL/MAL/CAL
  - constraints: 복도 폭, 장비 간격, 도어 조건
  - building size: W x D mm

출력:
  - Room별 Rect(x, y, w, h)
  - Airlock별 Rect(x, y, w, h)
  - Equipment별 Rect(x, y, w, h)
  - Door별 위치, 회전, swing 방향
```

즉 Layout Solver는 "그릴 내용"을 직접 그리는 것이 아니라,
"그릴 대상의 위치와 크기"를 계산한다.

### 7.3 현재 좌표 생성 원리

현재 구현은 두 계열을 함께 갖는다.

첫째, 결정론적 heuristic 배치:

- 건물을 좌측 Auxiliary, 중앙 Process, 우측 NC 구역으로 나눈다.
- 중앙 Process 구역에는 Supply Corridor와 Return Corridor를 배치한다.
- 공정실은 공정 순서 또는 동적 분류 결과에 따라 상하 row와 zone band에 배치된다.
- Room 면적과 건물 크기를 이용해 폭과 높이를 정한다.
- Airlock은 연결된 Room의 경계 또는 내부 가장자리에 부착한다.
- 장비는 Room 내부 안전 영역 안에 row-major 또는 fit-grid 방식으로 배치한다.
- Door는 adjacency와 실제 공유 벽을 보고 위치와 회전을 정한다.

둘째, CP-SAT 기반 최적화 배치:

- `constraint_compiler.py`가 방 크기, 캔버스, 겹침 금지, zone, adjacency, objective를 정수 변수 모델로 변환한다.
- `cpsat_solver.py`가 OR-Tools CP-SAT solver로 좌표 해를 찾는다.
- 찾은 해는 다시 기존 `Layout` 객체로 변환된다.

이 구조의 중요한 장점은 renderer가 heuristic solver와 CP-SAT solver를 구분하지 않아도 된다는 점이다.
어떤 방식으로 좌표를 만들든 최종적으로 `Layout`만 맞으면 같은 renderer로 SVG를 만들 수 있다.

### 7.4 장비 좌표 생성

장비 배치는 `layout_solver.py`의 `_place_equipment_grid()` 계열에서 수행된다.

원리:

- Room 내부에서 라벨, 벽, Airlock과 겹치지 않는 안전 영역을 먼저 계산한다.
- 장비 목록을 공정 순서 또는 입력 순서대로 가져온다.
- 장비 간격과 벽 여백을 고려해 row-major packing을 시도한다.
- 들어가지 않으면 장비 시각 크기를 줄이거나 fit-grid로 재배치한다.
- 최종적으로 각 장비는 `PlacedEquipment(eq, Rect(...))` 형태로 `PlacedRoom.equipment`에 저장된다.

중요한 구분:

- 장비를 "어디에 놓을지"는 Layout Solver 책임이다.
- 장비 박스를 "빨간 테두리 SVG로 어떻게 그릴지"는 Renderer 책임이다.

### 7.5 도어 좌표와 swing 방향

도어 배치는 `layout_solver.py`의 `_place_doors()` 계열에서 수행된다.

원리:

- `spec.adjacency`의 연결 관계를 읽는다.
- passthrough-only는 도어로 그리지 않는다.
- Room과 Corridor가 실제로 맞닿는 벽을 찾는다.
- 공유 벽 위에 도어 중심 좌표와 회전값을 계산한다.
- `door_swing_to`가 있으면 이를 우선 사용한다.
- 없으면 양쪽 Room의 차압을 비교하여 높은 압력에서 낮은 압력 방향으로 swing을 추론한다.
- 판단이 모호하면 `layout.annotations`에 경고를 남긴다.

이 단계도 Coordinate Planning에 속한다. 아직 SVG를 그리는 것이 아니라,
도어의 좌표와 방향이라는 geometry 정보를 만든다.

---

## 8. `constraint_compiler.py`와 `cpsat_solver.py`: 최적화 기반 Coordinate Planning

Heuristic solver는 빠르고 설명하기 쉽지만, 모든 제약을 최적으로 만족하는 배치를 보장하지는 않는다.
그래서 CP-SAT 기반 경로가 추가되어 있다.

### 8.1 Constraint Compiler

`constraint_compiler.py`는 배치 문제를 수학적 제약 모델로 바꾼다.

예:

- 각 Room의 x, y, w, h를 정수 격자 변수로 둔다.
- 모든 Room이 캔버스 안에 있어야 한다.
- Room끼리는 겹치면 안 된다.
- 특정 zone의 Room은 특정 x 범위에 있어야 한다.
- adjacency pair는 너무 멀어지면 안 된다.
- Supply Corridor와 Return Corridor의 직접 연결을 피한다.
- P-series surrogate objective로 flow와 compactness를 반영한다.

이 모듈은 "문제를 푸는" 모듈이 아니라 "풀 수 있는 형태로 번역하는" 모듈이다.

### 8.2 CP-SAT Solver

`cpsat_solver.py`는 컴파일된 모델을 OR-Tools CP-SAT solver로 푼다.

출력:

- `Layout`: renderer가 사용할 좌표 결과
- `SolveReport`: status, objective, solve time, grid resolution 등

논문에서는 이 계층을 다음처럼 표현할 수 있다.

> For optimization-based variants, the Drawing Agent compiles the spatial placement problem into a CP-SAT model, where room positions are represented as integer grid variables and GMP layout rules are encoded as hard or soft constraints. The solver output is converted back into the common `Layout` representation, enabling the same rendering pipeline to be reused.

---

## 9. `renderer.py`: Vector/SVG Renderer

Renderer는 좌표를 새로 결정하지 않는다. 이미 계산된 `Layout`을 받아 SVG 텍스트로 변환한다.

핵심 함수:

```python
render(spec, layout, flow_mode="full") -> str
```

입력:

- `spec`: 등급, 이름, flow paths, metadata
- `layout`: 실제 좌표가 들어 있는 Room, Airlock, Door, Equipment

출력:

- `<svg ...> ... </svg>` 형태의 문자열

### 9.1 벡터적으로 표현한다는 의미

이 프로젝트는 픽셀 이미지를 직접 생성하지 않는다.
`renderer.py`는 다음과 같은 SVG 명령어를 텍스트로 작성한다.

```xml
<rect x="..." y="..." width="..." height="..." fill="..." stroke="..." />
<line x1="..." y1="..." x2="..." y2="..." />
<path d="M ... L ... L ..." marker-end="url(#arrow-product)" />
<text x="..." y="...">Room Name</text>
```

이 명령어는 브라우저, macOS Preview, Inkscape, Illustrator, CAD 변환기 등이 해석하여 화면에 그린다.
따라서 Drawing Agent는 raster image generator가 아니라 vector drawing instruction generator다.

### 9.2 mm 좌표에서 SVG 좌표로 변환

Layout Solver는 mm 단위로 좌표를 만든다.
Renderer는 `design_tokens.py`의 scale factor를 사용해 이를 SVG user unit으로 변환한다.

```text
Layout Rect in mm
  -> T.mm(...)
  -> SVG x, y, width, height
```

이 분리는 중요하다.

- Layout Solver는 실제 도면의 물리 좌표를 다룬다.
- Renderer는 화면과 파일에 표현되는 vector coordinate를 다룬다.

### 9.3 SVG Z-order

Renderer는 도면 요소를 일정한 순서로 쌓는다.

```text
z0  background
z1  minor grid
z2  major grid
z2b architectural axes
z3  building outline
z4  room fill
z5  room border / wall
z6  equipment
z7  doors and swing arc
z8  airlocks
z9  flow arrows
z10 labels
z11 boundary flow labels
z12 legend and title block
```

이 순서가 중요한 이유:

- grid가 Room 위에 올라오면 도면이 지저분해진다.
- Room fill이 wall보다 나중에 그려지면 벽선이 사라진다.
- flow arrow가 label보다 위에 있으면 글자를 가린다.
- 장비와 Airlock은 Room 내부에서 clipping되어야 한다.

즉 Renderer는 단순히 "그림을 그리는 함수"가 아니라,
건축 도면의 가독성을 위한 layer compositor 역할도 한다.

---

## 10. Flow Renderer: 동선 화살표 표시 모듈

Flow 화살표는 `renderer.py` 안의 `_emit_z9_flow_arrows()`가 담당한다.

입력 데이터:

```text
spec.flow_paths.personnel_entry
spec.flow_paths.personnel_exit
spec.flow_paths.material_entry
spec.flow_paths.waste_exit
spec.flow_paths.product_process_order
```

처리 원리:

1. 각 flow path의 node id를 읽는다.
2. node id가 Room이면 `layout.rooms[node].rect`의 중심점을 찾는다.
3. node id가 Airlock이면 `layout.airlocks[node].rect`의 중심점을 찾는다.
4. 외부 출입구나 elevator node는 건물 외곽 포트 또는 boundary label로 처리한다.
5. 얻은 좌표들을 polyline으로 연결한다.
6. flow 종류별 색상과 offset을 적용한다.
7. SVG marker를 사용해 화살촉을 붙인다.
8. 같은 path가 중복되면 signature로 제거한다.

Flow 종류:

| Flow | 의미 | Renderer key |
|---|---|---|
| Personnel | 작업자 출입 동선 | `personnel` |
| Material | 자재 반입 동선 | `material` |
| Product | 제품/공정 진행 동선 | `product` |
| Waste | 폐기물 반출 동선 | `waste` |

중요한 점:

- Flow path의 논리적 순서는 Rule Engine이 제공한다.
- Flow path를 실제 SVG 좌표에 매핑하는 것은 Renderer가 수행한다.
- Flow 화살표는 좌표 생성이 아니라 "좌표 기반 시각화"에 속한다.

논문 표현:

> Flow visualization is performed after coordinate generation. The renderer maps each symbolic flow node to the center of its placed room or airlock and emits color-coded SVG polylines with directional arrow markers.

---

## 11. `validators.py`: Layout-level 검증

Renderer가 SVG를 만들기 전후로, `validate_layout()`은 좌표 결과가 실제 도면 제약을 만족하는지 검사한다.

검사 예:

- Grade D Room이 D corridor에 실제로 맞닿는가
- NC-D gateway가 NC corridor와 D corridor 양쪽에 맞닿는가
- D-C gateway가 D corridor와 Supply corridor 양쪽에 맞닿는가
- 비전실 Room끼리 직접 door가 뚫려 있지는 않은가
- 모든 Room에 접근 가능한 door가 있는가
- 장비가 Airlock과 겹치지는 않는가
- URS 면적 비율과 도면 면적 비율이 지나치게 어긋나지는 않는가

이 모듈은 좌표를 만들지는 않는다. 대신 좌표가 GMP 도면으로서 말이 되는지 확인한다.

---

## 12. 모듈 간 책임 경계

아래 구분이 발표와 논문에서 가장 중요하다.

| 질문 | 책임 모듈 | 설명 |
|---|---|---|
| 어떤 Room이 필요한가? | Rule Engine | URS와 KB, GMP rule로 결정 |
| Room의 청정등급과 면적은? | Rule Engine | `rooms[]`에 기록 |
| Room 간 인접 관계는? | Rule Engine | `adjacency[]`에 기록 |
| Flow path의 논리적 순서는? | Rule Engine | `flow_paths`에 기록 |
| Room을 실제 어디에 놓을 것인가? | Layout Solver / Coordinate Planner | `Rect(x,y,w,h)` 생성 |
| 장비를 Room 안 어디에 놓을 것인가? | Layout Solver / Coordinate Planner | `PlacedEquipment.rect` 생성 |
| 도어를 벽 어디에 표시할 것인가? | Layout Solver / Coordinate Planner | `PlacedDoor` 생성 |
| 좌표를 SVG로 어떻게 표현할 것인가? | SVG Renderer | `<rect>`, `<path>`, `<text>` 생성 |
| Flow를 화살표로 어떻게 표시할 것인가? | Flow Renderer | flow node를 좌표화하고 polyline 출력 |
| 도면 좌표가 제약을 만족하는가? | Layout Validator | 좌표 기반 violation 검사 |

---

## 13. 5분 설명 영상 구성안

### 0:00-0:40 문제 정의

"Rule Engine은 GMP 기준에 따라 어떤 방, 전실, 장비, 동선이 필요한지 7-block spec으로 생성합니다.
하지만 이 spec에는 실제 좌표가 없습니다. Drawing Agent는 이 추상 명세를 실제 도면 좌표와 SVG 벡터 도면으로 변환합니다."

### 0:40-1:20 전체 구조

```text
Rule Engine output
  -> Spec Adapter
  -> Layout Solver / Coordinate Planner
  -> SVG Renderer
  -> Layout Validator
  -> floorplan.svg
```

강조할 말:

"여기서 Coordinate Planner는 Layout Solver 내부의 핵심 역할입니다. spec에 있는 Room과 adjacency를 읽고,
각 요소의 x, y, width, height를 mm 단위로 결정합니다."

### 1:20-2:20 Coordinate Planner 설명

예시:

"배지조제실, 세포배양실, 정제실 같은 공정 Room은 process zone에 배치하고,
사무실과 로비는 NC zone에 배치합니다. PAL/MAL/CAL은 연결된 Room 경계에 붙이고,
장비는 Room 내부 안전 영역 안에 간격을 두고 배치합니다. 이 결과가 `Layout` 객체입니다."

화면에 보여줄 자료:

- `RuleEngineOutput` JSON 일부
- `Layout`의 `Rect(x,y,w,h)` 예시
- Room box가 좌표로 배치되는 도식

### 2:20-3:10 SVG Renderer 설명

"Renderer는 좌표를 새로 정하지 않습니다. Layout Solver가 만든 좌표를 SVG 명령어로 바꿉니다.
Room은 `<rect>`, 도어와 flow는 `<path>`, 라벨은 `<text>`로 표현됩니다.
그래서 출력은 픽셀 이미지가 아니라 확대해도 깨지지 않는 벡터 도면입니다."

화면에 보여줄 자료:

- SVG 코드 한 줄
- 실제 도면 화면
- zoom-in해도 깨지지 않는 장면

### 3:10-4:00 Flow Renderer 설명

"Flow Renderer는 Rule Engine의 `flow_paths`를 실제 좌표와 연결합니다.
예를 들어 product process order가 Media Prep, Inoculation, Cell Culture 순서라면,
각 Room 중심 좌표를 찾아 주황색 화살표로 연결합니다.
Personnel, material, product, waste는 서로 다른 색상과 offset을 사용해 겹치지 않게 표시합니다."

화면에 보여줄 자료:

- `flow_paths.product_process_order`
- 방 중심점을 연결하는 polyline
- 색상별 flow arrow

### 4:00-4:40 검증 계층

"마지막으로 Layout Validator가 생성된 좌표가 실제 GMP 도면으로 타당한지 확인합니다.
예를 들어 Room이 복도와 맞닿는지, door가 있는지, 장비가 Airlock과 겹치지 않는지 검사합니다."

### 4:40-5:00 마무리

"따라서 이 시스템은 Rule Engine이 설계 의미를 만들고, Drawing Agent가 좌표와 벡터 표현을 생성하며,
Validator가 도면의 공간적 타당성을 확인하는 구조입니다."

---

## 14. 논문용 방법론 서술 초안

아래 문단은 논문 본문에 거의 그대로 사용할 수 있는 표현이다.

### Korean draft

본 연구의 Drawing Agent는 Rule Engine이 생성한 7-block 구조화 명세를 입력으로 받아,
이를 물리 좌표 기반의 2차원 도면으로 변환한다. Rule Engine의 출력은 Room, Airlock,
Adjacency, Flow Path, Zone, Constraint, Rationale을 포함하지만, 개별 공간 요소의
절대 좌표는 포함하지 않는다. 따라서 Drawing Agent는 먼저 4-tier data enrichment를 통해
장비 치수, 공정 순서, 건물 크기 등 누락 가능성이 있는 도면 생성 값을 보강한다.
이후 Layout Solver가 Coordinate Planner의 역할을 수행하여 각 Room, Airlock, Door,
Equipment에 대해 mm 단위의 `Rect(x, y, w, h)` 좌표를 산정한다. 이때 zone partition,
corridor topology, adjacency, door swing, equipment clearance와 같은 GMP 공간 제약이
좌표 생성 과정에 반영된다. 생성된 좌표는 공통 중간 표현인 `Layout` 객체에 저장되며,
SVG Renderer는 이 `Layout`을 입력으로 받아 Room, 장비, 도어, 전실, 라벨, flow arrow를
SVG vector primitives로 변환한다. Flow visualization은 Rule Engine의 symbolic
`flow_paths`를 배치된 Room 또는 Airlock 중심 좌표에 매핑한 뒤, 동선 종류별 색상과
방향성 marker를 가진 SVG polyline으로 출력한다. 마지막으로 Layout Validator는 생성된
좌표가 복도 인접성, door 접근성, Airlock-장비 겹침 방지 등 도면 수준의 공간 제약을
만족하는지 검증한다.

### English draft

The Drawing Agent converts the structured 7-block specification produced by the Rule Engine into a coordinate-level two-dimensional facility drawing. While the Rule Engine output specifies rooms, airlocks, adjacency relationships, flow paths, zones, constraints, and rationales, it does not directly include the absolute coordinates of each spatial element. The Drawing Agent therefore first performs a 4-tier data enrichment step to resolve missing drawing parameters such as equipment bounding boxes, process ordering, and building dimensions. The Layout Solver then acts as the coordinate planning layer, assigning millimeter-level rectangular coordinates, `Rect(x, y, w, h)`, to rooms, airlocks, doors, and equipment. During this process, GMP-relevant spatial constraints such as zone partitioning, corridor topology, adjacency, door swing direction, and equipment clearance are incorporated into the placement logic. The generated coordinate representation is stored in a common `Layout` object. The SVG Renderer subsequently transforms this `Layout` into vector primitives, including room rectangles, equipment boxes, doors, airlock symbols, labels, legends, and flow arrows. Flow visualization is performed by mapping symbolic nodes in `flow_paths` to the centers of placed rooms or airlocks and emitting color-coded SVG polylines with directional markers. Finally, the Layout Validator checks whether the generated coordinates satisfy drawing-level spatial constraints such as corridor adjacency, door accessibility, and avoidance of airlock-equipment overlap.

---

## 15. 발표용 용어 추천

| 한국어 | 영어 | 사용 맥락 |
|---|---|---|
| 룰엔진 | Rule Engine | URS에서 설계 의미를 생성 |
| 7-block 명세 | 7-block specification | Drawing Agent 입력 |
| 드로잉 에이전트 | Drawing Agent | 좌표 생성과 SVG 생성 전체 |
| 도면 오케스트레이터 | Drawing Orchestrator | `floorplan.py` |
| 명세 보강기 | Spec Enricher / Data Adapter | `data/` |
| 배치 솔버 | Layout Solver | `layout_solver.py` |
| 좌표 계획기 | Coordinate Planner | Layout Solver 내부 역할 |
| 제약 컴파일러 | Constraint Compiler | `constraint_compiler.py` |
| 최적화 솔버 | CP-SAT Solver | `cpsat_solver.py` |
| SVG 렌더러 | SVG Renderer | `renderer.py` |
| 동선 렌더러 | Flow Renderer | `_emit_z9_flow_arrows()` |
| 도면 검증기 | Layout Validator | `validators.py` |

권장 표현:

```text
Drawing Agent consists of a spec enrichment layer, a layout solver that performs coordinate planning, an SVG renderer for vector representation, a flow renderer for visualizing GMP paths, and a layout validator for spatial compliance checks.
```

한국어:

```text
Drawing Agent는 명세 보강 계층, 좌표 계획을 수행하는 Layout Solver, 벡터 표현을 담당하는 SVG Renderer, GMP 동선을 표시하는 Flow Renderer, 공간 제약을 검증하는 Layout Validator로 구성된다.
```

---

## 16. 코드 추적 표

| 설명할 내용 | 함수 또는 파일 |
|---|---|
| 전체 Drawing Agent 진입점 | `src/drawing_agent/floorplan.py::generate_floorplan` |
| Rule Engine 출력 보강 | `src/drawing_agent/data::enrich_spec` |
| 건물 크기 결정 | `src/drawing_agent/data/building.py::resolve_building_dims` |
| 결정론적 좌표 생성 | `src/drawing_agent/layout_solver.py::solve` |
| GMP gradient 배치 | `src/drawing_agent/layout_solver.py::_solve_gmp_gradient` |
| 장비 내부 배치 | `src/drawing_agent/layout_solver.py::_place_equipment_grid` |
| 도어 좌표와 swing | `src/drawing_agent/layout_solver.py::_place_doors`, `_resolve_swing` |
| CP-SAT 모델 생성 | `src/drawing_agent/constraint_compiler.py` |
| CP-SAT 해 계산 | `src/drawing_agent/cpsat_solver.py` |
| SVG 전체 렌더링 | `src/drawing_agent/renderer.py::render` |
| 장비 SVG 출력 | `src/drawing_agent/renderer.py::_emit_z8_equipment` |
| Flow 화살표 출력 | `src/drawing_agent/renderer.py::_emit_z9_flow_arrows` |
| Flow node 좌표 매핑 | `src/drawing_agent/renderer.py::_flow_point` |
| Layout 검증 | `src/drawing_agent/validators.py::validate_layout` |
| 색상, 축척, 선두께 | `src/drawing_agent/design_tokens.py` |

---

## 17. 주의할 표현

피해야 할 표현:

- "Rule Engine이 도면 좌표를 만든다."
- "Renderer가 배치를 결정한다."
- "Flow Renderer가 동선을 새로 계산한다."
- "SVG는 이미지 파일이라 픽셀을 생성한다."
- "Coordinate Planner가 별도 파일로 구현되어 있다."

권장 표현:

- "Rule Engine은 좌표 이전의 설계 의미를 생성한다."
- "Layout Solver가 좌표 배치를 결정한다."
- "Coordinate Planner는 Layout Solver 내부의 역할명이다."
- "Renderer는 이미 생성된 좌표를 SVG vector primitive로 변환한다."
- "Flow Renderer는 Rule Engine의 flow path를 실제 좌표에 매핑하여 표시한다."
- "SVG는 픽셀이 아니라 벡터 명령어의 텍스트 표현이다."

---

## 18. 결론

Drawing Agent는 단순한 그림 출력기가 아니라, 세 단계의 변환기를 포함한다.

```text
1. Semantic enrichment
   Rule Engine output을 도면 생성에 충분한 spec으로 보강

2. Coordinate planning
   Layout Solver가 Room, Airlock, Door, Equipment의 mm 좌표 생성

3. Vector rendering
   SVG Renderer가 좌표 기반 Layout을 vector drawing으로 표현
```

따라서 "layout의 좌표를 만들어내는 것은 Coordinate Planner라고 할 수 있는가"라는 질문에는
다음처럼 답하는 것이 가장 정확하다.

> **그렇다. 다만 현재 구현에서는 Coordinate Planner가 별도 파일로 분리되어 있는 것이 아니라, Layout Solver 내부의 핵심 역할로 구현되어 있다.**

