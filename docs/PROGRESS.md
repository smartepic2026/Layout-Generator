# PROGRESS — 작업 진행 상황

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

### 다음 — Phase B1 진입 대기
- B1: P-series 수식 (P1·P2·P6·P7)
- 사용자 검토 → OK 받으면 시작
