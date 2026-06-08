# Drawing Agent 진행 공유

> Rule Engine이 출력한 **7-block spec** (rooms/airlocks/adjacency/flow_paths/zones/constraints/rationale)을 받아 **실측 mm 좌표 기반 2D 도면**으로 변환하는 에이전트.
> *(README 본문에서 "Documentation Agent"라고 부른 부분과 동일 — 호칭 통일 필요)*

---

## 0) Current Status — 2026-06-09

팀장님 URS 1~5 기준 최종 고도화가 Drawing Agent에 반영되었다.

### 최신 동작
- `src.cli draw`는 `--seed`, `--variant`, `--variants`, `--report`를 지원한다.
- `output/audit_0608/urs_0607-{1..5}_final_v{1..3}.svg` 형태로 URS당 3개
  layout variant를 생성한다.
- `src.drawing_agent.validators.validate_layout`가 생성된 `Layout`을 geometric하게
  검증하고, JSON report를 남긴다.
- Product flow 색상은 Orange(`#F97316`)로 Personnel과 분리된다.
- full flow renderer는 같은 색 lane fan-out을 제거하고, 연결된 SVG path로 그린다.
- D-zone room은 corridor 인접을 유지하면서 미배치 흰 공간 없이 zone 폭을 채운다.
- 장비는 PAL/MAL/CAL 전실과 겹치지 않는 안전 영역에 배치된다.
- Legend는 우측 정보 패널로 확장되어 canvas 크기/면적, room/corridor/airlock/door
  count, modality를 표시한다.

### 최신 검증
- 팀장님 URS 1~5 x 3 variants = 15개 도면 생성.
- 15개 validation hard error 0.
- 15개 SVG XML parse 정상.
- `python3 -m pytest tests/test_layout_validation.py tests/test_drawing_agent.py`
  → 10 passed.

### 현재 남은 이슈
- 일부 report warning은 room area ratio 편차다. hard constraint, 전실/장비 겹침,
  flow 색/중복/끊김, 빈 공간, legend overflow는 우선 수정 완료.
- 다음 고도화 후보는 area-ratio objective 강화(W4~W7)와 full-flow branch의 더 높은
  수준의 시각 요약/토글이다.

---

## 1) 개념 설명

### 입력 (Rule Engine output, 7 blocks)
좌표 없이 **"무엇이 / 어디에 / 어떤 관계로"** 만 정의된 추상 명세입니다.

| 블록 | 내용 | Drawing Agent 활용 |
|---|---|---|
| `rooms[]` | Room별 등급, 면적, 차압, 장비 리스트 | **면적·등급별 색상 적용** |
| `airlocks[]` | PAL/MAL/CAL, in/out, cascade/sink/bubble | **공정 Room 상하단에 배치** |
| `adjacency[]` | Room↔Room 그래프 (door/wall/passthrough, swing 방향) | **도어 위치·회전·열림방향** |
| `flow_paths` | personnel/material/waste/product 4종 동선 | (향후) 동선 화살표 오버레이 |
| `zones` | process / auxiliary / NC 구역 그룹핑 | **좌측 Aux / 중앙 Process / 우측 NC 띠 분할** |
| `constraints` | 복도 폭, AL 크기, 장비 간격 등 정량 룰 | 좌표 산정의 하한값 |
| `rationale[]` | 룰 트레이스 (감사/디버깅용) | 도면 메타 주석 |

### 출력
- **결정론적 SVG 도면** (브라우저/CAD에서 열림)
- 동시에 **`Layout` 객체** (RL/Reward가 다시 받아 채점·재학습)

### 처리 전략 (v1, 결정론적)
**BIG/SOM 컨셉 다이어그램 풍의 정형 토폴로지**를 시작점으로 사용:

```
┌──────── BUILDING bbox ──────────────────────────────┐
│ ┌──────────────────────────────────────────────┐ ┌─┐ │
│ │ Return Corridor (top)                        │ │ │ │
│ │ ┌────┐┌────┐┌────┐  AL-out row              │ │ │ │
│Aux ┌────┐┌────┐┌────┐  Process row (top)     │ │NC│ │
│stack ┌────┐┌────┐┌────┐  AL-in row           │ │stack│
│ │ ════ Supply Corridor ════════════════════════│ │ │ │
│ │ ┌────┐┌────┐┌────┐  AL-in row              │ │ │ │
│ │ ┌────┐┌────┐┌────┐  Process row (bottom)   │ │ │ │
│ │ ┌────┐┌────┐┌────┐  AL-out row             │ │ │ │
│ │ Return Corridor (bottom)                    │ │ │ │
│ └──────────────────────────────────────────────┘ └─┘ │
└──────────────────────────────────────────────────────┘
```

- **9-stripe band** 비율로 Y축 분할
- 좌(Aux 15%) / 중(Process 67%) / 우(NC 18%) 로 X축 분할
- Process Row 내 Room들은 **면적 비율로 가로폭 자동 분배**

→ 이 v1은 **결정론적 stub** 입니다. RL이 이걸 시작점으로 더 좋은 후보를 학습하는 구조.

---

## 2) 코드화 진행 현황

### 디렉토리 구조
```
src/drawing_agent/
├── floorplan.py        22줄  ← entrypoint (solve + render 호출)
├── layout_solver.py   419줄  ← 7-block → 좌표 변환 로직 ★ 핵심
├── renderer.py        475줄  ← Layout → SVG (스타일·도어·라벨)
└── design_tokens.py    82줄  ← Grade별 색상·폰트·치수 토큰 (DESIGN.md 연동)
                       ────
                       998줄
```

### 동작 검증
| 검증 항목 | 상태 |
|---|---|
| 4종 시나리오 URS 입력 (baseline / small+aseptic / large multi-product / closed-system) | ✅ 모두 SVG 출력 |
| Rule Engine → Drawing Agent end-to-end CLI 파이프라인 | ✅ `python -m src.cli rule-engine ... && draw ...` |
| 시나리오별 시각적 차이 발생 | ✅ Airlock 수 (5 ~ 17개), Room 수 (25 ~ 29개) 등 명확한 차이 |
| Hard Constraint (C1~C10) 위반 시 rationale 로깅 | ✅ `--no-strict` 모드 |
| 출력 Layout 객체 → Reward 함수 입력 가능 | ✅ Step 9 reward 함수와 인터페이스 일치 |

### 완료된 기능
- Aux/Process/NC zone 3분할 배치
- Process Row 면적 비율 자동 분배 (Room이 늘어나도 자동 대응)
- Airlock in/out 분리 배치, CAL/PAL/MAL은 supply corridor 내 inline
- Door 좌표·회전 산출 (adjacency.swing_to 기반)
- Equipment grid 배치 (Room 내부 1000mm 간격, 벽 600~1200mm offset)
- Grade별 배경색·범례·차압 화살표 SVG 렌더링

### 아직 v1 stub인 부분
- Room 간 **빈 공간(gap)** 처리 — 면적 합이 안 맞으면 그냥 띄움
- **장비 회전·실제 footprint** — 현재 axis-aligned grid만
- **다층(floor_level > 1)** 처리 — 1층만 그려짐
- **동선(flow_paths) 시각화** — 데이터는 있지만 SVG에 안 그림

---

## 3) 허들 (현재 막힌/난제 부분)

### 허들 1 — **"Room 면적 합 ≠ 건물 면적"** 문제 ★★★
- Rule Engine은 각 Room 면적을 장비/등급 기반으로 산출 → 합이 건물 가용 면적과 정확히 일치하지 않음 (보통 ±10~20%)
- 현재는 stripe 비율로 강제 fit → **빈 공간 발생 또는 Room 압축**
- 근본 해결: 면적 충돌 시 어느 Room을 우선 압축할지 정책 필요 (auxiliary는 가능, process는 불가 등)

### 허들 2 — **Room 인접 배치의 자유도 부족** ★★★
- v1은 공정 순서를 코드에 **하드코딩** (`TOP_ROW`, `BOTTOM_ROW` 리스트)
- mAb 표준 공정은 OK지만 vaccine/ADC 등 modality가 바뀌면 적용 불가
- RL에게 넘기기 전에 **adjacency 그래프를 토폴로지로 자동 풀어내는 알고리즘** 필요
  - 후보: force-directed layout, BSP tree, MILP 최적화

### 허들 3 — **Airlock 4개 룰 (C4) 시각화** ★★
- Grade B + one-way → AL 4개 강제 (EU GMP Annex 1)
- 4개를 한 Room의 어느 면에 어떻게 배치할지 결정론적으로 풀기 어려움 (현재는 in/out × top/bottom 단순 분배)
- 실제 도면 가독성 떨어짐 → Drawing 품질 저하

### 허들 4 — **도어 swing 방향이 차압과 충돌하는 케이스** ★★
- C10 룰: 도어는 차압 흐름 방향으로 열려야 함
- 인접 두 Room의 차압이 양쪽으로 강할 때 swing 방향 결정이 모호
- 현재 v1은 단순 휴리스틱 → **edge case에서 룰 위반 발생 가능** (rationale에 WARNING 기록은 됨)

### 허들 5 — **RL과의 인터페이스 검증 부족** ★
- Layout 객체는 Reward 함수와 연동되지만, **RL 학습이 8GB RAM 환경에서 OOM** 발생 (지난 시도 시 강제 재시동)
- 학습은 Colab/연구실 GPU 환경 필요 → 검증 환경 확보가 선행 과제

---

## 다음 마일스톤 (제안)

| 우선순위 | 작업 | 예상 효과 |
|---|---|---|
| P1 | 허들 1 (면적 fit) 해결 — Room 우선순위 압축 정책 | 시각적 완성도 ↑ |
| P1 | 허들 2 (토폴로지 자동화) — adjacency → BSP 또는 MILP | 비-mAb modality 확장 가능 |
| P2 | RL 학습 환경 (Colab) 셋업 + 5000 step 스모크 학습 | 허들 5 검증 |
| P3 | 다층 / 동선 오버레이 / 장비 회전 | v2 완성도 |

---

**Repo**: https://github.com/Hyemin-xxx/Layout-Generator
**현 커밋**: `775be12` (Step 10 RL + HOW_IT_WORKS.md 완료)
**다음 작업 진입점**: `src/drawing_agent/layout_solver.py` (419줄, 허들 1·2 모두 여기서)
