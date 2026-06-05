# Rule Engine → Drawing Agent 정렬 감사 (Alignment Audit)

> **목적 (CLAUDE.md 최우선 원칙 + 사용자 #2)**: multi-agent 파이프라인에서
> Rule Engine / Validation Agent 의 출력이 **누락·왜곡 없이** drawing 에
> 표현되는지 필드 단위로 추적한다. 이 문서는 Phase 0 산출물이며, 후속
> Phase 1~3 의 작업 명세이자 논문 method(정렬 검증)·특허(계약 경계 추적)
> 원재료다.
>
> **기준 입력**: 새 15-룰 엔진 실제 출력 `output/teammate_engine_v2_output.json`
> (teammate/main `e05b85c`, 48 rooms / 18 airlocks / 27 adjacency / 399 rationale).
> **작성일**: 2026-06-06. **앵커 결정**: decisions.md **D-022**.

---

## 0. 통합 벤치테스트 결과 (사용자 #1)

| 경로 | 결과 |
|---|---|
| raw 엔진 출력 → `cli draw` 직접 | ❌ **크래시** (Pydantic: `rationale.*.target`/`reason` 필수). raw 는 `target_id`/`decision` 필드. |
| raw → `adapt_external_dict` → 내부 spec → `cli draw` | ✅ **정상** (SVG 80KB, rooms placed 23, airlocks 18, doors 39). |

**결론**:
1. **계약 변경(6/2, 13→15룰)은 additive·non-breaking** — 어댑터를 거치면
   drawing 이 안 깨진다. `flow_paths` 5필드 구조 불변 확인.
2. **단, 통합 경로에 어댑터 단계가 필수**다. raw 엔진 출력은 `draw` 가 바로
   못 먹는다. → CLI/문서에 "rule-engine(어댑터 포함) → draw" 순서 명시 필요.
   (현재 `cli rule-engine` 은 어댑터를 거치지만 `cli draw` 는 *이미 어댑터를
   통과한* 내부 spec 만 받는다. cli.py:38 vs cli.py:54.)

---

## 1. 필드 단위 정렬 표

> consumed = layout/렌더에 실제 반영 · DROPPED = 내부에서 버려짐(silent).
> 인용 file:line 은 직접 검증한 것.

### rooms[]

| 엔진 필드 | 상태 | 위치 / 비고 |
|---|---|---|
| room_id, name_ko/en, category, clean_grade | ✅ consumed | 배치·라벨·등급색 |
| area_m2 | ✅ consumed | `_alloc_dim` 면적비례 분배 (layout_solver.py:342, 368) |
| **width_mm, depth_mm** | ⚠️ **DROPPED** | 솔버가 `√area_m2`+aspect 로 자체 산출. 엔진이 준 명시 치수 무시 |
| **area_ratio_pct** | ⚠️ **DROPPED** | 0 hits. URS 면적 비율(피드백 #5)이 렌더에 반영 안 됨 |
| **is_airlock / airlock_id** | ⚠️ **DROPPED** | 내부 Room 스키마에 필드 없음(schemas.py:29 extra=ignore). 새 계약 dedup 신호 미사용 |
| differential_pressure_Pa | ✅ consumed | 도어 swing fallback·차압 표기 |
| equipment[] | ✅ consumed | 장비 배치(C3) |
| process_no | ✅ consumed | tier3 sort_order |
| background_color, transparency_pct | ◻︎ 대체소비 | 엔진값 무시, **grade→KB색**(design_tokens, grade_colors_kb)으로 동등 산출 |
| **gowning_type, gowning_method** | ⚠️ **DROPPED** | 0 hits. 갱의 종류/방식 라벨·검증 없음 |
| **volume_m3, air_changes_per_hour, recovery_time_min** | ⚠️ DROPPED | HVAC 메타. 2D 도면엔 비필수이나 룸 주석으로 표기 가능 |
| **well_type_ceiling** | ⚠️ DROPPED | 우물형 천정 표기 없음 |
| room_flow (one/both-way) | ✅ consumed | one_way_flow |

### airlocks[]

| 엔진 필드 | 상태 | 위치 / 비고 |
|---|---|---|
| al_id, kind, clean_grade | ✅ consumed | 전실 배치·라벨 |
| connects_higher_room | ✅ consumed | 전실을 인접 방에 붙임 (layout_solver.py:615) |
| **area_m2** (신규 9/12) | ⚠️ DROPPED | 전실 크기를 면적 아닌 고정폭(상한 3.8m)으로. 새 KB footprint 미사용 |
| **flow_type** (cascade/sink/bubble) | ⚠️ DROPPED | 차압 방향 타입 표기 없음 |
| **connects_lower_room** | ⚠️ DROPPED | 한쪽(higher)만 사용 |
| **purpose** | ⚠️ DROPPED | |
| differential_pressure_Pa | ◻︎ 부분 | |

### adjacency[]

| 엔진 필드 | 상태 | 위치 / 비고 |
|---|---|---|
| from_id, to_id, relationship | ✅ consumed | 도어 생성 |
| door_count, door_size_mm | ✅ consumed | |
| **door_swing_target** | ✅ consumed | `adj.door_swing_to` 있으면 사용, 없으면 DP fallback (layout_solver.py:815-816). null 시 룰 미반영 → WARNING |
| **flow_direction** | ⚠️ **DROPPED** | 0 hits. 인접 방향성 미사용 |
| **is_elevator_constraint** | ⚠️ DROPPED | 엘리베이터(반입/반출구) 제약 미반영 — 피드백 #3(Waste↔Material 분리) 근거 |

### flow_paths{} ★ 최대 gap

| 엔진 필드 | 상태 | 위치 / 비고 |
|---|---|---|
| product_process_order | ✅ consumed | 방 정렬·sort_order (constraint_compiler.py:429, layout_solver.py:201) |
| **personnel_entry** | ⚠️ **DROPPED** | 동선 렌더가 미사용 |
| **personnel_exit** | ⚠️ **DROPPED** | 〃 |
| **material_entry** | ⚠️ **DROPPED** | 〃 |
| **waste_exit** | ⚠️ **DROPPED** | 〃 |

> **스모킹건**: 동선 화살표 렌더러 `_emit_z9_flow_arrows(s, ox, oy, layout)`
> (renderer.py:606) 는 **`spec` 를 인자로 받지도 않는다** → flow_paths 를
> 물리적으로 볼 수 없다. 대신 방 id 문자열 `"SUPPLY_CORRIDOR"` /
> `"RETURN_CORRIDOR"` 패턴매칭(renderer.py:634, 637)으로 동선을 **휴리스틱
> 재구성**한다. 즉 엔진이 명시한 4종 동선 시퀀스(Person 입/퇴, Material, Waste)는
> 도면에 반영되지 않는다. 새 GMP Flow 규정(Person/Material/Product/Waste)을
> drawing agent 에서 학습하기로 한 팀 결정의 정확한 작업 지점.

### zones{}, constraints{}

| 엔진 필드 | 상태 | 위치 / 비고 |
|---|---|---|
| **process_zone / auxiliary_zone / nc_zone** | ⚠️ **DROPPED** | 0 hits. 솔버가 category+ID 패턴으로 **재분류**(layout_solver.py:160~236). 엔진 zone 멤버십 무시 |
| **constraints.corridor_width_mm** | ⚠️ DROPPED | 복도폭 하드코딩(design_tokens) |
| **constraints.airlock_size_mm** | ⚠️ DROPPED | 전실 크기 하드코딩 |
| **constraints.equipment_clearance_mm** | ⚠️ DROPPED | P6(청소 이격) 데이터 부재와 연결 |
| **constraints.process_zone_area_ratio** | ◻︎ scorer만 | S1 점수에서 참조, 배치엔 미반영 |
| **constraints.supply_return_no_direct_connection** | ✅ consumed | H5 정수제약(특허자료①) |
| **constraints.color_legend** | ⚠️ DROPPED | 범례를 KB색으로 자체 생성 |

---

## 2. Top 정렬 GAP (우선순위)

| # | Gap | 심각도 | 위치 | 사용자 연결 |
|---|---|---|---|---|
| **G1** | 동선 화살표가 flow_paths 미사용(휴리스틱) | 🔴 CRITICAL | renderer.py:606-676 | 새 GMP Flow 규정·#2 정렬 |
| **G2** | width_mm/depth_mm·area_ratio_pct 무시 → 면적 비율 왜곡 | 🔴 CRITICAL | layout_solver.py:342-381 | 도면 피드백 #5 |
| **G3** | is_airlock/airlock_id 미소비 — dedup 이 ID패턴+area==0 휴리스틱에만 의존(취약) | 🟠 HIGH | layout_solver.py:153-155 | 새 계약 견고성 |
| **G4** | zones{} 무시, 재분류 | 🟠 HIGH | layout_solver.py:160-236 | 구역 일치성 |
| **G5** | is_elevator_constraint·flow_direction 미사용 | 🟠 HIGH | adjacency 처리부 | 피드백 #3(반입/반출 분리) |
| **G6** | constraints{}(복도폭/전실/이격) 하드코딩 | 🟡 MED | design_tokens | 피드백 #4 |
| **G7** | gowning_type/method, airlock flow_type/area, well_type 등 메타 라벨 미표기 | 🟡 MED | (드롭) | 도면 정보량 |

---

## 3. 개선 계획 매핑

- **Phase 1** → G1: `_emit_z9_flow_arrows` 가 `spec`(flow_paths) 를 받아 4종
  동선(Person 입/퇴·Material·Waste·Product)을 실제 방 좌표로 연결. Product 는
  벽 가로지르기, 나머지는 복도 경유, 외부 legend. (decisions D-023 예정)
- **Phase 2** → G2(면적 비례 렌더 + width/depth 존중), G3(is_airlock 명시
  소비), G6(constraints 일부 소비).
- **Phase 3** → G4·G5·G7 + 도면 피드백 5건.

---

## 4. 논문/특허 메모

- 이 감사 자체가 "**계약 경계 정렬 검증(contract-alignment verification)**"
  으로 method 의 한 절. 어댑터(anti-corruption layer, D-003) + 출처추적(D-001)
  위에 "필드별 소비 추적표"를 두면 *어느 출력이 도면에 반영되는지* 가
  재현가능하게 추적된다.
- **epistemic honesty 일관**: DROPPED 필드를 은폐하지 않고 명시 → P3·P5·P8
  보류 정책과 같은 줄기. 향후 채워지면 표가 ✅ 로 이행하는 추적성.

---

## 5. 진행 현황 (gap 해소 추적)

| Gap | 상태 | 처리 |
|---|---|---|
| **G1** 동선 화살표 flow_paths 미사용 | ✅ **해소** (Phase 1, D-023) | `_emit_z9_flow_arrows` 가 spec.flow_paths 4종 렌더 |
| **(신규) 실제 방 누락** (MEDIA/BUFFER 등 7개) | ✅ **해소** (Phase 1, D-023) | cli draw 기본 gradient(누락 0)+`--strip`+WARN |
| **G2** 면적 비율 왜곡 (#5) | 🟡 **부분 해소** (Phase 2, D-024) | NC/D 컬럼 squarified treemap(✅) / 공정행은 단일행 토폴로지 trade-off(잔여) |
| **G3** is_airlock dedup 취약 | ✅ **해소** (Phase 2, D-024) | 내부 스키마에 is_airlock/airlock_id 추가 + dedup 1차 신호 |
| **G4** zones{} 무시 | ⬜ 대기 (Phase 3) | |
| **G5** is_elevator_constraint/flow_direction | ⬜ 대기 (Phase 3, 피드백 #3) | |
| **G6** constraints{} 하드코딩 | ⬜ 대기 (Phase 3) | |
| **G7** gowning/airlock flow_type 메타 | ⬜ 대기 | |
