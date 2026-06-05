# Layout-Generator

**스마트팩토리 캡스톤 디자인 — 바이오의약품(mAb) 제조시설 GMP Layout 자동 생성**

> 시각 산출물 디자인은 [DESIGN.md](DESIGN.md) (Silicon Valley creative-director-grade 디자인 시스템) 룰을 따릅니다.
> **엔진이 어떻게 도면을 만드는지** 처음 보는 분은 → [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)

URS(User Requirements Specification)를 입력받아 EU GMP Annex 1과 사내 Layout 설계 원리 13조를 준수하는
바이오 제조시설 도면을 자동 생성합니다. 이후 강화학습으로 도면 품질을 진화시키고, 결과를 연구논문으로 정리합니다.

---

## 1. 전체 파이프라인

```
┌─────────────┐   ┌─────────────────┐   ┌──────────────────┐   ┌──────────────┐   ┌────────────┐
│  1. URS     │ → │  2. Rule Engine │ → │  3. Drawing      │ → │  4. Reward   │ → │  5. RL     │
│  (JSON)     │   │  (이 repo)      │   │     Agent        │   │     Function │   │  진화       │
└─────────────┘   └─────────────────┘   └──────────────────┘   └──────────────┘   └────────────┘
                          │                      │
                          ▼                      ▼
                   7-블록 JSON            2D Floorplan (SVG/DXF)
                   (혜민님께 인계)         + 장비 배치 + 색상 범례
```

| 단계 | Input | Output | 담당 |
|---|---|---|---|
| 1. URS | 사용자 요구사항 (제품종류/공정규모/건물면적/층수/물류방향 등) | 구조화된 JSON | 클라이언트 |
| 2. **Rule Engine** | URS JSON + GMP 룰 KB | **rooms / airlocks / adjacency / flow_paths / zones / constraints / rationale** | **이 repo** |
| 3. Drawing Agent | Rule Engine 7블록 output | 좌표 기반 2D 도면 후보 (SVG/DXF) | 혜민님 |
| 4. Reward | 도면 후보 + constraints | 점수 + 위반 리스트 + 개선포인트 | 이 repo |
| 5. RL | 후보 + reward | 더 나은 후보 / 최적 후보 선택 | 이 repo |

---

## 2. Rule Engine이 출력하는 7 블록 (Documentation Agent 인터페이스)

혜민님(Drawing Agent)에게 넘기는 **계약(contract)** 입니다. 좌표는 포함하지 않습니다 — "무엇이 / 어디에 / 어떤 관계로" 만 정의합니다.

| # | 블록 | 내용 |
|---|------|------|
| 1 | `rooms[]` | Room별 청정등급, 면적, 천정고, 차압, ACPH, gowning, 색상, 장비 리스트 |
| 2 | `airlocks[]` | PAL/MAL/CAL, in/out, cascade/sink/bubble, 양쪽 연결 Room |
| 3 | `adjacency[]` | Room↔Room 연결 그래프 (door/wall/passthrough, 도어 크기, swing 방향, flow 방향) |
| 4 | `flow_paths` | personnel/material/waste/product 4종 동선 |
| 5 | `zones` | process / auxiliary / NC 구역 그룹핑 |
| 6 | `constraints` | 복도 폭, AL 크기, 장비 간격, 색상 범례 등 정량 룰 |
| 7 | `rationale[]` | 어떤 룰이 어떤 결정을 내렸는지 추적 로그 (감사/디버깅용) |

---

## 3. GMP Layout 설계 원리 13조 (Rule Engine 코어)

| Rule | 항목 | 함수 | 산출 |
|------|------|------|------|
| 1 | 전체 배열 컨셉 | `derive_layout_axis()` | 공급→공정→리턴 축 방향 |
| 2 | Room 구성 | `expand_room_shape_constraints()` | 직사각형(합) 제약 |
| 3 | Room 크기 | `calc_room_area()` | 장비 footprint 기반 면적 |
| 4 | 청정등급 부여 | `assign_clean_grade()` | A/B/C/D/CNC/NC + 배경색 |
| 5 | Room 배열 | `partition_zones()` | process/auxiliary/NC zoning |
| 6 | 전실 배열 | `assign_airlocks()` | PAL/MAL/CAL in/out |
| 7 | 전실 타입 | `select_al_flow_type()` | cascade / sink / bubble |
| 8 | 복도 배열 | `build_corridors()` | supply / return (직접연결 금지) |
| 9 | 도어 위치 | `place_door()` | 크기, swing 방향(차압대응) |
| 10 | 장비 배치 | `attach_equipment()` | 장비간 ≥1000mm, 벽 600~1200mm |
| 11 | 세척실/준비실 | `link_wash_prep()` | passthrough COP 공유, 인적 차단 |
| 12 | NC 구역 | `attach_nc_rooms()` | 별도 영역 분리 |
| 13 | 차압(DP) | `compute_pressure_cascade()` | B>C>D>CNC>NC, ≥10~15Pa |

### Hard Constraints (절대 위반 불가, Reward에서도 critical 페널티)

| # | 제약 | 근거 |
|---|------|------|
| C1 | Supply ↔ Return 복도 직접 연결 금지 | 교차오염 |
| C2 | 세척실 ↔ 준비실 사람 왕래 차단 | 교차오염 |
| C3 | One-way Room 입구 AL ≠ 출구 AL | Bio-safety |
| C4 | Grade B + one-way → AL 4개 | EU GMP Annex 1 |
| C5 | 인접등급 간 차압 ≥ 10~15 Pa | EU GMP Annex 1 |
| C6 | 등급 순서: B > C > D > CNC > NC | EU GMP Annex 1 |
| C7 | 복도 폭 ≥ 1500 mm | 인적·자재 동선 |
| C8 | 장비 간격 ≥ 1000 mm, 장비-벽 ≥ 600 mm | 작업·청소 |
| C9 | 주공정 Room 총합 ∈ [40%, 70%] × TOTAL_AREA | 면적 효율 |
| C10 | 도어 swing = 차압 흐름 방향 | Fail-safe |

---

## 4. 기술 스택 & 디렉토리

- **언어**: Python 3.11+
- **스키마**: Pydantic v2 (JSON Schema 자동 생성)
- **드로잉**: shapely + svgwrite (v1), 추후 DXF (ezdxf)
- **RL**: gymnasium + stable-baselines3 (PPO)
- **테스트**: pytest

```
Layout-Generator/
├── README.md                    # ← 이 파일 (단계별 진행 로그)
├── ARCHITECTURE.md              # 상세 아키텍처
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── rule_engine/
│   │   ├── schemas.py           # Pydantic 모델 (input/output)
│   │   ├── engine.py            # 오케스트레이터
│   │   ├── validators.py        # Hard constraint 체크
│   │   ├── rules/               # 13개 룰 (rule_01 ~ rule_13)
│   │   └── kb/                  # Knowledge base JSON
│   ├── drawing_agent/           # 7블록 → SVG floorplan
│   │   ├── data/                # 4-tier 데이터 어댑터 (Phase A1)
│   │   │   ├── adapter.py       # SourceTracker + enrich_spec orchestrator
│   │   │   ├── tier1_ruleengine.py
│   │   │   ├── tier2_urs.py
│   │   │   ├── tier3_derive.py  # sort_order / bbox_m / same-room connects_to
│   │   │   └── tier4_manual_stub.py
│   │   ├── kb/                  # 수기 보충 데이터 (Phase B 부터 cross_room_links 등)
│   │   ├── design_tokens.py
│   │   ├── layout_solver.py     # 현재 strip-band; Phase C 에서 CP-SAT 으로 교체
│   │   ├── renderer.py          # z0~z12 SVG layer
│   │   └── floorplan.py         # 파이프라인 entry (enrich → solve → render)
│   ├── reward/                  # 점수 함수 (P1~P8 골격, P3·P5·P8 보류)
│   └── rl/                      # Gym env + 학습 스크립트
├── examples/
│   └── urs_mab_8000L.json       # 표준 예제 (URS_ConceptualDesign 기준)
├── output/                      # 생성된 결과물
├── docs/
│   ├── rule_mapping.md
│   └── rl_guide.md              # 강화학습 가이드
└── tests/
```

---

## 5. 강화학습 (RL) 전략 — 사용자 가이드 (향후 사용)

> Rule Engine output(7블록)은 **결정론적**입니다. RL은 그 다음 단계인 **도면 후보 배치 최적화**에 적용합니다.

### 5.1 RL 적용 지점
- **State**: 부분 배치된 floorplan (이미 놓인 Room들의 좌표 + 남은 Room 리스트)
- **Action**: 다음 Room의 위치(grid 좌표) + 방향(rotation)
- **Reward**: `src/reward/scorer.py`가 계산
  - +α: 동선 분리 / 차압 cascade 충족 / 면적 비율 충족 / 복도 폭 충족
  - −β: hard constraint 위반 (-∞에 가까운 큰 페널티)
  - −γ: soft 룰 위반 (1000mm 권장 어김 등)

### 5.2 알고리즘 권장
- **시작**: PPO (stable-baselines3) — 안정적, 연속+이산 mixed action에 강함
- **상태 인코딩**: CNN (grid 이미지) + MLP (메타데이터 concat)
- **확장**: 향후 Graph Neural Network (rooms+adjacency를 그래프로)

### 5.3 학습 절차 (구현 후)
```bash
# 1. 룰엔진으로 7블록 생성
python -m src.cli rule-engine examples/urs_mab_8000L.json output/spec.json

# 2. 결정론적 baseline 도면 1장 생성
python -m src.cli draw output/spec.json output/baseline.svg

# 3. RL 환경 sanity check
python -m src.rl.env --spec output/spec.json --random-episodes 5

# 4. 본격 학습 (수십만 step)
python -m src.rl.train --spec output/spec.json --total-timesteps 500000

# 5. 베스트 정책으로 도면 N장 생성 + 점수 분포 분석
python -m src.cli rl-rollout output/best_policy.zip --n 20
```

자세한 내용은 [docs/rl_guide.md](docs/rl_guide.md)에 (RL 단계 진입 시 작성).

---

## 6. 진행 단계 로그

> 매 단계 끝나면 여기에 한 줄씩 추가하고 commit.

- **[Step 0] 2026-05-26** — 자료 인수, 메모리/계획 수립. README + ARCHITECTURE 작성.
- **[Step 1] 2026-05-26** — Knowledge Base 6종 작성 (rooms_mab, equipment, grade_colors, acph_table, gowning_table, flow_policy_defaults). URS PDF + Layout Logic 표를 그대로 JSON화. 룰 코드와 데이터 분리 — modality 확장 시 KB만 추가.
- **[Step 2] 2026-05-26** — Pydantic v2 스키마 작성 (`src/rule_engine/schemas.py`). URSInput(5 sub-spec) + RuleEngineOutput(7 블록). 테스트 4/4 통과. extra='forbid'로 오타 방지.
- **[Step 3] 2026-05-26** — DESIGN.md 작성 (Silicon Valley creative-director-grade UI/UX 시스템). 컬러/타이포/그리드/Z-order/컴포넌트/접근성 단일 정의. `grade_colors.json`을 Tailwind-grade 토큰(fill/border/label/pattern)으로 업그레이드. 동선 4색·차압 sequential·neutral scale·semantic state 토큰 추가. Drawing Agent가 이 토큰만 참조.
- **[Step 4] 2026-05-26** — Rules 1-7 구현. `kb_loader.py`(JSON 캐시) + `working_state.py`(파이프라인 상태) + 7개 룰 모듈. 각 룰은 `apply(state)` 함수 하나로 동작하고 rationale을 자동 로그. 룰 1(axis)→2(shape)→3(size+면적비율 검증)→4(grade+색)→5(zones+동선)→6(AL 갯수)→7(AL 타입 cascade/sink/bubble). 임포트 smoke OK.
- **[Step 5] 2026-05-26** — Rules 8-13 + `adjacency_builder.py` 구현. 룰 8(복도 폭+supply/return 분리)→adjacency_build(AL↔Room↔복도 도어 페어)→9(MAL≥1500mm, swing은 사후)→10(장비 간격 constraints)→11(세척↔준비 passthrough + 사람 차단)→12(NC 누락 검증)→13(등급별 DP+정제2 보정+AL DP+ACPH+gowning attach). 13/13 import OK.
- **[Step 6] 2026-05-26** — Engine orchestrator + Hard Constraint Validator. `engine.py`의 `run_rule_engine(urs)`가 9 Phase 파이프라인 (Room 선택→룰1~5→6~7→adjacency→8~10→11~12→13+swing→C1~C10 validator→7블록 변환) 실행. `validators.py`에 C1~C10 각각 함수화. 기본 URS에서 **28 Room / 17 AL / 41 adjacency / 92 rationale** 생성, strict 모드 통과. 테스트 12/12 통과 (positive + negative + JSON roundtrip + override).
- **[Step 7] 2026-05-26** — 표준 예제 URS + CLI + Golden output. `examples/urs_mab_8000L.json` (URS_051 baseline), `src/cli.py` (`rule-engine` / `validate` 서브커맨드), `examples/golden_spec.json` (2794 lines, 28 Room / 17 AL / 41 adj / 93 rationale). C9(주공정 비율)는 안전 직결이 아닌 효율 권장이라 soft constraint로 재분류 — strict는 C1~C8, C10만 적용. 테스트 12/12 유지.
- **[Step 8] 2026-05-26** — Drawing Agent v1 (deterministic SVG floorplan). `design_tokens.py`가 DESIGN.md 토큰을 코드로 단일 정의 (NEUTRAL/GRADE/FLOW/PRESSURE/SEMANTIC + Typography + 8pt grid + stroke). `layout_solver.py`가 BIG/SOM 컨셉 다이어그램 풍 토폴로지(Aux-left / Core-stripes / NC-right + supply 중앙복도 + 양측 process row + AL stripe + return 상하)로 결정론적 배치. `renderer.py`가 z0~z12 layer 순서로 SVG 생성 — Grade A diagonal/CNC dotted pattern, Grade chip, DP badge, equipment with process-step, swing-arc door, AL type 표기, legend, title block. CLI에 `draw` 서브커맨드. **첫 산출물: examples/floorplan_v1.svg** (28 Room + 17 AL + 40 door, 411 lines SVG). 의존성 0 (raw SVG). 테스트 17/17 통과 (5 신규 drawing).
- **[Step 9] 2026-05-26** — Reward Function (`src/reward/scorer.py`). 3계층 점수: Hard penalty(C1~C10, -50/건) + Soft penalty(C9 등, -5/건) + Geometric quality 6종(flow_separation 8 / pressure_smoothness 6 / corridor_efficiency 4 / equipment_margin 5 / area_ratio_fit 3 / aesthetics 4). 베이스라인 도면 채점 결과 119.91점 (C9 -5, area_ratio_fit 0, 나머지 만점), hard 0건. RL의 step reward로 직접 사용 가능. 테스트 21/21 통과 (4 신규 reward).
- **[Step 10] 2026-05-26** — **RL 환경 스켈레톤 + 학습 가이드 완료** (마지막 단계). `src/rl/env.py` `LayoutEnv` (gymnasium 인터페이스, 5-d obs / 3-d continuous action / score-delta reward), `src/rl/train.py` PPO train + rollout 서브커맨드, `docs/rl_guide.md` 7-section 한국어 가이드 (MDP 정식화 / 알고리즘 비교 / 학습 절차 / 디버깅 / 확장 / 논문 그래프 권장). gymnasium 미설치 시에도 import 안 깨지도록 lazy guard. 테스트 22 passed + 1 skipped (gym optional).
- **[2026-05-29 / f665353]** Phase A1+A2 — 건축 도면 스타일 (그리드 축선 + Airlock swing 삼각형).
- **[2026-05-29 / 35d385a]** A3+A4+B+C+D — 도면 스타일 완성, 허들 3·4 해결, RL Colab 가이드.
- **[2026-05-29 / f4da244]** 장비 박스 빨간 테두리 두께 절반 (1.3 → 0.65).
- **[2026-05-29 / 6a0171b]** Stage 1 — 도면 스타일 GMP 컨벤션 6종 적용.
- **[2026-05-29 / f2a7820]** Z9 corridor flow arrows + 색상 코딩 동선 + floorplan_v2.
- **[2026-05-29 / 46b1da1, 076ed71]** floorplan_v3 — demo 템플릿 + KB Grade 색 (Grade D 추가).
- **[2026-05-29 / a3f9832]** SPEC v0.1 + PATCH v0.2 §1·§6 — Equipment/Room 스키마 확장 (Optional, 하위호환).
- **[2026-05-29 / 5f091cc]** SPEC §2 P1~P8 채점 골격 (P1·P2·P6·P7 active, P3·P5·P8 보류 — epistemic honesty).
- **[2026-05-29 / f583eb4]** floorplan_v4 — 스키마 확장 후 회귀 없음 검증.
- **[2026-05-29 / 6e2908f]** 모노톤 (선=검정, AL 세모/▼▲ 제거).
- **[2026-05-29 / 7c509f0]** 장비 빨강 복원 + AL 라벨 중앙 정렬.
- **[2026-05-29 / 0eeeed9, ea7ce77, 27aedc4]** AL drop 화살표 — 길이/굵기/머리 비율/refX 정렬 미세조정.
- **[2026-05-29 / a0f1db9]** 방 메타정보-장비 텍스트 충돌 해결 (메타 우측상단 + halo).
- **[2026-05-29 / 6dfff6c]** 메타를 방 이름 아래 중앙 정렬 + 장비 박스 안쪽 마진 확대.
- **[2026-05-29 / 92bf501]** 장비 박스 빨강 단색 + 20% 축소 + 자동축소로 전부 배치 (66/66).
- **[2026-05-29 / fc216ee]** **Phase A1 완료** — 4-tier 데이터 어댑터 (`src/drawing_agent/data/`) + tier3 derive (sort_order/bbox_m/same-room connects_to). 32 passed, 1 skipped. docs/decisions.md D-001·D-002 기록.
- **[2026-05-29 / 309bda8]** CLAUDE.md 기록 규칙 반영 — `docs/PROGRESS.md` 신설, `prompts.md` 에 사용자 주요 방향 M1~M7 누적.
- **[2026-05-29 / 09f952f]** **Phase A1.5 — Anti-corruption layer + silent-failure 차단.** 팀원 출력 진단(36건 mismatch + 4건 silent failure) 대응. schemas.py `extra="forbid"`→`"ignore"`, tier1_ruleengine.py 에 필드명 매핑·WxDxH 파싱·trailing space strip·process_no alias·swing→notes 변환 추가. scorer S1(area_ratio_fit current 키 silent default), S4(모든 DP=0 시 silent 1.0 만점) → None 명시 반환. 테스트 15건 추가 (47 passed). D-003, D-004 결정 로그.
- **[2026-05-29 / (이 커밋)]** **Phase A1.6 — process_no 통일 + PPO 기반 sort_order derive + co_locate_group.** D-005 `Equipment.process_step` → `process_no` rename (Pydantic alias 로 JSON 양방향 호환), D-006 `@property process_step` 으로 rule_engine 무수정 회복 (15건 회귀 → 0), D-007 schema `co_locate_group` 필드 신설 + tier3 derive 전략을 product_process_order rank 기반으로 교체. 팀원 출력 65 장비 fixture 검증: sort_order 65/65, co_locate_group 65/65, 13 그룹. 테스트 9건 신규 (56 passed).
- **[2026-05-29 / (이 커밋)]** **Phase B1 — P-series 수식 (P1·P2·P6·P7).** scorer 의 `score_spec_p_series()` 골격에 4개 active 수식 채움 + 정규화 분모를 "측정된 active 가중치 합" 으로 동적 변경 (epistemic honesty 일관). 근거: ISPE Vol.6 §7.9(P1)·§7.5(P2)·§7.6 + ISO 14644-4 §6(P6)·§1(P7). fixture 65 장비 layout=None 검증: P1=1.0 (52 link forward), P2=1.0 (same-room + group 응집), P6=None (clearance_m 부재 → skipped_no_data, 분모 19), P7=0.4387 (9 process 방 평균 density), normalized=0.9114. 테스트 10건 신규 (66 passed, 1 skipped). D-008 결정 로그.
- **[2026-05-29 / (이 커밋)]** **Phase B1 (D-009) — P-series 좌표 기반 재구현 + "점수 ≠ 데이터 일관성" 원칙 명시.** 사용자 진단으로 D-008 silent 만점 버그 발견 (P1·P2·P7 이 layout 받지만 본체 미사용 → 좌표 변해도 점수 안 변함, 모든 fixture P1=1.0/P2=1.0). 재구현: P1=흐름축 unit vector 투영 단조성, P2=co_locate_group 좌표 평균 거리 + connects_to link 거리, P7=좌표 기반 packing density (inner+outer). layout=None → P1/P2/P7 모두 None. strip-band 4 시나리오 검증: P1≈0.64, P2≈0.90, P7≈0.25, norm≈0.66 (CP-SAT 가 풀어야 할 진짜 before 베이스라인). 테스트 7건 좌표 기반으로 재작성 + 합성 layout 케이스 추가 (67 passed). D-008 SUPERSEDED.
- **[2026-05-30 / (이 커밋)]** **Phase B1.5 (D-010) — 시나리오 변별 책임 분리 (캔버스 = drawing_agent, 장비 사양 = rule_engine).** 4 시나리오 strip-band 동일 점수 원인 진단 = rule_engine 이 URS 의 culture_scale_L/n_product_types/building dim 을 spec 에 안 흘림. 옵션 2 (drawing_agent 가 장비 sizing override) 거부 — 추론 데이터로 도메인 침범 = epistemic honesty 위배. 대신 우리 영역 (캔버스) 만 해결: `src/drawing_agent/data/building.py` 신규, `resolve_building_dims(spec, urs_path)` 4-tier (tier1 룰엔진 / tier2 URS / tier3 의도 미구현 / tier4 default 78500×42500). `generate_floorplan(urs_path=...)` 가 URS dim 자동 적용. **결과 — 4 시나리오 모두 distinct norm**: A_small=0.6687, mab_8000L=0.6615, C_closed=0.6965, B_large=0.6511. A_small P7 0.25→0.31 (좁은 캔버스 자동 compact), B_large P2 0.90→0.89 (장비 흩어짐). 테스트 6건 신규 (73 passed). D-010 결정 로그.
- **[2026-05-30 / (이 커밋)]** **Phase B2 (D-013) — before-baseline 저장 (output/baselines.json).** `scripts/baselines.py` 신규 — 4 시나리오 strip-band P-series + 6종 geometric quality + hard/soft 를 결정론적으로 측정 (`--check` 동일성 검증 통과). 메타 5건 한계 박음 (rule_engine 장비 변별 부재, CP-SAT 미도입, P3·P5·P8 보류, P6 미구현, 정규화 분모 동적). 4 시나리오 norm 0.6511~0.6965 / geo_total 121.5~127.06 / hard 0건 전부 만족. 변동 폭 좁음 (~7%p) 은 예상된 중간 상태 — 장비 변별 + CP-SAT 두 요인 해소 시 "before → after" 정량 신호로 기능. D-013 결정 로그.
- **[2026-05-30 / (이 커밋)]** **Phase B3 (D-014) — NNE Pharmaplan 모범 배치 골든 + P-series 타당성 검증.** `docs/reference/nne_equipment_layout.md` (사용자 작성, NNE Pharmaplan Bacterial Bio PilotPlant Doc 0617C05016 추출) 기반으로 `tests/fixtures/golden_nne_layout.json` (16 rooms / 70 eq / 62000×42000mm) + `scripts/golden_nne.py` 작성. 방법 B (구조 검증, 정밀 좌표 X). **결과: NNE_golden norm=0.7233 > strip-band avg norm=0.6694, Δ=+0.054 (+5.4%p)**. P1 +0.05 (NNE 직선 흐름축 vs strip-band zigzag), P7 +0.17 (NNE 방·장비 면적 균형). P2 ≈동등 (둘 다 같은 방 응집 만점 편향 → D_REF=20m 후속 보정). P-series 가 전문가 배치를 strip-band 보다 명확히 높게 평가 → CP-SAT 가기 전 점수 수식 타당성 확보. 회귀 7건 신규 (80 passed). D-014 결정 로그.
- **[2026-05-30 / (이 커밋)]** **Phase C0 (D-015) — CP-SAT 진입점 + 최소 골격 검증.** 진단 보고 (이전 턴) 로 strip-band 4 한계 정리 → 결론: **층1 (방 배치) 부터 CP-SAT, 층2 (장비) 는 strip-band 재사용 보류** (P2 group_term 포화로 leverage 작음). `requirements.txt` 에 `ortools==9.10.4067` 핀. `src/drawing_agent/constraint_compiler.py` + `cpsat_solver.py` 신규 (격자 500mm, AddNoOverlap2D, 캔버스 도메인, 좌상단 모으기 임시 목적). 기존 `layout_solver.solve()` 수정 0줄 — fallback 보존. **C0 검증 (mab_8000L, 3 방)**: OPTIMAL / 20.12ms / 안겹침·캔버스 PASS / Layout·renderer 재사용 0줄 수정 → `output/floorplan_c0_cpsat_3room.svg`. 결정론 (num_search_workers=1) 보장. 테스트 8건 신규 (88 passed). D-015 결정 로그.
- **[2026-05-30 / (이 커밋)]** **Phase C1a (D-016) — 전체 방 + hard 제약 + 사이징 정직화.** `compile_c1a` / `solve_c1a` 신규 — 28방 (mab_8000L) 에 H1 캔버스 / H2 안겹침 / H3 zone 분리 / H4 adjacency 25m. **단계 완화로 INFEASIBLE 진단**: zone 만 켜도 IF → 원인 `ROOM_AREA_TO_SIDE_FACTOR=1.4` 가 방 면적을 1.96× 부풀려 stripe 안 못 들어감. **1.4 → 1.0 정직화** (방 한 변 = √area, aspect [0.7, 1.4] 자연 변동). 결정론 강화 — `max_deterministic_time = time_limit × 4` 추가 (wall-clock 무관). **결과**: status FEASIBLE / **첫 feasible 500ms** / 28방 모두 안 겹침·캔버스·adjacency 25m 안 / renderer 재사용 0줄 → `output/floorplan_c1a_28room.svg` 68KB / 결정론 통과. 점수 목적함수는 C1b. 테스트 10건 신규 (98 passed). D-016 결정 로그.
- **[2026-05-30 / (이 커밋)]** **Phase C1b (D-017) — P-series surrogate 목적함수 + 첫 before→after.** `compile_c1b` / `solve_c1b` 신규 — C1a hard 위에 P1 (PPO 인접 쌍 흐름축 단조 페널티) + P2 (adjacency 거리 합) + tie-breaker (좌상단) surrogate. **4 시나리오 측정 (P1-only weight)**: A_small +0.044, mab −0.009, C_closed −0.056, B_large +0.015 / avg **−0.002 (거의 동등)** / NNE_golden ref 0.7233. 모두 OPTIMAL (700ms~2.6s). 디폴트 weight 는 −0.033 저조 (P2 ↔ P1 충돌). **핵심 진단**: ① CP-SAT (factor 1.0) vs strip-band (area 비율) 방 사이즈 정의 다름, ② adjacency 35건 (room↔airlock) 모델 밖 — C2 결정, ③ P1 surrogate (방 단위) ≠ 진짜 P1 (장비 흐름축 투영) — 같은 방 row-major pack 으로 sort_order row 간 역행 → 진짜 향상은 **C3 (장비 CP-SAT)** 필요, ④ NNE 까지 격차 +0.054 의 핵심은 P7 (방-장비 면적 균형). 테스트 8건 신규 (98→**106 passed**). SVG `output/floorplan_c1b_mab_8000L.svg`. D-017 결정 로그.
- **[2026-05-30 / (이 커밋)]** **Phase C3a (D-018) — 장비 CP-SAT 착수 + D-015 부분 재검토 + B-001 시각 축소 분리.** D-017 실측으로 P1·P7 의 진짜 leverage 가 *장비* 단위임을 확인 → C3 우선. **C3a (한 방 5장비)** 만 — `compile_room_c3a` / `solve_room_c3a` 신규 (장비 격자 + AddNoOverlap2D + P1 단조 surrogate + P7 외접 bbox perimeter 최소화). `_place_equipment_grid(use_actual_mm)` 플래그 추가 (default False 보존 — baselines/B3 안 흔듦). **R_MEDIA_PREP 5장비 (10×10m=100m²) 검증**: P7_room 0.126 (row-major 시각축소) → 0.556 (row-major 실제) → **0.870 (CP-SAT 실제)** = **+0.31 향상**. P1_local 0.50 → **0.75**. CP-SAT outer_fill=0.510 (sweet 0.5 정확). 226ms OPTIMAL. strip-band rect (54m²) 에선 INFEASIBLE — 방 rect 가 spec area 근처여야. 테스트 8건 신규 (106→**114 passed**). D-018 결정 로그.
- **[2026-05-30 / (이 커밋)]** **Phase C3b (D-019) — 장비 있는 모든 방 sweep + 정제실1 진단.** `scripts/c3b_room_map.py` 신규 — mab_8000L 의 13방 (장비 있는 모든 방) 에 C3a 적용. 방 rect = spec area_m2 정사각. **13/13 모두 feasible** (INFEASIBLE 0건). 평균 P7: row-major 실제 0.505 → CP-SAT 0.605 (**+10%p**), P1: 0.696 → 0.911 (**+21.5%p**). 큰 향상: R_PURIFICATION_1 **P7 +0.518** (가장 큼!) / R_MEDIA_PREP +0.314 / R_INOCULATION +0.245 / R_PURIFICATION_2 +0.222. **R_PURIFICATION_1 (사용자 1순위 위험 23장비) FEASIBLE 5s, P7 0.259 → 0.777 — fallback 불필요**. 작은 방 (1~4 장비) sub-second OPTIMAL, 큰 방 5s timeout (FEASIBLE 첫 해). 테스트 4건 신규 (114→**118 passed**). 산출물 `output/c3b_room_map.json`. D-019 결정 로그.
- **[2026-05-30 / (이 커밋)]** **Phase C1+C3 통합 (D-020) — 첫 진짜 before→after.** `scripts/c1c3_pipeline.py` 신규 — C1b(방) → C3a(장비) → P-series + INFEASIBLE row-major fallback. `solve_c1b` 에 `aspect_min/max` 인자 추가. **3단계 진단·해결**: ① default [0.7,1.4] → 44% INFEASIBLE (C1b 가 방 작게 풀음), ② 좁힘 [0.9,1.1] → mab +0.06 but A_small 캔버스 부족 INFEASIBLE, ③ **동적 aspect (canvas vs spec area 비교, threshold=1.0)** 채택. C3 시간 단축 (≤4=1s, 5-10=3s, 11+=8s). **결과**: avg 0.6694 → **0.6888 (+0.0194)**. **mab_8000L 0.6615 → 0.7230 = NNE 0.7233 거의 도달** (mab P7 +0.43). C_closed +0.009. A_small/B_large 미미. **R_PURIFICATION_1 FEASIBLE 8s fallback 안 함**. 전체 시간 66s, INFEASIBLE→fallback 8/52. 테스트 4건 신규 (118→**122 passed**). D-020 결정 로그. 산출물 `output/c1c3_pipeline.json`.
- **[2026-06-01 / (이 커밋)]** **소연 룰엔진 모노레포 통합 (옵션 2).** 공용 레포 `smartepic2026/Layout-Generator` 로 이전(origin), 베이스라인 푸시. **anti-corruption 구조 정착**: ① 우리 내부 계약(`schemas/validators/working_state/kb_loader/kb`)을 `src/contract/` 로 분리(import 16곳+scripts/tests 일괄 갱신), ② `src/rule_engine/` 를 소연 최신 엔진(dataclass `models.py`)으로 교체, 소연 코드 절대 import 64곳 `src.` 접두사 정렬, ③ `cli.py rule-engine` 재작성 — URS xlsx → 소연 `run_rule_engine` → `to_json` → tier1 어댑터 → 우리 pydantic spec. **end-to-end 검증**: `rule-engine`/`draw`/`validate` 3 명령 + 드로잉(SVG 90KB, 방 30 배치) 통과. 테스트 **102 passed** (옛 엔진 fixture 는 `tests/_legacy_spec.py` shim 으로 공급). **남은 15 fail/6 error 는 옛 엔진 특정값 단언(R_MEDIA_PREP 등)** → 소연 출력 기준 갱신 follow-up. RAG_DB_build/rag_interface 는 소연 최신과 내용 동일.
- **[2026-06-02 / (이 커밋)]** **도면 v3 (D-021) — GMP 청정도 구배 토폴로지 (전문가 피드백 6건).** 외부(소연) spec 경로(`dynamic_rooms=True`)를 신규 `_solve_gmp_gradient` 로 재설계: 가로 청정도 구배 **NC→Grade D→[D 세로복도]→Grade C 공정**, 공정구역=return(상)·공정행·[가운 게이트]supply(중앙)·공정행·return(하). ① 작은 방 슬리버 → water-filling 종횡비 클램프(`_alloc_dim`), ② 양측 return 복도 실제 배치(정제실 하행 return 인접), ③ Grade D 세로복도 + 가운(C) 게이트 + 합성도어, ④ 도어 swing arc `sweep` 반전(여닫이 정상), ⑤ NC→D→C 한방향 구배, ⑥ one-way flow 화살표 재작성(supply→공정행 수직통과→양측 return→D복도 배출). AL 폭 절대상한 3.8m. **경계 보존**: 하드코딩 strip-band(`dynamic_rooms=False`)·baselines·NNE 무수정. 발표 도면 5종 재생성(배치 31/21/43/36/30) + `ppt_png/` 라이트 5종 갱신. **회귀 0** (변경 전·후 17 fail/100 pass/6 err 동일; 차이는 CP-SAT 결정성 테스트 flakiness). D-021 결정 로그.
- **[2026-06-03 / (이 커밋)]** 발표 산출물 `output/0602/` 추가 — 5 시나리오 SVG 10종(라이트 5 + 블루프린트 5) + `시나리오_비교표.md`(URS 입력 노브 → 룰엔진 출력 변화 → 도면 배치 차이 정리표, 수치 요약, 시나리오별 상세, 방법 주석). 발표자료용.
- **[2026-06-06 / (이 커밋)]** **고도화 Phase 0 (D-022) — 통합 벤치테스트 + 룰엔진→drawing 정렬 감사.** 룰엔진 6/2 push 분석(teammate/main `e05b85c`, 13→15룰, is_airlock/airlock_id·AirLock.area_m2 추가 = **additive·non-breaking**, flow_paths 구조 불변). 새 엔진 실제 출력 추출(`output/teammate_engine_v2_output.json`, 48 rooms/18 AL). **벤치테스트**: raw→`draw` 직접=크래시(rationale 필드명), **어댑터(`adapt_external_dict`) 거치면 정상**(SVG `output/bench_v2_new_engine.svg`, rooms 23/AL 18/doors 39) → 통합 경로에 어댑터 단계 필수. **정렬 감사 `docs/alignment_audit.md`** — 필드별 consumed/DROPPED 표 + Top7 gap. **G1(🔴)**: 동선 화살표 `_emit_z9_flow_arrows`가 spec 미수신 → flow_paths 4종 동선 미사용, `"SUPPLY_CORRIDOR"` 패턴 휴리스틱(renderer.py:606,634). **G2(🔴)**: width_mm/area_ratio_pct 무시(피드백#5). **G3(🟠)**: is_airlock dedup이 ID패턴+area==0 휴리스틱에만 의존(취약). 사용자 결정: Phase 0부터 / 새 엔진 기준 진행. 다음=Phase 1(동선 화살표 flow_paths 재작성).
