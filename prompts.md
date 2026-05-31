# 작업 프롬프트 로그

> 단계별 사용자 프롬프트 요약 + 작업 결과 + 게이트 점검 기록.

---

## 2026-05-29 — Phase 0: Drawing renderer 스타일 정합

### 사용자 요청 요약
- `reference_style_demo.svg` 스타일을 자동 생성 렌더러(`src/drawing_agent/renderer.py`)에 적용
- **Grade별 색상은 floorplan_v1 방식 (KB 기반) 유지**
- 동선 화살표 색상 코딩 + boundary 라벨 색상화
- main 브랜치에서 작업
- 엔진 다시 돌려 `floorplan_v2.svg` 생성 → `floorplan_v1.svg` 와 비교

### Pre-work
- [x] `feature/drawing-style-v2 → main` fast-forward 머지 완료 (`f665353 → 6a0171b`)
- [x] 현재 main = `6a0171b` (Stage 1 6종 변경 포함)
- [x] `prompts.md` 생성 (이 파일)

### 작업 항목
1. [x] renderer.py — `_emit_z11_boundary_flow` 색상화 (Personnel/Material/Waste FLOW 색상 적용)
2. [x] renderer.py — `_emit_z9_flow_arrows` 신규 (Supply=personnel색 좌→우 / Return=waste색 우→좌 / AL drop PAL=personnel·MAL=material)
3. [x] render() 파이프라인에 z9 wire-in
4. [x] dimension chain은 이미 `_emit_z2b_axes` 에서 정식 표기 중 (변경 없음)
5. [x] 엔진 실행: `urs_mab_8000L.json → output/floorplan_v2.svg` + `examples/floorplan_v2.svg`
6. [x] 시나리오 3종 (A/B/C) 재생성

### 게이트 통과 결과
- [x] `pytest tests/ -q` → **22 passed, 1 skipped**
- [x] `floorplan_v2.svg` 생성됨 (81 KB, v1: 60 KB → +35% 화살표/라벨 추가분)
- [x] Grade 색상 (KB 기반 `room-fills`) 보존 — design_tokens.py 무변경

### 결과 검증
| Scenario | corridor 화살표 | 색상 boundary 라벨 |
|---|---|---|
| floorplan_v2 (mAb 8000L baseline) | 22 | 6 |
| A_small_aseptic (2000L + aseptic) | 16 | 6 |
| B_large_multiproduct (15000L × 3) | 22 | 6 |
| C_closed_system (5000L closed) | 10 | 6 |

### 코드 변경
- `src/drawing_agent/renderer.py`: 2 함수 추가/수정 (~95줄)
  - `_emit_z11_boundary_flow` — FLOW 색상 매핑 추가
  - `_emit_z9_flow_arrows` — 신규 (corridor + AL drop)
- `render()` Z-order에 z9 삽입 (z8 equipment ↔ z10 labels 사이)

---

## 다음 단계 (Phase 1)

main 브랜치 push 후 → `feature/rl-env-graph` 새 브랜치 생성 → `B_OPTION_SPEC.md` 8단계 작업 진행 예정.

---

## 2026-05-29 (continued) — Phase 0.5: floorplan_v3 (demo 템플릿 + KB Grade 색)

### 사용자 피드백
> Phase 0 결과(floorplan_v2)는 layout topology가 demo와 완전 다름. demo는 수작업, v2는 strip-band 알고리즘 — **근본적으로 다른 출력**.
> 옵션 A 선택: **demo를 정적 템플릿으로 쓰고 KB Grade 색만 입히기**.

### 작업
1. [x] `output/reference_style_demo.svg` → `output/floorplan_v3.svg` 복사
2. [x] `<style>` 블록의 CSS class 업데이트:
   - `.room-c` : `#FBF1D9` → `#FCD34D` (KB Grade C, 50% opacity)
   - `.room-cnc`: `#F2F2F2` → `#D6D3D1` (KB CNC)
   - `.room-nc` : `#FFFFFF` → `#E7E5E4` (KB NC)
   - `.ante` : `#F7E8C2` → `#FCD34D` @ 35% (C 톤다운)
   - **신규**: `.room-a` `.room-b` `.room-d` 추가 (개별 룸을 다른 Grade로 바꿀 때 클래스만 갈아끼우면 됨)
3. [x] `examples/floorplan_v3.svg` 동기

### 결과물
- `output/floorplan_v3.svg` (49 KB) — demo 구조 + KB Grade 색
- 비교: v1 (60 KB auto) / v2 (81 KB auto + 화살표) / v3 (49 KB demo+KB color)

### 한계 (사용자 인지)
- v3는 **정적 템플릿** — 다른 URS 넣어도 layout 변하지 않음
- 진정한 URS-driven 출력은 `layout_solver.py` 재작성 필요 (옵션 B, Phase 1 끝나고 별도)




---

## 2026-05-29 — 사용자 주요 방향 정리 (CLAUDE.md 기반 의사결정)

> 세션 누적용. 어떤 사용자 지시가 어떤 코드 변화로 이어졌는지 추적 (감사/논문 재현).

### M1. CLAUDE.md 등록 — 판단 기준 4대 원칙

사용자: "프로젝트 루트에 CLAUDE.md 를 추가했어. 지금부터 모든 추천·선택은 거기
적힌 4대 기준(성능 / 실무 수준 / SW등록·특허 / 논문)으로 판단해.
'빠르다·코드 적다·구현 쉽다'는 추천 사유가 아니야."

→ 이전에 추천한 SA 무효. 시간 기준은 추천 사유가 될 수 없음.

### M2. 솔버는 CP-SAT 확정

사용자: "솔버는 CP-SAT 다. 그리고 솔버보다 데이터·수식·before 베이스라인이 먼저야."

→ CLAUDE.md 에 명시. CP-SAT 채택 이유: 결정론적(재현성), 수학적 최적,
   규칙→정수제약 컴파일이 특허 핵심.
→ ortools 의존성 추가 예정 (Phase C).
→ 작업 순서: A(데이터) → B(수식+베이스라인) → C(CP-SAT) → D(평가)

### M3. P3·P5·P8 점수 보류는 의도된 설계

사용자 (CLAUDE.md 안): "검수자가 없어 추론 데이터로 점수를 오염시키지 않는다.
스키마 필드는 미리 두고 값만 null. 이 '근거가 명확한 제약만 적용하고 불확실한 건
confidence 태깅해 분리'는 버그가 아니라 의도된 설계 원칙(epistemic honesty)이며
논문/특허 강점."

→ scorer P3·P5·P8 은 가중치 0 + null 가드 유지.
→ 이게 강점이라는 점을 논문 method 섹션에서 명시.

### M4. 3계층 (실제는 4-tier) 데이터 어댑터

사용자: "입력 데이터 출처를 3계층 어댑터로 설계해. drawing_agent가 값을 찾을 때:
(1) RuleEngineOutput → (2) examples/ URS → (3) derive → (4) drawing_agent/kb/.
이렇게 하면 팀원이 나중에 rule_engine에 열을 추가해도 (1)이 자동 우선되니
내 코드는 안 바꿔도 됨. 이 어댑터를 먼저 만들어."

후속: "옵션 나 (tier별 파일 분리). 이유: 3계층 어댑터 구조 자체가 특허·논문
포인트라, 디렉토리 구조로 데이터 출처 분리가 드러나야 해."

→ src/drawing_agent/data/{adapter,tier1_ruleengine,tier2_urs,tier3_derive,
  tier4_manual_stub}.py 생성 (Phase A1).
→ 각 tier 가 자기 이름으로 source 태그 박음 (재현가능성 + 청구항).

### M5. cross-room connects_to 는 Phase B로 미룸

사용자: "A1은 same-room chain만. cross-room connects_to는 도메인 추론값이라,
검증 없이 지금 박지 말고 P2 수식 만들 때(B단계) 같이 채워. P2 수식이 있어야
'이 link가 점수에 맞게 작동하는지' 보면서 검증하며 넣을 수 있어. 검수자 없는
추론값은 P3·P5처럼 신중히 다루는 원칙 그대로 적용."

→ tier3_derive 는 same-room chain 만 처리 (test_no_cross_room_chain 강제).
→ cross-room link 는 Phase B 에서 tier4_manual_stub 으로 검증과 함께 채움.

### M6. 절대 규칙

- `src/rule_engine/` 와 `GMP_Layout_Logic_0510.xlsx` **수정 금지** (팀원 원천).
- 보충 데이터는 `examples/` 시나리오 JSON 이나 `src/drawing_agent/kb/` 에만.
- 두 영역은 공유 JSON 스키마(계약)로만 통신, import 금지.

### M7. 기록 규칙 (CLAUDE.md "작업 기록 규칙")

- `docs/PROGRESS.md` — 진행 상황 한 줄 누적
- `docs/decisions.md` — 결정 / 이유 / 근거 (ISPE·ISO 조항)
- `prompts.md` — 사용자 주요 지시 시간순 누적 (이 파일)
- `README.md` — 커밋 한 줄 로그 + 모듈 구조

세션 시작 시 PROGRESS.md / decisions.md 부터 읽고 이어감 — 처음부터 다시 안 함.

### Phase 진행 매핑

| 사용자 지시 | 반영 위치 |
|---|---|
| M1 CLAUDE.md 원칙 | 모든 추천에 적용 |
| M2 CP-SAT 결정 | docs/decisions.md D-003 (Phase C 진입 시 작성 예정) |
| M3 P3·P5·P8 보류 | src/reward/scorer.py — `P_DEFERRED` |
| M4 4-tier 어댑터 | src/drawing_agent/data/ (D-001) |
| M5 cross-room 보류 | tier3_derive same-room only (D-002), Phase B 에서 tier4 |
| M6 코드 경계 | tier1 이 rule_engine 무수정 자동 우선 |
| M7 기록 규칙 | docs/PROGRESS.md, docs/decisions.md, 이 파일, README |

---

## 2026-05-29 — M8: Phase B1 진행 지시 (P-series 수식 P1·P2·P6·P7)

### 사용자 요청 요약

- 새 세션 시작. PROGRESS / decisions / D-007 까지 읽고 한 줄 요약 후 B1 진입.
- **P1** (flow_monotonicity): `sort_order` 다른 장비쌍에만 역류 페널티,
  같은 `sort_order` (D-003 병렬) 은 중립. 근거 주석 `ISPE 7.9`.
- **P2** (adjacency): `connects_to` (직렬) + `co_locate_group` (같은방 병렬
  응집) 둘 다 반영, 별개 항. 근거 `ISPE 7.5`.
- **P6** (cleaning_access): `ISO 14644-4 §6`. 데이터(`clearance_m`) 부재면
  중립 가드.
- **P7** (compactness): 면적 효율.
- **P3·P5·P8**: 데이터 null → 보류(분모 제외).
- **정규화 분모** = 활성 4개 (P1+P2+P6+P7) 가중치 합.
- **검증**: 작은 테스트가 아니라 팀원 65장비 fixture 전체로 돌려서 NaN/None
  없이 점수 + 4개 P 표 보고.
- `src/rule_engine/` 수정 금지.
- 끝나면 PROGRESS/decisions 갱신.

### 반영 위치

- `src/reward/scorer.py` — `_p1_flow_monotonicity` / `_p2_adjacency`
  / `_p6_cleaning_access` / `_p7_compactness` 채움 + 정규화 분모 동적화.
- `tests/test_reward.py` — P-series 검증 10건 추가.
- `docs/decisions.md` — D-008 신규.
- `docs/PROGRESS.md` — Phase B1 완료 + B2 cold-start guide.
- 회귀: 56 → 66 passed, 1 skipped, 0 fail.

### 핵심 보고 (사용자 요구한 표)

| Key | Status | W | Raw | Contrib |
|---|---|---:|---:|---:|
| P1_flow_monotonicity | active | 10 | 1.0000 | 10.000 |
| P2_adjacency | active | 6 | 1.0000 | 6.000 |
| P6_cleaning_access | skipped_no_data | 4 | None | None |
| P7_compactness | active | 3 | 0.4387 | 1.316 |

measured_denominator = 19.0 / active_denominator(상수) = 23.0 /
**normalized = 0.9114** (= 17.316 / 19).

- P6 = None 인 이유: fixture 의 `clearance_m` 가 65/65 모두 미채움.
  CLAUDE.md epistemic honesty 원칙 — proxy 0.5 plug 금지. 분모에서 자동 제외.
- P1 = 1.0 인 이유: tier3 (D-007) 가 `connects_to` 를 same-room sort_order
  chain 으로 채움 → 52 link 모두 forward. 이게 데이터-only baseline 의 천장.
- P2 = 1.0 인 이유: 모든 link same-room + 13 group 모두 단일 방 응집.
- P7 = 0.4387: 9 process 방 density 평균 (sweet 0.55 미달, R_WASHING 0.13
  등 빈 방 다수) → 면적 효율 개선 여지 = CP-SAT 가 풀어야 할 과제.

---

## 2026-05-29 — M9: D-008 silent 만점 진단 → D-009 좌표 기반 재구현

### 사용자 진단 (정확)

P1=1.0 / P2=1.0 이 layout=None 에서 나온 것이 의심됨 → 코드 사실 확인:
P1·P2·P7 모두 `layout` 인자를 받지만 본체에서 미사용. tier3 derive 의 데이터
일관성을 "측정" 했을 뿐 배치 품질이 아님 → S4(DP 만점) 같은 silent 만점 버그.

### 사용자 지시

> **핵심 원칙: 점수(P-series)는 "배치 품질(좌표 기반)"만 측정한다.**
> **"데이터 일관성"(tier3 가 connects_to 잘 채웠나 등)은 validation 이지 점수가 아니다.**

방향 1번 선택 — P1·P2·P7 모두 좌표 기반 재구현 + layout=None → None.
- P1: 흐름축 투영 단조성 (PPO 첫↔끝 방향).
- P2: co_locate_group 좌표 거리 + connects_to 좌표 거리. room_id 동일성 아님.
- P7: packing density (좌표 기반). 팀원 area_m2 평가 아님.
- P6: 이미 None 가드 OK. 본 수식 미구현 — return None 유지.
- 검증: 4 시나리오 strip-band 점수표. strip-band 가 P1·P2·P7 낮게 나와야 정상.

### 반영 위치

- `src/reward/scorer.py` — P1·P2·P7 좌표 기반 재구현 + 헬퍼 `_flow_axis`,
  `_proj`, `_placed_eq_iter`, `_placed_eq_by_name`, `_eq_center` 신설.
  D_REF=20m (P2), P7 sweet=0.50/half-band=0.40.
- `tests/test_reward.py` — 7건 layout=None 가정 테스트를 좌표 기반으로 재작성
  (5건 strip-band layout, 3건 합성 layout). 67 passed, 1 skipped.
- `docs/decisions.md` — D-009 신규 (좌표 기반 + 원칙 명시) + D-008 SUPERSEDED.
- `docs/PROGRESS.md` — D-008 SUPERSEDED 표기 + D-009 완료 + B2 cold-start.

### 핵심 보고 — strip-band 4 시나리오 점수표 (진짜 before 베이스라인)

| Scenario | Rooms | Eq | P1 | P2 | P6 | P7 | normalized |
|---|---:|---:|---:|---:|---:|---:|---:|
| mab_8000L | 28 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
| A_small_aseptic | 28 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
| B_large_multiproduct | 29 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
| C_closed_system | 25 | 66 | 0.6707 | 0.9046 | None | 0.2483 | 0.6779 |

전 시나리오 layout=None 호출 시 P1/P2/P7 모두 None ✓.

**관찰 / 사용자에게 보고 의무 사항**:
- P1 ≈ 0.64 — strip-band 격자 → 흐름축 ~35% 역행. 정상 (만점 아님).
- P7 ≈ 0.25 — CP-SAT 가 가장 크게 개선할 차원.
- **4 시나리오 P2/P7 동일값** — 룰엔진이 URS 차이를 잘 반영 안 함. 별도 이슈
  (rule_engine/ 수정 금지 — Phase B2 에서 확인).

---

## 2026-05-30 — M10: 시나리오 변별 책임 분리 (D-010)

### 사용자 진단 확정 + 방향

원인 (b) rule_engine 책임. 부속발견: 우리 솔버도 default 78500×42500 만 사용.
책임 분리 — 장비 사양 = 팀원 (도메인), 캔버스 = 우리 (배치).

옵션 2 (drawing_agent 가 culture_scale_L → 장비 sizing override) **거부**:
> 장비 치수는 공정 도메인 결정이지 배치 결정이 아님. scale-up rule 로 추정하면
> "검증 안 된 추론 데이터" → P3·P5·P8 보류 원칙 (epistemic honesty) 위배 +
> 논문 방어 약화.

옵션 3 (examples overrides 강화) 보류 — 1번 후 결과 보고 결정.

### 이번 할 일 (이미 완료)

1. ★ 솔버에 building dimension 흘리기. anti-corruption layer / tier 구조로 깔끔하게.
2. 4 시나리오 strip-band 재측정 (적용 전/후 비교).
3. D-010 결정 로그.

### 반영 위치

- `src/drawing_agent/data/building.py` **신규** — `resolve_building_dims(spec,
  urs_path) → (w, h, source_tag)`. 4-tier (룰엔진 → URS → derive 미구현 → default).
- `src/drawing_agent/floorplan.py` — `generate_floorplan(building_w_mm=None,
  building_h_mm=None, urs_path=None)` 시그니처. None → resolver fallback.
- `src/drawing_agent/data/__init__.py` — public export.
- `tests/test_data_adapter.py` — 6건 신규 (default, URS pickup, 4 distinct,
  bad URS fallback, generate_floorplan URS 자동, 명시 인자 우선).
- `docs/decisions.md` — D-010 신규.
- `docs/PROGRESS.md` — D-010 완료 + B2 cold-start.
- 회귀 73 passed, 1 skipped, 0 fail.

### 핵심 보고 (사용자 요구한 적용 전/후 표)

| Scenario | URS w×d (mm) | Before P1/P2/P7/norm | After P1/P2/P7/norm |
|---|---|---|---|
| A_small | 60000×30000 | 0.6396 / 0.9046 / 0.2483 / 0.6615 | 0.6309 / **0.9136** / **0.3051** / 0.6687 |
| mab_8000L | 78500×42500 | 0.6396 / 0.9046 / 0.2483 / 0.6615 | 0.6396 / 0.9046 / 0.2483 / 0.6615 |
| C_closed | 60000×40000 | 0.6707 / 0.9046 / 0.2483 / 0.6779 | **0.6974** / 0.9136 / 0.2595 / **0.6965** |
| B_large | 100000×52000 | 0.6396 / 0.9046 / 0.2483 / 0.6615 | 0.6260 / **0.8898** / 0.2574 / 0.6511 |

- **4 시나리오 모두 distinct** (norm 0.6511~0.6965) — "URS 다르면 배치 다르다" 살아남.
- **A_small (좁은 캔버스) → 자동 compact** (P7 0.25→0.31): 논문 valid 신호.
- **B_large (넓은 캔버스) → 장비 흩어짐** (P2 0.90→0.89): 일관.
- **C_closed (방 25개 + 작은 캔버스) → 최고 norm**: 컴팩트 + PPO 짧음.
- **mab_8000L (default dim) 변화 없음**: 검산 OK.

**변동 폭 작은 이유 보고**: 룰엔진의 장비 변별 부재 (장비 65개 동일).
강한 분리는 옵션 1 (팀원 협의, 사용자 별도) 후. CP-SAT (Phase C) 가 더
자유로운 배치 → 캔버스 변별이 점수에 더 크게 흘러갈 것 예상.

---

## 2026-05-30 — M11: Phase B2 — before baseline 저장 (D-013)

### 사용자 지시

- B1.5 좋음, 변동 폭 좁은 거는 버그 아니라 예상된 중간 상태로 정직 기록.
- B2 — 4 시나리오 strip-band 점수 + 6종 geometric quality 를
  `output/baselines.json` 으로 저장. 논문 "before" 기준점.
- 각 점수에 메타 (시나리오명, URS dim, 측정 시각, 한계 주석) 박기. 향후
  "장비 변별 후" "CP-SAT 후" 비교 시 차이 추적 가능하게.
- 재현 가능 (결정론적). 두 번 돌려 동일값 확인.
- decisions.md D-013 — baseline 확정 + 약한 변동 폭이 "장비 미변별 +
  CP-SAT 전" 의 예상된 한계임을 명시. "before → after" 서사의 출발점.

### 반영 위치

- `scripts/baselines.py` 신규 — `python -m scripts.baselines [--check]`.
- `output/baselines.json` 신규 (354 줄, schema_version=1.0, decision_anchor=D-013).
  - schema/meta 외에 limitations 5건 + expected_variation_note 박음.
  - building_dim_source (tier2_urs / tier4_manual_stub_default) 도 기록.
- `docs/decisions.md` — D-013 신규.
- `docs/PROGRESS.md` — B2 완료 + Phase C 또는 B3 cold-start guide.
- 회귀 73 passed, 1 skipped (기존 유지). 결정론 --check 통과.

### 핵심 보고 — output/baselines.json 요약

| Scenario | URS dim | P1 | P2 | P6 | P7 | norm | geo total | hard | soft |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A_small_aseptic | 60000×30000 | 0.6309 | 0.9136 | None | 0.3051 | 0.6687 | 121.50 | 0 | 1 |
| mab_8000L | 78500×42500 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 | 121.68 | 0 | 1 |
| C_closed_sys | 60000×40000 | 0.6974 | 0.9136 | None | 0.2595 | 0.6965 | 127.06 | 0 | 0 |
| B_large_multi | 100000×52000 | 0.6260 | 0.8898 | None | 0.2574 | 0.6511 | 121.67 | 0 | 1 |

**핵심 명시 (논문 서사 출발점)**: 변동 폭 좁음 (~7%p) 은 버그 아닌 예상된
중간 상태. (1) 장비 변별 부재 — 사용자/팀원이 URS 3.6 채운 뒤 rule_engine
이 그를 읽도록 연결 예정 (별도 진행). (2) CP-SAT 미도입 — Phase C. 두
요인 해소 시 변동 폭 커지는 것이 정량 신호. 현 baselines.json 은 두 요인
*없을 때* 의 진짜 floor.

hard violation 4 시나리오 모두 0 = 룰엔진 출력이 hard 제약은 만족 (정상).

---

## 2026-05-30 — M12: B3 NNE 모범 배치 골든 (D-014)

### 사용자 지시

- `docs/reference/nne_equipment_layout.md` 먼저 읽기 (사용자가 NNE Pharmaplan
  Doc 0617C05016 정리).
- B3 = 점수 수식 타당성 검증 (C 전 안전판). NNE 모범 배치가 strip-band 보다
  높은 점수 나와야 함, 특히 P1·P2.
- 방법 B (정밀 좌표 X, 구조만). 매핑워크북 F1~F10 보류.
- fixture: `tests/fixtures/golden_nne_layout.json`. 출처 명시 필수.
- NNE < strip-band 면 점수 수식 진단 + 보고 후 보정.
- D-014 — NNE golden 도입 + 목적 + 출처 + 한계.

### 반영 위치

- `tests/fixtures/golden_nne_layout.json` 신규 — RuleEngineOutput 호환 spec +
  방별 layout_rects_mm (16 rooms / 70 eq / 62000×42000mm 캔버스).
- `scripts/golden_nne.py` 신규 — `load_golden_nne_spec_and_layout()` (방 안
  장비는 row-major auto-pack), `compare_with_baseline()`, CLI 표 출력.
- `tests/test_golden_nne.py` 신규 — 7 회귀 (NNE 우위 보장).
- `docs/decisions.md` D-014, `docs/PROGRESS.md` B3 완료, `README.md` 한 줄.
- 회귀 80 passed, 1 skipped (73 → 80, +7).

### 핵심 보고 (사용자 요구한 표)

| Layout | P1 | P2 | P6 | P7 | norm |
|---|---:|---:|---:|---:|---:|
| **NNE_golden** | **0.6986** | 0.9079 | None | **0.4366** | **0.7233** |
| A_small_aseptic | 0.6309 | 0.9136 | None | 0.3051 | 0.6687 |
| mab_8000L | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
| C_closed_sys | 0.6974 | 0.9136 | None | 0.2595 | 0.6965 |
| B_large_multi | 0.6260 | 0.8898 | None | 0.2574 | 0.6511 |
| strip-band avg | 0.6484 | 0.9054 | — | 0.2676 | 0.6694 |
| **Δ (NNE − sb avg)** | **+0.050** | +0.003 | — | **+0.169** | **+0.054** |

**합격 — P-series 수식이 전문가 배치를 strip-band 보다 높게 평가**.

### P 별 해석

- **P1 +0.05**: NNE 의 6 PPO 방 (Media → PurifIII) 좌→우 단일 stripe → 흐름축
  직선. strip-band 는 top/bottom 두 row + supply/return 끼움 → 흐름축 대각선
  zigzag → 일부 역행 페널티. 의도대로.
- **P2 ≈ 동등 (+0.003)**: group 응집은 둘 다 같은 방 안 row-major pack 으로
  자연 만점에 가까움. D_REF=20m 가 너무 관대 — CP-SAT 가 P2 에서 큰 개선분
  만들기 어려울 수 있다는 신호. 후속 보정 후보 (golden fixture 데이터로).
- **P7 +0.17**: NNE 방 면적 (Seed 50/Ferm 100/PurifI 80/Storage 30) 이 장비
  면적 합과 잘 맞아 outer_fill ≈ 0.5 sweet. strip-band 는 시각 축소 + stripe
  비율 고정 → outer_fill 낮음.
- **P6 None**: 둘 다 clearance_m 부재.

### 별도 주의

NNE spec 의 hard_violations=16, geo_total=-694 — NNE 실제 도면 위반 아님.
우리 fixture 단순화 (airlock 빈 list, supply↔return 직접 인접 등) 때문에 룰엔진
hard 검증이 페널티 부여. P-series 비교가 본 검증이라 별도 차원. 후속 옵션
(NNE fixture 에 airlock 보완).

---

## 2026-05-30 — M13: 진단(strip-band 한계) + Phase C0 CP-SAT 골격 (D-015)

### 사용자 지시 (진단)

C 들어가기 전 strip-band 가 정확히 뭘 하는지 코드 기준 진단. 코드 수정 0건.
보고: (a) 방/장비 배치 로직, (b) 입출력 구조, (c) CP-SAT 전환 시 재사용/폐기,
(d) 현재 한계. 어디부터 (층1/층2) CP-SAT 끼울지 정한 뒤 진행.

### 진단 결론 (사용자 채택)

- **층1 (방 배치) 부터 CP-SAT**.
- **층2 (장비)**: row-major 가 P2 group_term 을 0.9+ 포화시켜 leverage 작음 +
  변수 폭증 → C3 보류, strip-band `_place_equipment_grid` 그대로 재사용.
- 재사용: `Layout`/`PlacedRoom`/`Rect` 자료구조, renderer, score 인터페이스,
  enrich_spec, resolve_building_dims, `_place_doors` 후처리.
- 폐기 (strip-band 특유): TOP_ROW/BOTTOM_ROW/AUX_LEFT/NC_RIGHT 하드코딩,
  9-stripe ratio, area 비례 분배, row-major pack 자동 축소.

### 사용자 지시 (C0)

- **단계적으로**. C0 = 가장 작은 검증 only.
- 방 2~3개만 (예: MEDIA, BUFFER, INOC), 캔버스 안에 안 겹치게.
- 변수: (x, y) 격자. 크기 w,h 는 area 에서 고정.
- 제약 (hard): 안 겹침 + 캔버스 안. 둘만.
- 목적함수: 없거나 좌상단 모으기.
- 출력: Layout 채워 renderer 로 SVG 한 장.
- 확인: feasible 해, Layout/renderer 재사용, 풀이 시간.
- 안 함: 점수 연동, 전체 방, adjacency/zone, 장비 CP-SAT, 정제실.
- `requirements.txt` 에 ortools 핀, `rule_engine/` 수정 금지.
- 새 파일 (constraint_compiler.py / cpsat_solver.py), strip-band fallback 보존.

### 반영 위치

- `requirements.txt` — `ortools==9.10.4067` 핀 (재현성).
- `src/drawing_agent/constraint_compiler.py` 신규 (`compile_minimal`).
- `src/drawing_agent/cpsat_solver.py` 신규 (`solve_minimal` → Layout + SolveReport).
- `src/drawing_agent/layout_solver.py` **수정 0줄** (strip-band 보존).
- `tests/test_cpsat_c0.py` 신규 (8 회귀).
- `output/floorplan_c0_cpsat_3room.svg` 생성.
- `docs/decisions.md` D-015, `docs/PROGRESS.md` C0 완료 + C1 cold-start,
  `README.md` 한 줄.
- 회귀 80 → **88 passed**, 1 skipped, 0 fail.

### 핵심 보고 — C0 검증 결과

| 확인 항목 | 결과 |
|---|---|
| CP-SAT feasible 해 | ✓ OPTIMAL (code 4), objective 46.0 |
| 풀이 시간 (방 3개) | **20.12 ms** (즉시, 정상) |
| 안 겹침 sanity | ✓ PASS |
| 캔버스 안 sanity | ✓ PASS (78500×42500mm) |
| Layout 재사용 | ✓ 기존 `Layout`/`PlacedRoom`/`Rect` 타입 그대로 |
| renderer 재사용 | ✓ render(spec, layout) 코드 수정 0줄, SVG 23,819 bytes |
| SVG 산출물 | `output/floorplan_c0_cpsat_3room.svg` (0.3ms 렌더링) |
| 결정론 | ✓ 두 번 풀이 좌표 동일 (num_search_workers=1) |
| strip-band fallback | ✓ 기존 `solve()` 수정 0줄, 그대로 동작 |

좌표 (격자 → mm, 좌상단 모으기 결과):
- R_INOCULATION (81m²): (0, 0) 9000×9000
- R_MEDIA_PREP (196m²): (0, 9000) 14000×14000
- R_BUFFER_PREP (400m²): (14000, 0) 20000×20000

---

## 2026-05-30 — M14: Phase C1a (D-016) 전체 방 + hard 제약

### 사용자 지시

- 단계적 진행. C1a = "16개 방 전부가 hard 제약 안에서 feasible + 시간 감당".
- 변수: 전체 spec.rooms (x, y, w, h) 직사각, w·h 분리.
- area_m2 범위 ±10% 정도 (feasible 여지).
- hard 제약: 안 겹침, 캔버스, zone/category 분리, adjacency 인접,
  supply↔return 직접 연결 금지.
- 목적함수: 단순 (좌상단 또는 없음). P-series 는 C1b.
- 확인: feasibility / 시간 / SVG.
- infeasible/timeout 진단 + 완화 옵션 보고.
- strip-band 보존, rule_engine 수정 금지. D-016 작성.

### 반영 위치

- `src/drawing_agent/constraint_compiler.py` — `compile_c1a()` 추가 +
  사이징 상수 `ROOM_AREA_TO_SIDE_FACTOR=1.4 → 1.0` 정직화 + 모듈 상수
  `ASPECT_MIN=0.7 / MAX=1.4`, `ADJ_MAX_DEFAULT_MM=25000`, `RoomVarsC1a` /
  `CompiledModelC1a` dataclass.
- `src/drawing_agent/cpsat_solver.py` — `solve_c1a()` 추가, 결정론 강화
  (`max_deterministic_time = time_limit × 4` + `random_seed=0`).
- `tests/test_cpsat_c1a.py` 신규 (10 회귀).
- `output/floorplan_c1a_28room.svg` 생성.
- `docs/decisions.md` D-016 / PROGRESS.md C1a 완료 + C1b cold-start /
  README.md / 이 파일.
- 회귀 88 → **98 passed**, 1 skipped, 0 fail.

### 핵심 진단 + 결과

| 단계 | zones | adj | factor | 결과 |
|---|---|---|---|---|
| 1차 (default) | ON | ON | 1.4 | INFEASIBLE 1080ms |
| 격리 | ON | OFF | 1.4 | INFEASIBLE (zones 가 원인) |
| 격리 | OFF | ON | 1.4 | FEASIBLE (30s timeout, 풀이 가능 검증) |
| **정직화** | ON | ON | **1.0** | **FEASIBLE 500ms** ← 채택 |

INFEASIBLE 근본 원인: `ROOM_AREA_TO_SIDE_FACTOR=1.4` → 방 한 변 √area×1.4 →
면적 1.96× 부풀음 → aux stripe (0.20W=15.5m × 42.5m) 안에 12방 못 들어감.

해결: factor 1.4 → 1.0 (정직). aspect [0.7, 1.4] 만으로 자연 변동.

### C1a 검증 결과 (mab_8000L 28방, 5s)

| 항목 | 값 |
|---|---|
| status | FEASIBLE |
| **첫 feasible 시간** | **500ms** |
| 5s 종료 objective | 1650 (좌상단 모으기 임시) |
| 28방 모두 좌표 | ✓ |
| 안 겹침 / 캔버스 / adjacency 25m | ✓ / ✓ / ✓ |
| renderer 재사용 (0줄 수정) | ✓ SVG 68KB |
| 결정론 | ✓ 두 번 풀이 좌표 동일 |
| SVG | `output/floorplan_c1a_28room.svg` |

---

## 2026-05-30 — M15: Phase C1b (D-017) P-series surrogate + 첫 before→after

### 사용자 지시

- 목적함수에 P-series surrogate 얹기. P1 + P7 (P2 는 포화라 기대 안 함).
- 4 시나리오 CP-SAT 측정 + strip-band(`baselines.json`) + NNE golden 비교표.
- 기대: CP-SAT > strip-band, 가능하면 ≥ NNE.
- 인지 2가지 (보고에 명시):
  1. CP-SAT factor 1.0 vs strip-band area 비율 — 방 크기 정의 다름.
  2. adjacency 6 pair (room↔room) 만 모델, 35건 (room↔airlock) 모델 밖.
     NNE golden 과 비교에 주는 영향.
- 풀이 시간 + status 보고. 결정론 유지. strip-band/rule_engine 보존.

### 반영 위치

- `src/drawing_agent/constraint_compiler.py` — `compile_c1b()` 추가.
  `compile_c1a` 에 `add_compactness_objective: bool=True` 플래그 추가.
  `AdjPairVars` (adjacency abs(dx)/abs(dy) 변수 expose) — C1b cost 재사용.
- `src/drawing_agent/cpsat_solver.py` — `solve_c1b()` 추가.
- `tests/test_cpsat_c1b.py` 신규 (8 회귀).
- `output/floorplan_c1b_mab_8000L.svg` 생성.
- decisions.md D-017 / PROGRESS.md C1b 완료 + C2/C3 cold-start / README.md /
  이 파일 (M15).
- 회귀 98 → **106 passed** (+8), 1 skipped, 0 fail.

### 핵심 보고 — 4 시나리오 비교표 (P1-only: p1=500, p2=0, tie=0, 10s)

| Scenario | strip-band | CP-SAT C1b | Δ |
|---|---:|---:|---:|
| A_small_aseptic | 0.6687 | **0.7122** | **+0.0435** |
| mab_8000L | 0.6615 | 0.6527 | −0.0088 |
| C_closed_sys | 0.6965 | 0.6405 | −0.0560 |
| B_large_multi | 0.6511 | **0.6658** | **+0.0147** |
| **avg** | **0.6694** | **0.6678** | **−0.0017** |
| NNE_golden | — | 0.7233 | — |

모두 OPTIMAL 도달 (726~2584ms). 결정론 통과.

**디폴트 (P1=100, P2=60, tie=1) 는 더 저조** (avg Δ −0.033) — P2 surrogate 가
P1 과 충돌, tie-breaker 가 PPO 단조 방해 → timeout. P1-only 권장.

### 핵심 진단

1. **factor 정책 차이** (사용자 인지 1): CP-SAT (방 한 변 √area × aspect
   [0.7,1.4]) vs strip-band (area_m2 stripe 비례 + 시각 축소). 방 사이즈
   정의가 다름 → 점수 비교 시 *방 사이즈* 자체가 변동.
2. **adjacency room↔airlock 35건 모델 밖** (사용자 인지 2): 전실 (PAL/MAL)
   미편입 → P2 link 거리에 통과 무시. NNE golden fixture 도 단순화로 같이
   무시 → 본 비교 OK. *실제 GMP 도면* 평가 시 차이 발생 가능. **C2 에서 결정**.
3. **P1 surrogate ≠ 실제 P1 점수**: surrogate=방 단위, 실제=장비 흐름축 투영.
   같은 방 안 row-major pack 으로 sort_order row 간 역행 → 진짜 P1 향상은
   **C3 (장비 CP-SAT)** 가 가야 가능.
4. **NNE 까지 격차 +0.054**: 핵심은 P7 (방-장비 면적 균형). NNE 0.44 도달은
   B-001 (시각 축소 분리) + C3 가 필요.

### 사용자 결정 받을 사항 (D-017 후속)

1. solve_c1b default weight (P1=100, P2=60, tie=1) → P1-only (500, 0, 0) 변경?
2. **C2 (airlock 편입) vs C3 (장비 CP-SAT)** 중 어느 것 먼저? 진짜 P1 향상에는 C3.

---

## 2026-05-30 — M16: Phase C3a (D-018) 장비 CP-SAT 착수 + B-001 시각 축소 분리

### 사용자 결정 (D-017 후속)

- Q1: weight P1-only (500, 0, 0). 임시.
- Q2: **C3 (장비 CP-SAT) 우선** > C2 (전실). 진짜 P1·P7 향상은 장비.
- **단계적**: C3a (방 1개 5장비) → C3b (쉬운 방 여러 개) → C3c (정제실1 22장비).
- B-001 백로그 같이 정리 — CP-SAT 는 실제 W_mm, 시각축소는 renderer 로.
- 검증 질문: ① row-major 보다 P1·P7 향상? ② 풀이 시간? ③ 실제 W_mm 기준 P7
  이 strip-band 시각축소 대비 어떻게?
- D-018: D-015 부분 재검토 + C3a 착수.

### 반영 위치

- `src/drawing_agent/layout_solver.py` — `_place_equipment_grid(use_actual_mm: bool=False)`
  플래그 추가. default 무변경 (기존 strip-band 동작 보존).
- `src/drawing_agent/constraint_compiler.py` — `compile_room_c3a()` 추가.
  EquipmentVarsC3a / CompiledRoomC3a / C3A_* 상수.
- `src/drawing_agent/cpsat_solver.py` — `solve_room_c3a()` 추가.
- `tests/test_cpsat_c3a.py` 신규 (8 회귀).
- decisions.md D-018 / PROGRESS.md C3a 완료 + C3b cold-start / README.md /
  이 파일 (M16).
- 회귀 106 → **114 passed** (+8), 1 skipped, 0 fail.

### 핵심 보고 — R_MEDIA_PREP 5장비 3-mode 비교 (10×10m=100m² 방)

| Mode | inner | outer_fill | outer | **P7_room** | P1_local |
|---|---:|---:|---:|---:|---:|
| A row-major **시각축소 (0.8x)** | 0.206 | 0.118 | 0.046 | **0.126** | 1.000 (왜곡) |
| B row-major **실제 W_mm** | 0.570 | 0.684 | 0.541 | **0.556** | 0.500 |
| **C CP-SAT 실제 W_mm** | **0.765** | **0.510** | **0.975** | **0.870** | **0.750** |

**핵심 발견 — 사용자 3개 질문 답**:

1. **row-major 대비 P1·P7 향상?** ✓ CP-SAT vs row-major 실제: **P7_room +0.314,
   P1_local +0.250**. 장비 CP-SAT 진짜 leverage 확인.
2. **풀이 시간?** 226ms (5장비, OPTIMAL). sub-second.
3. **시각축소 vs 실제 W_mm 기준 P7?** 0.126 → 0.556 → 0.870. 시각축소가 P7
   왜곡 (A 의 0.126 은 장비가 너무 작아져 outer_fill 망가짐). 실제 W_mm 으로
   분리하면 진짜 측정 가능. CP-SAT 가 outer_fill 0.510 (sweet 0.5 정확히) 잡음.

**부속 보고**:
- strip-band rect (54m²) 에선 INFEASIBLE — **방 rect 가 spec area 근처여야**.
  C1 (방 CP-SAT) 결과와 결합 필수. 통합은 다음 단계.
- A row-major 시각축소의 P1_local=1.0 은 가짜 신호 (장비를 좁은 일자로 깔아서
  명목상 단조 만족) — 시각축소 자체가 점수 측정 wrap 한 증거.

### 사용자 결정 받을 사항 (D-018 후속)

1. **C3b** (쉬운 방 여러 개) vs **C1+C3 통합** (4 시나리오 전체 파이프라인 vs
   baselines/NNE) 중 어느 것 먼저?
2. B-001 default 변경 (`use_actual_mm=True` 기본화) — baselines.json 재생성
   필요 (점수 정의 변경 영향). 지금 안 함.

---

## 2026-05-30 — M17: Phase C3b (D-019) 장비 있는 모든 방 sweep + 정제실1

### 사용자 결정 (D-018 후속)

- **Q1: C3b 먼저** (통합 아직 X). 정제실1 infeasible 위험 1순위 → 방별
  지도부터.
- Q2: B-001 default 변경 안 함 (지금). C1+C3 통합 후 일괄.
- 순서: 쉬운 방 (장비 적은 순) → 정제실1 마지막 강조.
- 각 방 row-major(실제) 대비 P7·P1 + 풀이시간 + feasible + 방 rect 충분 여부.

### 반영 위치

- `scripts/c3b_room_map.py` 신규 — 13방 sweep + 정제실1 강조.
- `output/c3b_room_map.json` (결정론 저장).
- `tests/test_cpsat_c3b.py` 신규 (4 회귀).
- decisions.md D-019 / PROGRESS.md C3b 완료 + C1+C3 통합 cold-start /
  README.md / 이 파일 (M17).
- 회귀 114 → **118 passed** (+4), 1 skipped, 0 fail.

### 핵심 보고 — 13방 sweep 결과

**13/13 모두 feasible. INFEASIBLE 0건. 정제실1 fallback 불필요.**

| Room | n | density | RM P7 | CP P7 | ΔP7 | ΔP1 | status | ms |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| R_CIP_SUPPLY | 1 | 0.167 | 0.583 | 0.583 | 0 | — | OPT | 24 |
| R_WASHING | 1 | 0.125 | 0.531 | 0.531 | 0 | — | OPT | 0 |
| R_CELL_BANK_STORAGE | 2 | 0.100 | 0.407 | 0.431 | +0.024 | 0 | OPT | 12 |
| R_PREPARATION | 2 | 0.188 | 0.578 | 0.587 | +0.009 | 0 | OPT | 6 |
| R_IPC | 3 | 0.090 | 0.374 | 0.417 | +0.043 | 0 | OPT | 9 |
| R_DS_STORAGE | 4 | 0.096 | 0.380 | 0.351 | −0.028 | 0 | OPT | 41 |
| R_HARVEST | 4 | 0.340 | 0.829 | 0.801 | −0.028 | **+0.667** | OPT | 12 |
| R_INOCULATION | 4 | 0.279 | 0.511 | **0.757** | **+0.245** | +0.250 | OPT | 26 |
| R_BUFFER_PREP | 5 | 0.219 | 0.633 | 0.615 | −0.018 | +0.250 | FEA | 5003 |
| R_MEDIA_PREP | 5 | 0.390 | 0.556 | **0.870** | **+0.314** | +0.250 | OPT | 223 |
| R_CELL_CULTURE | 6 | 0.122 | 0.429 | 0.438 | +0.009 | +0.286 | FEA | 5003 |
| R_PURIFICATION_2 | 6 | 0.270 | 0.500 | **0.722** | **+0.222** | **+0.556** | OPT | 4421 |
| **R_PURIFICATION_1** | **23** | **0.390** | **0.259** | **0.777** | **+0.518** | −0.010 | **FEA** | **5003** |

**평균**: P7 0.505 → **0.605 (+10%p)**, P1 0.696 → **0.911 (+21.5%p)**.

### R_PURIFICATION_1 (정제실1) 강조 — 사용자 1순위 위험

- spec area = 350.4 m², rect = 18.7×18.7 m (정사각)
- 23 장비, 합 = 136.5 m², density = 0.39
- row-major 실제: P7=0.259, P1=0.492
- CP-SAT: **FEASIBLE 5003ms, P7=0.777 (+0.518), P1=0.482 (−0.010)**
- ✅ **fallback 불필요. 정제실1 도 풀린다.** P7 향상이 13방 중 *최대*.

### 관찰

- density 큰 방에서 CP-SAT 효과 큼. 장비 적은 방은 row-major 도 OK.
- P1 향상 큰 방: R_HARVEST +0.67, R_PURIFICATION_2 +0.56, R_CELL_CULTURE +0.29.
- 정제실1 P1 −0.01: 23장비 sort_order 단조가 5s 안에 못 풀림 — 시간 더 주면
  향상 예상. C1+C3 통합 시 함께.
- 풀이 시간: 11/13 sub-second, 4 방 5s timeout 도달 (큰 방).

---

## 2026-05-30 — M18: Phase C1+C3 통합 (D-020) — 첫 진짜 before→after

### 사용자 결정 (D-019 후속)

- C1+C3 통합 승인. 4 시나리오 전체 파이프라인.
- 시간 예산 주의 (분 단위면 줄여야).
- 비교표: strip-band(before) vs CP-SAT 통합(after) vs NNE.
- CP-SAT 는 실제 mm, strip-band 는 시각축소 — 주석으로 명시 (공정성 단서).
- baselines.json 재생성 안 함 (통합 결과 안정 후).
- 정제실1 P1 통합에서도 timeout 으로 끌어내리는지 관심.

### 반영 위치

- `scripts/c1c3_pipeline.py` 신규 — solve_full_pipeline 함수.
- `solve_c1b()` — `aspect_min/max` 인자 추가.
- `compile_c1b()` — `aspect_min/max` 인자 추가 (compile_c1a 로 전달).
- `tests/test_cpsat_pipeline.py` 신규 (4 회귀).
- `output/c1c3_pipeline.json` (결정론 저장).
- decisions.md D-020 / PROGRESS.md C1+C3 완료 + C2/B-001 cold-start /
  README.md / 이 파일 (M18).
- 회귀 118 + 4 = **122 passed**.

### 3단계 진단·해결

| 단계 | aspect 정책 | 결과 |
|---|---|---|
| 1차 default | [0.7, 1.4] | INFEASIBLE 23/52 (44%). C1b 가 방 작게 풀음. |
| 2차 좁힘 | [0.9, 1.1] | mab +0.06 but A_small INFEASIBLE (캔버스 부족). |
| **3차 동적** | canvas vs spec area, threshold=1.0 | **채택** |

### 최종 비교표 (CP-SAT 실제 W_mm vs strip-band 시각축소)

| Scenario | strip-band (before) | CP-SAT C1+C3 (after) | Δ | time | fallback |
|---|---:|---:|---:|---:|---:|
| A_small_aseptic | 0.6687 | 0.6740 | +0.0053 | 4.0s | 6/13 |
| **mab_8000L** | 0.6615 | **0.7230** | **+0.0615** | 20.3s | 1/13 |
| **C_closed_sys** | 0.6965 | **0.7050** | **+0.0085** | 25.1s | 1/13 |
| B_large_multi | 0.6511 | 0.6534 | +0.0023 | 16.7s | 0/13 |
| **avg** | **0.6694** | **0.6888** | **+0.0194** | **66.1s** | 8/52 |
| NNE golden (ref) | — | 0.7233 | — | — | — |

### 핵심 보고

- **mab_8000L 0.7230 = NNE 0.7233 거의 도달** (격차 -0.0003)!
- **mab P7 0.2483 → 0.6756 (+0.43!)** — C3 효과의 핵심.
- **R_PURIFICATION_1 FEASIBLE 8s, fallback 안 함** — 사용자 1순위 관심 통과.
  rect 272m², density 0.50, P1 통합에서도 timeout 부담 작음 (8s 한계 적용).
- 전체 풀이시간 66s (95s → 66s 단축, 점수 거의 동일).

### 한계 명시 (사용자 인지)

- A_small INFEASIBLE 6/13: 캔버스 1800m² < spec area 합 2535m² (URS 자체 한계).
- B_large 미미: 큰 캔버스에 방 비례 안 커짐 (룰엔진 area 정책).
- P2 감소 (~−0.09): C3 가 P7 우선해서 group 응집 약화. C2 (전실) 또는 P2
  surrogate C3 박기 후.
- avg NNE 까지 격차 -0.034: mab 만 거의 도달.

### 사용자 결정 받을 사항 (D-020 후속)

1. **C2 (전실 편입)** — P2 감소 보완.
2. **C3 에 P2 surrogate 추가** — group 응집 회복.
3. **B-001 default 변경 (`use_actual_mm=True`)** — baselines.json 재생성.
4. URS 3.6 (팀원 별도) 후 4 시나리오 재측정.
