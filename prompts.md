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
