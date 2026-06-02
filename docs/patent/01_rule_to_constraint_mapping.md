# 특허 자료 ① — 규칙 → 제약 컴파일 매핑표 (진보성 증빙)

> 목적: 본 발명이 "범용 최적화에 규칙 하나 넣은 단순 자동화"가 아니라,
> **이질적인 다수의 GMP 규제규칙을 각각 서로 다른 형태(hard 제약 / 목적항 /
> 속성로직 / 신뢰도 보류)로 컴파일하여 동시에 처리**함을 코드 근거로 증명한다.
>
> ⚠️ 면책: 본 문서는 변리사 검토 전 발명자 보조 자료다. 표준 조항 매핑은
> 일반 수준(ISO 14644-1 / EU GMP Annex 1 / ISPE Baseline Guide)으로 표기했고,
> **정확한 조항·근거는 KB(`GMP Layout Logic_0510.xlsx`) 및 도메인 전문가 확인 필요**.

---

## 0. 시스템 2단 구조 (발명자 범위에 영향)

| 단계 | 담당 | 역할 |
|---|---|---|
| **A. 룰엔진** (`src/rule_engine/`) | 소연 | 15개 GMP 규칙 적용 → 7블록(rooms/airlocks/adjacency/flow_paths/zones/constraints/rationale) 구조화 출력 |
| **B. 어댑터+컴파일+솔버+렌더** (`src/drawing_agent/`, `src/contract/`) | 본인 | 7블록 → 내부계약 변환 → **정수제약/목적함수 컴파일** → 결정론 최적화 → 점수 → 도면 |

> "규칙 자체(15종)"는 A, "규칙→정수제약 컴파일·최적화"는 B. → 공동출원 vs 단독(B 기여 중심) 범위 결정 필요 (청구항 단계 반영).

---

## 1. 컴파일 형태 4분류 (핵심 차별)

본 발명은 각 규칙을 **그 규칙의 유형과 근거 충분성**에 따라 아래 4형태 중 하나로 컴파일한다:

| 형태 | 의미 | 강제 방식 |
|---|---|---|
| **H (Hard 기하제약)** | 위반 시 해 없음 | 정수제약 (도메인 제한 / AddNoOverlap2D / 거리상한) |
| **S (Soft 목적항)** | 최적화로 개선 | 목적함수 minimize 항 (가중치) |
| **L (속성/조건 로직)** | 비교·도출 | 차압 비교 → 도어방향 등 |
| **D (보류·신뢰도)** | 근거 불충분 | null + confidence 태깅, **점수산출 가드** |

---

## 2. 규칙 → 제약 매핑표 (코드 근거)

격자 해상도 500mm, 방 한 변 = √area × 1.0, aspect [0.7, 1.4] 기준.

| # | 규칙/요인 (룰엔진) | 산출(7블록) | 컴파일 형태 | 변수·제약식 (우리 모델) | 근거 표준(일반) | 구현상태 | 코드 위치 |
|---|---|---|---|---|---|---|---|
| 1 | rule_01 layout_axis | building 축/방향 | L | 캔버스 W×H, 출입구 시계방향 → 좌표계 정의 | ISPE facility | 구현 | building.py / solve() |
| 2 | rule_02 room_shape | 직사각 W·D | H | 방 = 정수 (x,y,w,h), aspect [0.7,1.4] 도메인 | ISPE | 구현 | compile_c1a |
| 3 | rule_03 room_size | area·ceiling·vol | H | side=√area×1.0 → w/h 도메인 하한·상한 | ISPE | 구현 | `_room_side_cells`, compile_c1a |
| 4 | rule_04 clean_grade | grade·color | H | 등급 → 구역 식별자 → x-도메인 제한(아래 5와 결합) | ISO 14644-1 | 구현·강제 | `_zone_x_bounds`, H3 |
| 5 | rule_05 zones | process/aux/nc | H | aux=[0,0.20W], nc=[0.82W,W], process=중앙±0.03 | EU GMP Annex 1 | 구현·강제 | `_zone_x_bounds` |
| 6 | rule_06 airlocks | airlock 객체 | H+geom | AL을 connects_higher 방에 귀속 → 방경계 내측 배치 | EU GMP Annex 1 | 구현 | `_place_airlocks_in_rooms` |
| 7 | rule_07 al_flow_type | cascade/sink/bubble | L | biological_safety_isolation → sink/bubble 강제 도출 | EU GMP Annex 1 | 속성 | 룰엔진 rule_07 |
| 8 | rule_08 corridors | supply/return | **H (강제)** | supply↔return **직결금지 → 4방향 reified BoolOr 최소간격(2m) 분리 제약(H5)** | ISPE/EU GMP 동선 | ✅ **구현·강제** | constraint_compiler H5 |
| 9 | rule_09 doors | 위치·swing | L+geom | 차압 비교 → swing target=저압측; AL 2도어(코리도/방측) | EU GMP Annex 1 | 구현 | `_resolve_swing`(C10), `_place_airlock_doors` |
| 10 | rule_10 equipment | 정렬·clearance | H+S | 방내 장비 정수배치, no-overlap+gap 500mm; P1 sort_order 단조 + P7 외접둘레 최소 | ISPE | 구현 | compile_room_c3a (C3a) |
| 11 | rule_11 wash_prep | 인접·비교차 | H(목표) | wash↔prep **인원동선 비교차 제약** | EU GMP Annex 1 | ⚠️ 스키마만·솔버 미강제 | constraints.wash_prep_no_personnel_crossing |
| 12 | rule_12 nc_rooms | onsite 필터 | 구성 | organization 정책 → 방 집합 결정 | ISPE | 구현 | 룰엔진 rule_12 |
| 13 | rule_13 pressure | DP cascade | L | 차압 min 10Pa, 등급 압력순서; 차압 → 도어방향 | EU GMP Annex 1 | 구현(도어방향) | `_resolve_swing` |
| 14 | rule_14 acph | 환기횟수 | L | 등급별 ACPH 도출(속성) | ISO 14644 | 속성 | 룰엔진 rule_14 |
| 15 | rule_15 gowning | 갱의 type/method | L | 등급별 갱의 도출(속성) | EU GMP Annex 1 | 속성 | 룰엔진 rule_15 |
| — | adjacency(인접요구) | adjacency[] | H | 인접쌍 중심 **맨해튼거리 ≤ 25,000mm** 제약 | ISPE(동선) | 구현·강제 | H4, AddAbsEquality |
| — | flow_paths.PPO(공정순서) | product_process_order | S | 인접 공정쌍 흐름축(가로) 단조 위반 페널티, w=100 | ISPE(동선) | 구현·목적 | compile_c1b P1 |
| — | flow_paths(동선유형) | personnel/material/product/waste | geom | 4색 점선 라우팅, 에어록 drop 화살표 | — | 구현 | renderer z9 |
| — | corridor_width_mm | 통로폭 범위 | H(목표) | 통로폭 제약 | ISPE | ⚠️ strip-band ratio만 | constraints.corridor_width_mm |
| — | process_zone_area_ratio | 공정구역 면적비 | H(목표) | 면적비 제약 | ISPE | ⚠️ 미사용 | constraints |
| — | open_closed / contamination_class | (추론데이터) | **D** | null+confidence 태깅 → **P3/P5/P8 점수 가드(제외)** | — | 구현(의도된 보류) | tier1 adapter, scorer guard |

### 비중첩·캔버스 (전 방 공통 Hard)
- **H1 캔버스 내**: `x+w ≤ W`, `y+h ≤ H` — compile_c1a
- **H2 비중첩**: `AddNoOverlap2D([x_intervals],[y_intervals])` — compile_c1a

### 목적함수 (C1b)
`minimize( 100·Σ P1_pen + 60·Σ(|dx|+|dy|)_adjacency + 1·Σ(x+y) )`
- P1_pen = max(0, cx_i − cx_{i+1}) (PPO 인접쌍 흐름축 단조 위반)

### 결정론 보장 (재현성 = 기술적 효과)
`num_search_workers=1`, `random_seed=0`, `max_deterministic_time=time_limit×4` (벽시계 무관) → **동일 URS·동일 KB → 동일 좌표**. (cpsat_solver.py)

### Infeasible 폴백
hard 제약 충돌 시 `enforce_zones`/`enforce_adjacency` 단계 완화 또는 strip-band 대체 → 완화된 제약 진단 메타 기록. (solve_c1a 완화 플래그)

---

## 3. 이 표가 입증하는 진보성 포인트

1. **다종(15+) 규칙 → 다형(H/S/L/D) 컴파일** — 단일 규칙→단일 제약이 아님.
2. **근거강도 계층화** — 같은 규칙도 hard/soft/보류로 분류(특히 D: epistemic honesty). 우리 고유, 회피 어려움.
3. **결정론·재현성** — 휴리스틱/생성형과 구별되는 기술적 효과.
4. **규칙→정수제약의 구체적 변환식** — 등급차→구역도메인, 차압→도어방향, 공정순서→흐름축 단조, 인접→맨해튼거리 상한 (단순 if-then 아님).

## 4. ⚠️ 솔직한 갭 (출원 전 보완)

- ✅ **supply↔return 직결금지(H5) 는 구현 완료** — `compile_c1a` 에 4방향 reified
  BoolOr 최소간격(2m) 분리 제약으로 컴파일. C1b 풀이 결과 두 코리도 비인접 확인.
  단, 현재 소연 spec 인스턴스에선 compactness 목적이 이미 분리시켜 **이 인스턴스에선
  binding 안 됨** — 두 코리도가 서로 끌릴 인스턴스에서 효과가 드러남(추가 시나리오로 입증 권장).
- ⚠️ **wash/prep 비교차, 통로폭, 면적비**는 여전히 미강제. 사유: ① 비교차는 인원 *경로*
  모델 필요(약한 proxy는 엄밀성 훼손 → 의도적 보류), ② 통로폭은 자유배치에서 통로 방향
  reified 필요, ③ 면적비는 방 면적이 입력서 거의 정해져 placement 제약으론 약함. → 명세서엔
  "방법/구성"으로 기재 가능하나 hard 강제는 후속 모델링 필요.
- 표준 조항(ISO/EU GMP) **정확 매핑은 미확정** → KB·전문가 확인 필요.
- 발명자 범위(소연 공동 vs 단독) 미결 → 청구항 방향 영향.

---

_생성: 특허자료 ①. 다음: ② 선행기술 검색전략, ③ 청구항·명세서 재작성._
