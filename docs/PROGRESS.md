# PROGRESS — 작업 진행 상황

## [2026-06-06] Phase 1.6: 동선 복도 인지 라우팅 (D-026) — 브랜치 `drawing/floorplan-v2`

사용자 지적(동선이 NC 방·벽 관통). flow_paths 복도 웨이포인트를 중심점 대신
복도 중심선상 [진입,진출]로 펼쳐 동선이 복도를 타고 흐르게(`_corridor_axis_points`).
Product 는 벽 가로지르기 정상(규정 3-2) 유지. drawing 7건 통과. `output/bench_v6_corridor.svg`.
한계: flow_paths 가 건너뛴 교차구역 점프(Gowning→Lobby)는 Phase 1.7(완전 확장)에서.

## [2026-06-06] Phase 1.5: 동선 직교(Manhattan) 라우팅 (D-025) — 브랜치 `drawing/floorplan-v2`

D-023 동선이 방 중심 직선(대각선)이라 긴 대각선이 도면 가로질러 시인성 저하.
**`_draw_flow_polyline` 를 L자 직교 라우팅**으로 변경(수평→수직 엘보, 종류별
오프셋 유지). 화살표는 노드 도착 다리에만, 직선 구간은 단일 세그먼트(누락 버그
수정). 결과: 대각선 클러터 제거, 복도 따라 흐르는 GMP 도면 가독성. 충실성
(flow_paths 1:1)은 유지. drawing 7건 통과. 산출 `output/bench_v5_ortho.svg/png`.
다음: Phase 3(도면 피드백 잔여 — NC↔D 복도분리/Grade C 도어삭제/Waste↔Material
분리/접경 Gowning+MAL-in).

## [2026-06-06] Phase 2: 면적 비례 treemap + is_airlock dedup (D-024) — 브랜치 `drawing/floorplan-v2`

정렬 G2(면적 왜곡, 피드백 #5)·G3(is_airlock dedup 취약) 해소.

- **G2 면적 비례 (squarified treemap)**: gradient 솔버 그려진/spec 면적 배율이
  0.54~5.84(왜곡). 원인=고정폭 컬럼 + `_alloc_dim` 종횡비 floor 클램프가 작은
  방 일괄 부풀림. **`_squarify`/`_place_treemap` 신규**(Bruls 2000) → NC·Grade D
  컬럼 treemap 배치. 결과: **Cell bank 20㎡→23㎡, Material storage 100㎡→116㎡
  (둘 다 1.16×, 5배 차이 올바르게 비례)** — 피드백 #5 정확히 해소. 공정행은
  supply↔return 단일행 one-way 토폴로지 유지 위해 미적용(잔여 비례차=의도적
  trade-off, corridor 비례 제외).
- **G3 is_airlock 명시 dedup**: 내부 Room 스키마에 `is_airlock`/`airlock_id`
  추가(이전 18→0 드롭, 이제 18/18 흡수). `_is_al_fake_room` 1차 신호로 사용
  (패턴+area==0 폴백). 견고성: 엔진이 전실 방에 area 줘도 flag 로 dedup.
- **검증**: 컬럼 배율 ≈1.16 균일, is_airlock 18/18, drawing+adapter 47 통과.
  산출 `output/bench_v4_treemap.svg/png`. alignment_audit 진행현황 갱신.
- **다음**: Phase 1.5(동선 직교 라우팅) → Phase 3(피드백 잔여: NC↔D 복도분리,
  Grade C 도어삭제, Waste↔Material 분리, 접경 Gowning+MAL-in).

## [2026-06-06] Phase 1: 동선 화살표 flow_paths 기반 + 방 누락 해소 (D-023) — 브랜치 `drawing/floorplan-v2`

정렬 감사 최대 gap G1 + 발견된 방 누락 버그 해소.

- **동선 화살표 재작성** (`renderer._emit_z9_flow_arrows`): 이제 `spec` 을 받아
  `spec.flow_paths` 4종(personnel 입/퇴·material·waste·product)을 실제 좌표로
  연결. 종류별 색+수직 오프셋+구간 화살표. 외부 노드→URS 방위 외곽 포트. product=
  벽 가로지르기. placeholder spec 은 토폴로지 휴리스틱 폴백(기존 함수 `_topology`
  로 리네임 보존). render() 가 z9 에 spec 전달.
- **방 누락 버그 발견·해소**: `cli draw` 가 기본 strip-band(`dynamic_rooms=False`)
  로 호출 → 하드코딩 공정순서 리스트에 없는 새 엔진 방을 드롭(**MEDIA/BUFFER
  공정실 포함 7방 누락**, 23/48). gradient(`=True`)는 31방 전부 배치(누락 0).
  cli draw 기본을 gradient 로 변경(+`--strip` 레거시, +누락 WARN). **strip-band
  코드 무수정**(baselines/golden 경계) — 렌더=gradient(full)/측정=strip(subset) 분리.
- **테스트**: `test_drawing_agent` 갱신(올바른 경로 gradient + 전실 dedup 반영) +
  신규 `test_no_real_room_omitted`(누락 가드)·`test_flow_arrows_follow_flow_paths`(G1).
  7건 전부 통과. 전체 **17 fail→13 fail / 100→106 pass**(회귀 0, 남은 실패=옛
  fixture R_MEDIA_PREP·옛 engine_e2e·reward = 사전 존재 legacy).
- **산출물**: `output/bench_v3_flowpaths.svg/png`(gradient+동선), `bench_v3_strip.svg`.
- **다음**: Phase 2 — is_airlock dedup 명시 소비 + area 비례 렌더(#5) + constraints/
  door_swing. (또는 Phase 1.5 동선 직교 라우팅 polish — 사용자 도면 검토 후 결정.)

## [2026-06-06] 고도화 착수 — Phase 0: 통합 벤치테스트 + 정렬 감사 — 브랜치 `drawing/floorplan-v2`

팀톡 "프로그래밍 마지막 단계 고도화" 3목표(①agent 통합 벤치 ②**룰엔진→drawing
정렬(최우선)** ③도면 gap→규칙보완) 착수. 룰엔진 6/2 push 분석 → 계획 단계화.

- **룰엔진 6/2 push 위치 확정**: `teammate/main`(별도 repo
  smartepic2026/rule_engine_validation_agent) `228c0ff..e05b85c`. 모노레포(origin)
  아님. 13→15룰(rule_14_acph, rule_15_gowning, rule_06 airlock dedup, rule_13 차압).
  **계약 변경 additive·non-breaking**: Room에 `is_airlock`/`airlock_id` 추가
  (AL 이중표현 해결), AirLock.area_m2 항상 채움(9/12), `flow_paths` 구조 불변.
- **사용자 결정**: ⓐ Phase 0부터 ⓑ 새 엔진 기준 진행, 수정 필요분은 우리가
  다(권한 보유). (prompts.md 2026-06-06 참조)
- **통합 벤치테스트**: raw 엔진 출력 추출 → `output/teammate_engine_v2_output.json`
  (48 rooms/18 AL). `cli draw` 직접 = 크래시(rationale 필드명), **어댑터
  (`adapt_external_dict`) 거치면 정상**(SVG `output/bench_v2_new_engine.svg`,
  rooms 23/AL 18/doors 39). → 통합 경로에 어댑터 단계 필수.
- **정렬 감사 `docs/alignment_audit.md`** 작성(D-022). 필드별 consumed/DROPPED
  표 + Top7 gap. **최대 gap G1**: 동선 화살표 `_emit_z9_flow_arrows`가 spec을
  인자로 안 받아 flow_paths 미사용, `"SUPPLY_CORRIDOR"` 패턴 휴리스틱으로
  재구성(renderer.py:606,634). G2: area_ratio/width_mm 무시(피드백#5).
  G3: is_airlock dedup이 ID패턴+area==0 휴리스틱에만 의존(취약).
- **다음**: Phase 1 — 동선 화살표를 flow_paths 4종(Person/Material/Product/Waste)
  기반으로 재작성.

## [2026-06-02] 도면 v3 — GMP 청정도 구배 토폴로지 (전문가 피드백 반영) — 브랜치 `drawing/floorplan-v2`

사용자(GMP 도면) 피드백 6건을 drawing_agent 에 반영. decisions.md **D-021**.

- **④ 도어 곡선 버그**: z6 swing arc 의 `sweep` 플래그가 반대로 박혀 호가
  hinge 반대편으로 오목(=여닫이 반대). 가로·세로 도어 모두 sweep 반전 →
  건축 표준 여닫이문. (renderer.py)
- **① 작은 방 세로 슬리버**: `_alloc_dim` water-filling 도입 — 면적 비례
  분배 + 각 칸 cross/max_aspect 미만으로 안 얇아지게 보정(합 보존, 흰공간 0).
  `_place_row_aspect`/`_place_stack_aspect`. (Inoc/Prep/Wash/Gowning 정상비율)
- **②③⑤ 토폴로지 재설계 → `_solve_gmp_gradient`** (dynamic_rooms=True 경로):
  가로 청정도 구배 **NC → Grade D → [D 세로복도] → Grade C 공정**.
  공정구역 = return(상)·공정행(상)·[가운]supply(중앙)·공정행(하)·return(하).
  - 양측 return 복도 모두 *실제 방*으로 배치(기존 bottom 은 annotation 뿐) →
    정제실 하행 포함 전 공정행이 return 인접 (②).
  - 가운룸(C)을 D복도↔supply 접점에 게이트로 배치 + 합성 도어 2개 (③).
  - NC 를 D 와 같은 쪽으로 모아 NC→D→C 한 방향 구배 (⑤).
- **⑥ 동선 화살표 재작성** (`_emit_z9_flow_arrows`): one-way flow —
  supply(좌→우) → 공정행 수직 통과(상행 ↑/하행 ↓) → 양측 return(우→좌) →
  D복도(하→상 진입). AL drop 은 supply_cy 기준 방향 결정, PAL/MAL/CAL 색 구분.
- **AL 폭 절대상한 3.8m** (`_place_al_edge`) — 큰 방(정제실)에서 에어록이
  방의 40%까지 커지던 문제. 실제 전실 크기로.

- **경계 보존**: 하드코딩 strip-band 경로(dynamic_rooms=False)는 **무수정** →
  baselines.json / golden NNE / 우리 default URS 보존. 새 토폴로지는 외부(소연)
  spec = dynamic_rooms=True 에서만. solve_perimeter_ring 도 그대로(토폴로지 다양성).
- **회귀 검증 (stash diff)**: 변경 전/후 모두 **17 fail / 100 pass / 6 err** (동일).
  유일한 런간 차이는 `test_c1a_deterministic`↔`test_c1b_deterministic` 가
  번갈아 — CP-SAT 타이밍 의존 테스트의 *기존* flakiness(내 코드 무관).
  실패 17+err6 은 전부 옛 fixture(`R_MEDIA_PREP`)·옛 엔진 e2e (엔진 교체 잔재).
- **산출물**: `output/presentation/` 5종 재생성(light+blueprint, svg+png) +
  `ppt_png/` 라이트 5종 갱신 + README 토폴로지 표/공통표현 갱신.
- **다음**: (a) 옛 fixture 테스트들 소연 ID 로 갱신(별도). (b) 선택 — 정제실
  하행을 supply 위쪽 단일행으로 빼는 안(②-2, 흐름 단조성 ↑, 캔버스 가로↑)을
  쓸지 사용자 결정. 현재는 ②-1(양측 return) 채택. (c) CP-SAT 를 이 구배
  토폴로지의 zone 제약으로 확장(H3 를 NC/D/C 3구역으로).

> 위는 strip-band(휴리스틱) 도면 품질 개선. CLAUDE.md 의 솔버=CP-SAT 결정
> 불변 — 이 토폴로지는 CP-SAT zone 제약(H3)·목적함수의 도메인 근거가 됨.

## [2026-06-01] 소연 룰엔진 모노레포 통합 (옵션 2) — 브랜치 `integrate-soyeon-engine`
- **레포 이전**: origin = `smartepic2026/Layout-Generator` (공용), 기존 헤민 레포는 `hyemin` 리모트로 보존. teammate = `smartepic2026/rule_engine_validation_agent` (소연 최신 엔진, private, Hyemin 협업자 추가됨). 베이스라인 main 푸시 완료(c19d318).
- **구조**: ① `src/contract/` 신설 — 우리 pydantic 계약(schemas/validators/working_state/kb_loader/kb) 분리. ② `src/rule_engine/` = 소연 최신 엔진(dataclass models.py)으로 교체. ③ 소연 절대 import 64곳 → `src.` 접두사 정렬. ④ `cli.py rule-engine` = URS xlsx → 소연 엔진 → to_json → tier1 어댑터 → 우리 pydantic spec.
- **검증 완료**: CLI 3명령(rule-engine/draw/validate) + 드로잉 end-to-end(SVG 90KB) 통과. 테스트 102 passed.
- **다음 할 일 (follow-up)**: ① 옛 엔진 특정값 단언 테스트 15 fail/6 error 갱신 — 소연 출력 기준(방 ID `R_MEDIA_PREP`→`R_MEDIA_PREPARATION` 등). `test_engine_e2e.py`는 옛 pydantic 엔진 전용이라 대부분 obsolete(재작성 or 삭제 판단). fixture는 `tests/_legacy_spec.py` shim. ② 이 브랜치 PR 리뷰 후 main 병합. ③ 소연도 이제 이 레포에서 작업(옛 레포 아카이브) 합의됨.


> CLAUDE.md "작업 기록 규칙" — 매 세션 시작 시 이 파일부터 읽기.
> Phase/작업 하나 끝낼 때마다 한 줄. 중간에 멈출 때도 "현재 여기까지, 다음은 이것" 남기기.

---

## 큰 그림 (CLAUDE.md 결정사항)

순서: **데이터·수식·베이스라인 → CP-SAT 솔버 → 평가/산출물**

```
Phase A  데이터 인프라
  A1  4-tier 데이터 어댑터 + tier3 derive
  A2  (필요 시) URS / manual_stub 채움 — 현재는 stub 만

Phase B  Before 베이스라인 (수식 + 측정)
  B1  P-series 수식 구현 (P1·P2·P6·P7 active, P3·P5·P8 보류 유지)
  B2  strip-band 점수를 before 베이스라인으로 측정 → output/baselines.json
  B3  Golden fixture 검증 (BioPhorum 2×2000L, Witcher&Silver 18-cleanroom)

Phase C  CP-SAT 솔버
  C1  constraint_compiler — RuleEngineOutput → CP-SAT model
  C2  cpsat_solver — ortools 의존, 격자 해상도 결정
  C3  infeasible fallback (strip-band)

Phase D  평가 + 산출물
  D1  floorplan_v6.svg 생성 (4 시나리오)
  D2  strip-band vs CP-SAT 점수 비교 (표/차트)
  D3  decisions.md 정리 — 논문 method + 특허 청구항 원재료
```

---

## 진행 로그

### 2026-05-29 — Phase 0 (renderer 스타일 정합) [완료]
- floorplan_v2/v3/v4/v5 생성, AL 세모 제거, 선 검정 통일, 메타·라벨 위치 정리
- 장비 박스 자동축소 (방 안 들어가게)
- 한계: 자동축소가 0.25배까지 내려간 케이스 다수 → 옵션 3 가야 근본 해결

### 2026-05-29 — Phase A1 [완료]
- `src/drawing_agent/data/` 신설 (4-tier: ruleengine / urs / derive / manual_stub)
- `SourceTracker` + `enrich_spec()` orchestrator
- tier3: sort_order (process_step 파싱), bbox_m (mm→m), connects_to (same-room chain)
- `floorplan.py` 진입부에 wire-in
- 테스트 10건 추가 (전체 32 passed, 1 skipped)
- decisions.md: D-001 (4-tier 구조), D-002 (derive 규칙) 기록
- **결과**: baseline 165 필드 채움 (bbox_m=66, connects_to=46, sort_order=53), 모두 tier3_derive source
- **한계 / 이월**: cross-room connects_to 는 Phase B 에서 P2 수식 만들 때 검증과 함께

### 2026-05-29 — Phase A1.5 (anti-corruption layer + silent-failure 방어) [완료]
- 팀원 실제 출력 (RuleEngine_Output_for_DocAgent.md) 크로스체크 → 36건 mismatch + 4건 silent failure 발견
- D-003 anti-corruption layer 채택 — schema 에 팀원 필드명 박지 않음
- `schemas.py`: `extra="forbid"` → `"ignore"` (모르는 필드 흡수)
- `tier1_ruleengine.py` 에 변환 레이어 추가:
  - 필드명 매핑: room_id→id, cat→category, grade→clean_grade, DP→differential_pressure_Pa, ACPH→air_changes_per_hour, color→background_color, 투명%→transparency_pct, al_id→id, kind→type, doors→door_count, door_size→door_size_mm, target_id→target, gowning→gowning_type
  - WxDxH 합쳐진 문자열 파싱 (콤마 "2,000" 포함)
  - process_no → process_step alias
  - trailing space strip (Room/AL/장비 이름)
  - swing(descriptor) → notes 로 의미 보존
  - rationale severity+note → decision+reason 합성
- scorer 자체 버그:
  - S1: `_area_ratio_fit` — `current` 키 silent 0.5 default → `(layout, current 키, None)` 우선순위로 변경
  - S4: `_pressure_cascade_smoothness` — 모든 DP=0 일 때 silent 1.0 만점 → None 반환
  - `score()` 본체가 None 항목을 breakdown=null + total 미합산으로 graceful 처리
- 테스트 15건 추가 (47 passed, 1 skipped). 전체 회귀 없음
- decisions.md: D-003 anti-corruption layer 채택 이유 + 근거 기록

### 보류 (팀원 확인 후 처리)
- Airlock required 필드 (connects_higher/lower, area_m2) Optional 전환 — JSON 실물에 값 있는지 확인 후
- process_no 매핑 — alias 만 깔아둠. 팀원 키 확정되면 정리
- AL 이중표현 (rooms[] + airlocks[]) — 처리방식 결정 후

### 2026-05-29 — Phase A1.6 (D-005 / D-006 / D-007) [완료]
- 팀원 출력 추가 진단: process_no 가 JSON 컬럼에 미존재 (마크다운 §1.1) → tier3 sort_order silent 0 위험
- **D-005** `Equipment.process_step` → `process_no` rename + Pydantic `validation_alias=AliasChoices("process_no","process_step")` JSON 입력 양방향 호환
- **D-006** `Equipment.process_step` @property (read-only) — rule_engine 무수정 호환 (`rule_10_equipment.py:44` 의 속성 접근 회복). 15건 회귀 → 0
- **D-007** sort_order derive 전략 교체:
  - `Equipment.co_locate_group: Optional[str]` 신규 (같은 방 안 병렬 그룹 라벨)
  - tier3 우선순위 A→D: tier1 > process_no 파싱 > PPO rank 기반 > PPO 밖 보조방 rank 부여
  - `_full_room_rank()` 공통 헬퍼 (sort_order / co_locate_group 일관)
- **fixture**: `tests/fixtures/teammate_output_sample.json` (팀원 마크다운 65 장비 재구성)
- **검증**: sort_order 65/65, co_locate_group 65/65, 13 그룹, 단조 증가, tier1 우선 동작
- 테스트 9건 신규 (전체 56 passed, 1 skipped)

### 2026-05-29 — Phase B1 (D-008 1차 시도, spec-only) [SUPERSEDED by D-009]

D-008 으로 P1·P2·P7 을 spec-only 로 구현했으나 사용자 진단에서 silent 만점
버그 발견 — layout 인자를 받지만 본체 미사용. tier3 데이터 일관성을 "측정"
했을 뿐 배치 품질 측정 아니었음. 결과: 모든 fixture 가 P1=1.0/P2=1.0.

### 2026-05-29 — Phase B1 (D-009 좌표 기반 재구현) [완료]

- **원칙 명시 (D-009)**: 점수 = 배치 품질 (좌표 기반). 데이터 일관성 ≠ 점수.
  layout=None 시 P1/P2/P7 모두 명시적 None (= 측정 불가).
- **P1 flow_monotonicity** (W=10) — 흐름축 unit vector u = (마지막 PPO 방 중심)
  − (첫 PPO 방 중심). 각 장비 좌표 투영 proj. (i,j) 쌍 중 sort_order 다른
  것에 대해 forward / (forward+reverse). 같은 sort_order = D-003 병렬 = 분모
  제외. 근거: ISPE Vol.6 §7.9 (one-way flow).
- **P2 adjacency** (W=6) — (a) co_locate_group 멤버 좌표 평균 거리 d_g →
  `s_g = max(0, 1 − d_g / 20m)`, 그룹 평균. (b) connects_to link 좌표 거리
  d_link → `s_link = max(0, 1 − d_link / 20m)`, link 평균. raw = 두 항 평균.
  근거: ISPE §7.5 (process flow grouping).
- **P6 cleaning_access** (W=4) — `clearance_m` + layout 둘 다 있어야 함.
  본 수식 미구현 (return None 유지). 근거: ISO 14644-4 §6.
- **P7 compactness** (W=3) — 좌표 기반 packing density. inner = sum(eq.rect)
  / 장비 외접 bbox, outer = `max(0, 1 − |env/room − 0.5| / 0.4)`. process 방
  평균. 근거: ISPE Vol.6 §1.
- **정규화 분모 동적**: `_measured_denominator` = 측정된 active 가중치 합.
  None 항 (P6) 분모 제외. 비교용 `_active_denominator`(상수 23) 도 노출.
- **strip-band baseline (4 시나리오, layout 부여)**:

  | Scenario | Rooms | Eq | P1 | P2 | P6 | P7 | normalized |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | mab_8000L | 28 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
  | A_small_aseptic | 28 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
  | B_large_multiproduct | 29 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
  | C_closed_system | 25 | 66 | 0.6707 | 0.9046 | None | 0.2483 | 0.6779 |

  전 시나리오 layout=None → P1/P2/P7 모두 None (silent 만점 차단 확인).

- **관찰**:
  - strip-band 가 P1 만점 아님 (≈0.64) — 격자 배치 → 흐름축 ~35% 역행. 정상.
  - strip-band 가 P7 매우 낮음 (≈0.25) — CP-SAT 가 가장 크게 개선할 차원.
  - **4 시나리오 P2/P7 동일값** — 룰엔진이 URS 변동을 잘 반영 안 함. 별도
    이슈 (룰엔진 영역 수정 금지, Phase B2 에서 사용자 보고 후 결정).
- 테스트 추가 + 좌표 기반으로 재작성 (67 passed, 1 skipped). 회귀 0건.
- decisions.md D-009 작성 + D-008 SUPERSEDED 표기.

### 2026-05-30 — Phase B1.5 (D-010 책임 분리 — 캔버스 = 우리) [완료]

- **진단 (B1 직후)**: 4 시나리오 strip-band 점수 동일 → 원인 (b) rule_engine
  이 URS 의 culture_scale_L / n_product_types / building dim 을 spec 에 흘리지
  않음. 부속발견: 우리 솔버도 building dim 무시 (default 78500×42500).
- **책임 분리 (D-010)**: 장비 사양 = rule_engine (도메인), 건물 캔버스 =
  drawing_agent (배치). 옵션 2 (drawing_agent 가 장비 sizing override) 거부 —
  검증 안 된 추론 데이터 = epistemic honesty 위배 + 논문 방어 약화.
- **구현**: `src/drawing_agent/data/building.py` 신규 — `resolve_building_dims`
  4-tier (tier1 룰엔진 / tier2 URS / tier3 의도 미구현 / tier4 default).
  `generate_floorplan(spec, urs_path=...)` 가 자동으로 URS dim 적용.
- **strip-band 점수 (D-010 적용 후)**:

  | Scenario | URS dim | P1 | P2 | P7 | norm |
  |---|---|---:|---:|---:|---:|
  | A_small_aseptic | 60000×30000 | 0.6309 | 0.9136 | **0.3051** | 0.6687 |
  | mab_8000L | 78500×42500 | 0.6396 | 0.9046 | 0.2483 | 0.6615 |
  | C_closed_sys | 60000×40000 | **0.6974** | 0.9136 | 0.2595 | **0.6965** |
  | B_large_multi | 100000×52000 | 0.6260 | 0.8898 | 0.2574 | 0.6511 |

  - 4 시나리오 모두 distinct (norm 0.6511 ~ 0.6965).
  - 작은 캔버스 (A_small) → P7 ↑ (자동 compact). 큰 캔버스 (B_large) → P2 ↓
    (장비 흩어짐). 논문 valid 신호 "같은 공정, 다른 건물 → 다른 배치".
- 테스트 6건 신규 (73 passed, 1 skipped). 회귀 0건.
- decisions.md D-010 작성.

**남은 한계 (사용자 별도 진행)**:
- 변동 폭 좁음 (P7 0.25~0.31) — 룰엔진 변별 부재. 옵션 1 (팀원 협의로
  scale/multi-product 반영) 은 사용자가 별도 진행.
- 옵션 3 (examples overrides 강화) 도 보류 — D-010 만으로 시나리오 분리는
  충족, 강화는 옵션 1 결과 본 후.

### 2026-05-30 — Phase B2 (D-013 before-baseline 저장) [완료]

- **scripts/baselines.py 신규** — 4 시나리오 strip-band P-series + 기존 6종
  geometric quality + hard/soft 를 결정론적으로 측정 → `output/baselines.json`.
  `--check` 옵션: 두 번 측정해 동일성 검증 (timestamp 제외 byte-identical).
- **output/baselines.json (354 줄)** — 시나리오별 메타 (urs_path, building_dim
  + source, rooms/eq count, PPO len) + P-series 전체 (raw/weight/contrib/status)
  + geometric_quality (total + breakdown + hard/soft count) + 한계 5건 +
  expected_variation_note.
- **메타에 박은 한계 5건** (논문 추적성):
  1. rule_engine 장비 변별 부재 (URS 3.6 연결 대기 — 팀원 별도 작업).
  2. CP-SAT 미도입 (Phase C 예정).
  3. P3·P5·P8 보류 (검수자 부재, epistemic honesty).
  4. P6 미구현 (clearance_m 부재 + 수식 후속).
  5. 정규화 분모 동적 (P6 빠진 19, 상수 23 도 노출).
- **요약 표 (생성 직후)**:

  | Scenario | URS dim | P1 | P2 | P6 | P7 | norm | geo total | hard | soft |
  |---|---|---:|---:|---:|---:|---:|---:|---:|---:|
  | A_small_aseptic | 60000×30000 | 0.6309 | 0.9136 | None | 0.3051 | 0.6687 | 121.50 | 0 | 1 |
  | mab_8000L | 78500×42500 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 | 121.68 | 0 | 1 |
  | C_closed_sys | 60000×40000 | 0.6974 | 0.9136 | None | 0.2595 | 0.6965 | 127.06 | 0 | 0 |
  | B_large_multi | 100000×52000 | 0.6260 | 0.8898 | None | 0.2574 | 0.6511 | 121.67 | 0 | 1 |

  결정론 `--check` 통과. hard violation 4건 전부 0 — 룰엔진 출력은 모든
  시나리오에서 hard 제약 만족 (정상).
- decisions.md D-013 작성.

**핵심 명시 (논문 서사의 출발점)**:
변동 폭 좁음 (norm 0.65~0.70, ~7%p) 은 버그 아니라 예상된 중간 상태.
두 요인 (장비 변별 + CP-SAT) 해소 시 변동 폭이 커지는 것이 "before → after"
정량 신호. 현 baselines.json 은 두 요인 *없을 때* 의 진짜 floor.

### 2026-05-30 — Phase B3 (D-014 NNE 모범 배치 골든) [완료]

- **목적**: P-series 수식이 "좋은 배치를 높게 평가" 하는지 검증. 안 그러면
  CP-SAT 가 임의 낮은 점수로 수렴할 위험 → 진단·보정 필요.
- **방법 B (구조 검증)**: 정밀 좌표 X, 그리드 근사 + 같은 방 안 row-major
  auto-pack. 좌표 정확성 아닌 구조 (PPO 순서, 인접, 응집) 만 보장.
- **파일**:
  - `docs/reference/nne_equipment_layout.md` (사용자 작성, NNE 도면 추출).
  - `tests/fixtures/golden_nne_layout.json` (16 rooms / 70 eq / 62000×42000 mm).
  - `scripts/golden_nne.py` (`python -m scripts.golden_nne`).
  - `tests/test_golden_nne.py` (7 회귀 — NNE 우위 보장).
- **검증 결과 — NNE vs strip-band**:

  | Layout | P1 | P2 | P6 | P7 | norm |
  |---|---:|---:|---:|---:|---:|
  | **NNE_golden** | **0.6986** | 0.9079 | None | **0.4366** | **0.7233** |
  | strip-band avg (4 시나리오) | 0.6484 | 0.9054 | None | 0.2676 | 0.6694 |
  | **Δ** | **+0.050** | +0.003 | — | **+0.169** | **+0.054** |

  - **P1 (+0.05)**: NNE 직선 흐름축 vs strip-band zigzag — 의도대로.
  - **P2 (≈0)**: 둘 다 같은 방 응집 만점에 가까움 → D_REF=20m 가 너무 관대,
    후속 보정 여지.
  - **P7 (+0.17)**: NNE 의 방 면적 ↔ 장비 면적 균형이 strip-band 보다 명확
    우위 (outer_fill 가 sweet 0.5 근처).
- **결과**: **P-series 가 전문가 배치를 strip-band 보다 +5.4%p 높게 평가**.
  점수 수식 타당성 확인. CP-SAT 가기 전 안전판 확보.
- **별도 주의**: NNE spec 의 hard_violations = 16건 (airlock 부재 등 우리
  fixture 단순화 영향, NNE 실제 도면 위반 아님). geo_total = -694. P-series
  비교가 본 검증 목적이라 별도 차원으로 두고 진행. 후속 옵션.
- 테스트 7건 신규 (80 passed, 1 skipped). 회귀 0건.
- decisions.md D-014 작성.

### 2026-05-30 — Phase C0 (D-015 CP-SAT 골격 검증) [완료]

- **진단 보고 (이전 턴, 사용자 요청)**: 현재 strip-band 4 한계 (점수 분리,
  하드코딩 결정 변수, 도메인 제약 미표현, infeasibility 무시) 정리. 결론
  채택: **층1 (방 배치) 부터 CP-SAT, 층2 (장비) 는 strip-band `_place_equipment_grid`
  당분간 재사용** (P2 group_term 포화로 leverage 작음).
- **C0 = 최소 골격 검증 only**. 점수 연동·전체 방·adjacency/zone·장비 좌표
  모두 C1 이후.
- **구현**:
  - `requirements.txt` — `ortools==9.10.4067` 핀.
  - `src/drawing_agent/constraint_compiler.py` 신규 — `compile_minimal()`.
    변수: 방 (x_var, y_var) 격자 셀 + IntervalVar. 제약: 캔버스 도메인 +
    AddNoOverlap2D. 목적: 좌상단 모으기 (임시).
  - `src/drawing_agent/cpsat_solver.py` 신규 — `solve_minimal()` →
    (Layout, SolveReport). `num_search_workers=1` 결정론.
  - 기존 `layout_solver.solve()` (strip-band) **수정 0줄**, fallback 보존.
- **검증 (mab_8000L, 3 rooms: MEDIA/BUFFER/INOC)**:

  | 항목 | 값 |
  |---|---|
  | status | OPTIMAL (code 4), objective 46.0 |
  | CP-SAT 풀이 시간 | **20.12 ms** (방 3개) |
  | 안 겹침 / 캔버스 안 | PASS / PASS |
  | Layout 자료구조 재사용 | `Layout`/`PlacedRoom`/`Rect` 타입 그대로 |
  | renderer.render() 재사용 | 수정 0줄, SVG 23,819 bytes |
  | 결정론 | 두 번 풀이 좌표 동일 |
  | SVG 산출물 | `output/floorplan_c0_cpsat_3room.svg` |

- 테스트 8건 신규 (`tests/test_cpsat_c0.py`). 88 passed, 1 skipped.
  회귀 0건 (strip-band, P-series, NNE golden 전부 그대로).
- decisions.md D-015 작성.

### 2026-05-30 — Phase C1a (D-016 전체 방 + hard 제약) [완료]

- **C1a 목적**: 28 방 전부 hard 제약 안에서 feasible + 풀이 시간 감당.
  점수 목적함수는 C1b.
- **Hard 제약 4개**: H1 캔버스 안, H2 안 겹침 (AddNoOverlap2D), H3 zone 영역
  분리 (aux 좌/proc 중간/nc 우), H4 adjacency 인접 (좌상단 맨해튼 ≤ 25m).
- **첫 시도 INFEASIBLE → 진단 + 격리**:
  - 단계 완화 (zones/adj on-off) 로 **zone 만 켜도 INFEASIBLE** 확인.
  - 근본 원인: `ROOM_AREA_TO_SIDE_FACTOR=1.4` 로 방 면적이 1.96× 부풀음 →
    aux stripe (15.5m × 42.5m) 안에 12방 못 들어감.
  - **factor 1.4 → 1.0 정직화** (방 한 변 = √area, aspect [0.7, 1.4] 로 자연
    변동). 즉시 zones+adj hard 모두 FEASIBLE 500ms.
- **결정론 강화**: random_seed=0 + num_search_workers=1 만으로는 wall-clock
  time_limit 도달 시 머신 부하에 따라 좌표 다름 (테스트 실패). 해결:
  `max_deterministic_time = time_limit × 4.0` 추가 (ortools 권장 패턴).
- **검증 (mab_8000L 28방, zones+adj hard, 5s)**:
  - status FEASIBLE, **첫 feasible 500ms**, 5s 종료 시 obj=1650
  - 28방 모두 좌표, 안 겹침 0, 캔버스 밖 0, adjacency 6 pair 모두 25m 안
  - renderer 재사용 0 줄 → SVG 68KB (`output/floorplan_c1a_28room.svg`)
  - 결정론 통과 (두 번 풀이 좌표 동일)
- 테스트 10건 신규 (`tests/test_cpsat_c1a.py`). **98 passed**, 1 skipped, 0 fail.
- decisions.md D-016 작성.

### 2026-05-30 — Phase C1b (D-017 P-series surrogate + 첫 before→after) [완료]

- **목적함수 surrogate**: P1 (PPO 인접 쌍 흐름축 단조 페널티) + P2 (adjacency
  hard 변수 거리 합 minimize) + tie-breaker (좌상단). `compile_c1a` 의
  objective 를 분리 가능하게 `add_compactness_objective: bool=True` 플래그 추가.
- **4 시나리오 측정 (P1-only weight: p1=500, p2=0, tie=0, 10s)**:

  | Scenario | strip-band | CP-SAT C1b | Δ |
  |---|---:|---:|---:|
  | A_small_aseptic | 0.6687 | **0.7122** | **+0.0435** |
  | mab_8000L | 0.6615 | 0.6527 | −0.0088 |
  | C_closed_sys | 0.6965 | 0.6405 | −0.0560 |
  | B_large_multi | 0.6511 | **0.6658** | **+0.0147** |
  | **avg** | **0.6694** | **0.6678** | **−0.0017** |
  | NNE_golden (ref) | — | 0.7233 | — |

  - 모두 OPTIMAL 도달 (700ms ~ 2.6s, 10s timeout 안에)
  - 2/4 향상 (A, B), 2/4 저조 (mab, C). 평균 거의 동등.
- **디폴트 (P1=100, P2=60, tie=1) 는 더 저조 (−0.033 평균)**: P2 surrogate 가
  P1 과 충돌 + tie-breaker 가 PPO 단조 방해 → timeout 도달. **P1-only 권장**.
- **핵심 진단** (논문 자료):
  1. **factor 정책 차이**: CP-SAT (방 한 변 √area × aspect [0.7,1.4]) vs
     strip-band (area_m2 stripe 비례). 방 사이즈 비교 시 주의.
  2. **adjacency 35건 (room↔airlock) 모델 밖**: 전실 미편입 → P2 link 거리에
     PAL/MAL 통과 무시. **C2 에서 결정**.
  3. **P1 surrogate ≠ 실제 P1 점수**: surrogate=방 단위, 실제=장비 흐름축
     투영. 같은 방 안 row-major pack 으로 sort_order row 간 역행 → 진짜 P1
     향상은 **C3 (장비 CP-SAT)** 가 가야 가능.
  4. **NNE 까지 격차 (Δ +0.054)**: P7 (방-장비 면적 균형) 가 핵심. NNE 의
     0.44 도달은 B-001 (시각 축소 분리) + C3 가 필요.
- 테스트 8건 신규 (`tests/test_cpsat_c1b.py`). 회귀 0 (98 → **106 passed**).
- SVG: `output/floorplan_c1b_mab_8000L.svg`.
- decisions.md D-017 작성.

### 2026-05-30 — Phase C3a (D-018 장비 CP-SAT 착수 + B-001 시각 축소 분리) [완료]

- **D-015 부분 재검토**: C1b 실측에서 진짜 P1·P7 leverage 가 *장비* 단위
  임을 확인 → 층2 CP-SAT 필수. D-015 결정의 P2 포화 근거는 유효, 다만 P1·P7
  과소평가가 문제.
- **C3a 구현** (방 1개 + 장비 N개 CP-SAT):
  - `compile_room_c3a(room, room_rect_mm, ...)` — 장비 (x_var, y_var) 격자.
    hard: 방 안 + 안 겹침 (AddNoOverlap2D + gap padding). 목적: P1 surrogate
    (sort_order 인접 쌍 가로 단조) + P7 surrogate (장비 외접 bbox perimeter
    `(x_max-x_min)+(y_max-y_min)` 최소화).
  - `solve_room_c3a(...) → (list[PlacedEquipment], SolveReport)`. INFEASIBLE
    이면 빈 list.
- **B-001 부분 처리**: `_place_equipment_grid(use_actual_mm: bool=False)`
  플래그 추가. default 변경 X (baselines/B3 안 흔듦), True 면 실제 W_mm 사용.
- **검증 — R_MEDIA_PREP 5장비 (10×10m=100m² 방)**:

  | Mode | inner | outer_fill | **P7_room** | P1_local |
  |---|---:|---:|---:|---:|
  | A row-major 시각축소 (0.8x) | 0.206 | 0.118 | **0.126** | 1.000 (왜곡) |
  | B row-major 실제 W_mm | 0.570 | 0.684 | **0.556** | 0.500 |
  | **C CP-SAT 실제** | **0.765** | **0.510** | **0.870** | **0.750** |

  - CP-SAT vs row-major 실제: **P7 +0.314, P1 +0.250**.
  - CP-SAT outer_fill = 0.510 — sweet 0.50 거의 정확. ✓
  - **풀이 시간**: 226ms (OPTIMAL, 5장비).
  - strip-band rect (54m²) 에선 INFEASIBLE — **C3 사용 시 방 rect 가 spec
    area 근처여야 함** (C1 의 CP-SAT 방 rect 와 결합 필요).
- 테스트 8건 신규 (`tests/test_cpsat_c3a.py`). **114 passed**, 1 skipped, 0 fail.
- decisions.md D-018 작성.

### 2026-05-30 — Phase C3b (D-019 모든 방 sweep + 정제실1 진단) [완료]

- **scripts/c3b_room_map.py 신규** — mab_8000L 의 *장비 있는 모든 방* (13방)
  에 C3a 적용 + row-major(실제 W_mm) 대비 측정. 방 rect = spec area_m2 정사각.
  결과 `output/c3b_room_map.json` 저장.
- **결과 — 13/13 모두 feasible (INFEASIBLE 0건)**:

  | Room | n | density | RM P7 | CP P7 | ΔP7 | CP status | ms |
  |---|---:|---:|---:|---:|---:|---|---:|
  | R_CIP_SUPPLY ~ R_DS_STORAGE | 1~4 | <0.20 | … | … | ≈0 | OPT | <50 |
  | R_INOCULATION | 4 | 0.279 | 0.511 | 0.757 | **+0.245** | OPT | 26 |
  | R_HARVEST | 4 | 0.340 | 0.829 | 0.801 | −0.028 | OPT | 12 |
  | R_BUFFER_PREP | 5 | 0.219 | 0.633 | 0.615 | −0.018 | FEA | 5003 |
  | R_MEDIA_PREP | 5 | 0.390 | 0.556 | **0.870** | **+0.314** | OPT | 223 |
  | R_CELL_CULTURE | 6 | 0.122 | 0.429 | 0.438 | +0.009 | FEA | 5003 |
  | R_PURIFICATION_2 | 6 | 0.270 | 0.500 | **0.722** | **+0.222** | OPT | 4421 |
  | **R_PURIFICATION_1** | **23** | **0.390** | **0.259** | **0.777** | **+0.518** | **FEA** | **5003** |

  - **평균 P7: RM 0.505 → CP 0.605 (+10%p)**, P1 평균: RM 0.696 → CP 0.911 (+21.5%p).
  - density 큰 방에서 CP-SAT 효과 큼. 정제실1 (+0.52) 이 최대.
- **R_PURIFICATION_1 강조 (사용자 1순위 위험)**:
  - FEASIBLE 5s timeout, **P7 +0.518 (가장 큰 향상)**, P1 거의 동일.
  - **fallback 전략 불필요** — 정제실1 도 풀린다.
- 테스트 4건 신규. **118 passed**, 1 skipped, 0 fail.
- decisions.md D-019 작성.

### 2026-05-30 — Phase C1+C3 통합 (D-020 첫 진짜 before→after) [완료]

- **scripts/c1c3_pipeline.py 신규** — C1b(방) → C3a(장비) → P-series 측정.
- **3단계 진단·해결**:
  1. default aspect [0.7,1.4] → INFEASIBLE 23/52 (44%). C1b 가 방을 작게 풀음.
  2. aspect 좁힘 [0.9,1.1] → mab +0.06 그러나 A_small INFEASIBLE.
  3. **동적 aspect** (canvas vs spec area 비교, threshold=1.0) → 채택.
- **solve_c1b 에 aspect_min/max 인자 추가**. C3 시간 배분 단축 (≤4=1s,
  5-10=3s, 11+=8s). 95s → 66s.
- **최종 결과**:

  | Scenario | strip-band | CP-SAT C1+C3 | Δ | time | fallback |
  |---|---:|---:|---:|---:|---:|
  | A_small | 0.6687 | 0.6740 | +0.0053 | 4.0s | 6/13 |
  | **mab_8000L** | 0.6615 | **0.7230** | **+0.0615** | 20.3s | 1/13 |
  | **C_closed** | 0.6965 | **0.7050** | **+0.0085** | 25.1s | 1/13 |
  | B_large | 0.6511 | 0.6534 | +0.0023 | 16.7s | 0/13 |
  | **avg** | **0.6694** | **0.6888** | **+0.0194** | **66.1s** | 8/52 |
  | NNE | — | 0.7233 | — | — | — |

  - **mab_8000L = NNE 거의 도달** (0.7230 vs 0.7233).
  - **mab P7: 0.2483 → 0.6756 (+0.43!!)** — C3 효과의 핵심.
  - **R_PURIFICATION_1 FEASIBLE 8s, fallback 안 함**. 사용자 1순위 위험 통과.
- 테스트 4건 신규. **122 passed**, 1 skipped, 0 fail.
- decisions.md D-020 작성.

**한계 명시**:
- A_small / B_large 작은 향상 — URS 의 캔버스/area 부정합. URS 3.6 (별도 트랙) 후.
- P2 감소 (~−0.09) — C3 가 P7 우선해서 group 응집 약화. C2 (전실) 또는
  P2 surrogate C3 박기 후.

### 다음 — Phase C2 / B-001 default 변경 / URS 3.6 결합 대기

**다음 세션 첫 액션 (cold start guide)**:
1. PROGRESS / decisions 읽고 D-020 완료 확인. mab 0.7230 (NNE 거의 도달),
   avg +0.0194.
2. **사용자 결정 받을 사항**:
   - C2 (전실 편입) — P2 감소 보완. mab P2 0.9046 → 0.8152.
   - C3 에 P2 surrogate 박기 — group 응집 회복.
   - **B-001 default 변경 (`use_actual_mm=True`)** — baselines.json 재생성.
     통합 결과 안정됐으므로 적절한 타이밍.
   - URS 3.6 (팀원 별도) 후 4 시나리오 재측정.
3. **C4 fallback** 명시화: 통합 안 풀리는 방은 row-major 실제 자동 (이미 작동).

**별도 트랙 (사용자 / 팀원)**:
- URS 3.6 Critical Process Equipment List → rule_engine 연결.
- 해소되면 baselines.json + C1+C3 통합 재측정.

**다음에 보강할 수식 / 데이터**:
- P1 흐름축 polyline 평균 방향 (PPO 가 U-shape 일 때).
- P2 D_REF=20m 보정 + cross-room link 의 spec.adjacency 도어 거리.
- P6 본 수식 (clearance_m 채워질 때).
- P7 sweet=0.50 보정.
- 장비 회전 (직사각 rect 좁은 방에서 필요할 수 있음).

---

## 백로그 / TODO (지금 안 함, 트리거 조건 명시)

> 작업 도중 발견된 정리 / 개선 거리. 트리거 조건이 오기 전엔 baseline 흔들지
> 않게 그대로 둠.

### B-001: 시각 축소 (EQUIPMENT_VISUAL_SCALE=0.80) 와 점수 분리

- **현상**: `layout_solver.py:360` `EQUIPMENT_VISUAL_SCALE = 0.80` (+ 자동
  축소 0.9× 반복 ~ 0.25 하한) 이 `_place_equipment_grid` 안에서 적용 →
  `PlacedEquipment.rect` 가 시각 축소된 크기로 박힘. P7 inner_compactness =
  Σ(eq.rect 면적) / 외접 bbox 가 *축소된* 면적을 쓰므로 약간 왜곡.
- **정리 방향**: "시각 축소는 renderer 단계로 분리하거나 0.8× 규칙 자체를
  없애는 쪽으로 추후 결정. **점수·CP-SAT 는 실제 W_mm / D_mm 사용**." Layout
  단계의 `PlacedEquipment.rect` 는 실제 치수, renderer 가 그릴 때만 시각 축소.
- **트리거**: (a) Phase C3 — 층2 (방 안 장비) 를 CP-SAT 화할 때 (실제 W_mm
  으로 풀어야 정합), 또는 (b) P7 정밀화가 필요해질 때 (D_REF·sweet 보정과
  병합 가능).
- **지금 안 하는 이유**: baselines.json (B2) 과 NNE golden (B3) 비교가 모두
  현재 시각 축소된 좌표 위에 측정됨. 분리하면 두 baseline 다시 측정 필요 →
  C1 흐름 흔듦. C3 / P7 정밀화 시점에 한꺼번에 처리.
- **변경 시 영향 범위**: `layout_solver.py:360-362` 상수 + `_place_equipment_grid`
  scale 적용부, `renderer.py` 의 장비 그리기 단계, `scripts/baselines.py` 및
  `scripts/golden_nne.py` 재실행, `test_reward.py` / `test_golden_nne.py` 일부
  수치 기대값 (회귀 검증 후 재고정).
