# Layout-Generator

**스마트팩토리 캡스톤 디자인 — 바이오의약품(mAb) 제조시설 GMP Layout 자동 생성**

> 시각 산출물 디자인은 [DESIGN.md](DESIGN.md) (Silicon Valley creative-director-grade 디자인 시스템) 룰을 따릅니다.

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
│   ├── reward/                  # 점수 함수
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
