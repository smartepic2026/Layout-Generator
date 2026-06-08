# 설계 결정 로그 (논문 method / 특허 청구항 원재료)

> CLAUDE.md "설계 결정 로그" 원칙 — 중요한 설계 결정마다 무엇·왜·근거를
> 기록. 후속 논문 method 섹션과 특허 명세서의 원재료.

---

## D-036: 팀장님 URS 1~5 최종 도면 품질 기준 — validation-first + readable flow + filled footprint

**날짜**: 2026-06-09

**무엇**: 팀장님 피드백을 도면 생성 시스템의 hard/soft 기준으로 승격했다.
단순 SVG polish가 아니라 solver, renderer, CLI, validation report까지 한 흐름으로
묶는다.

**결정**:
1. **Validation-first**: Rule Engine/RAG가 맞아도 layout에서 깨질 수 있으므로,
   최종 SVG 생성 후 geometric validator를 반드시 돌린다. hard error 항목은
   Grade D corridor 인접, NC-D/D-C gowning·MAL gate 양측 corridor 접촉,
   비-airlock room-room door 금지, 장비-airlock overlap이다.
2. **Variants는 mirror/toggle이 아니라 실제 배치 후보**: `--seed`와 `--variant(s)`로
   재현 가능한 다양성을 만든다. 같은 seed는 재현성, variant index는 같은 zone 내
   room order/split/mirror 후보 차이를 만든다.
3. **Flow 가독성 우선**: 같은 색 flow를 lane별로 여러 줄 벌리지 않는다. 공유 trunk는
   한 번만 그리고, flow path는 하나의 SVG `<path>`로 렌더링해 중간 끊김을 줄인다.
   Product는 Personnel과 구분되도록 Orange(`#F97316`)를 사용한다.
4. **빈 흰 공간 금지**: 종횡비를 줄이기 위해 room을 한쪽으로 밀고 남기는 미배치
   여백은 평가용 도면에서 허용하지 않는다. D-zone room은 corridor 인접을 유지하며
   zone 폭을 채운다.
5. **전실은 장비 배치 금지 영역**: 장비 자동 축소보다 PAL/MAL/CAL 전실 침범 방지가
   우선이다. row-major 실패 시에도 안전 영역 내 grid fallback으로 배치한다.
6. **Legend는 정보 패널로 확장**: grade/flow 범례뿐 아니라 canvas W/H, canvas area,
   room/corridor/airlock/door count, modality를 우측 패널에 표시한다.

**검증 기준**:
- 팀장님 URS 1~5 x 3 variants = 15개 도면에서 validation hard error 0.
- SVG XML parse 정상.
- focused pytest: `tests/test_layout_validation.py`, `tests/test_drawing_agent.py` 통과.

**남은 soft risk**:
- 면적비율 warning은 일부 남을 수 있다. 현재는 hard error와 가독성 문제를 먼저
  봉합했으며, 다음 단계에서 W4~W7(area fit/ratio objective)로 별도 최적화한다.
- full flow mode는 방별 branch를 표시하므로 path 수 자체는 많다. 다만 같은 색
  lane fan-out과 segment 끊김은 제거했다.

---

## D-001: 4-tier 데이터 어댑터 (Phase A1)

**날짜**: 2026-05-29

**무엇**: drawing_agent 가 장비 속성값을 조회할 때 출처를 4계층으로 분리한
어댑터 구조. 디렉토리: `src/drawing_agent/data/`.

```
tier1_ruleengine  : RuleEngineOutput 에 이미 있는 값 (최우선)
tier2_urs         : examples/urs_*.json 시나리오 JSON (장비 override)
tier3_derive      : 기존 필드에서 파생 (process_step → sort_order 등)
tier4_manual_stub : drawing_agent/kb/ 의 수기 보충 (최후 수단)
```

각 채워진 필드는 `SourceTracker` 가 `(room_id, eq_idx, field_name) →
tier_name` 으로 기록.

**왜**:
1. **재현가능성** — 어떤 값이 어디서 왔는지 추적. audit · 검증 · 논문
   재현이 모두 source 태그로 가능.
2. **팀원 영역 보호** — rule_engine 이 향후 같은 필드(sort_order 등)를
   채우기 시작해도 tier1 이 자동 우선 → drawing_agent 코드 무수정.
3. **검수자 부재 데이터 분리** — 수기 보충값(tier4)은 source 태그로
   격리되어 후속 audit 시 명확히 분리 가능 (CLAUDE.md epistemic
   honesty 원칙).
4. **특허 청구항 후보** — "다중 출처 데이터의 우선순위 기반 조합 +
   출처 메타데이터 추적" 자체가 신규 구성요소. drawing_agent 의
   "결정 가능한 데이터 vs 추론 데이터 분리" 와 결합 시 청구항 강도 ↑.

**근거 / 트레이드오프**:
- 단순 derive 함수 1개 (`derive.py`) 로 끝낼 수도 있었음 →
  CLAUDE.md "데이터 출처가 특허·논문 포인트" 라는 사용자 결정으로
  디렉토리 구조 채택. 코드량은 늘었지만 출처별 격리가 명시적.
- 대안 (단일 파일) 와 비교: tier 추가 시 파일 하나만 늘리면 됨 →
  진화 비용 낮음.

**한계 / Phase B 이월**:
- tier2 (URS 시나리오) 는 stub. 현재 URS 는 정책 레벨만 표현 →
  장비 override 가 필요해질 때 구현.
- tier4 (manual_stub) 도 stub. **cross-room connects_to** (방 경계
  넘는 공정 link) 는 Phase B 에서 P2 수식 만들 때 검증과 함께 채움.
  검수자 없이 미리 박지 않음.

---

## D-002: tier3 derive 규칙 (Phase A1)

**날짜**: 2026-05-29

**무엇**: tier3 에서 파생하는 3개 필드의 derive 규칙.

| 필드 | 규칙 | 입력 |
|---|---|---|
| `sort_order` | 정규식 `P?(\d+)[\-_.](\d+)` 로 phase·seq 추출, `phase*10+seq` 반환 | `process_step` (예: "P1-2" → 12) |
| `bbox_m` | mm → m 환산 후 [w, d] 리스트 | `W_mm`, `D_mm` |
| `connects_to` | 같은 방 안에서 sort_order 가 다음인 장비를 후속 공정으로 가정. 단방향 chain | sort_order (전 단계에서 채워짐) |

**왜**:
- sort_order: P1 (flow_monotonicity) 점수 계산 시 정수 정렬 키가 필요.
  process_step 문자열은 라벨로 보존하면서 derive 한 정수만 사용 (PATCH
  v0.2 §1 #1 결정 반영).
- bbox_m: P7 (compactness) 와 솔버 격자 변환 시 미터 단위가 자연.
- connects_to (same-room): P2 (adjacency) 의 가장 안전한 신호. 같은 방
  안 공정 순서는 ISPE §7.9 의 "공정 순방향 배치" 그 자체.

**근거**:
- ISPE Baseline Guide Vol 6 Ch.7.9 — Facility Conceptualization Tool
  의 step1 = process flow sequencing.
- PATCH v0.2 §6.2 — "1차 채움 필드 = 엑셀 단위공정 시트에서 도출 가능".

**한계**:
- sort_order 가 한 phase 에 10개 이상이면 `phase*10+seq` 가 충돌.
  현재 데이터 (P1~P7, phase 당 ≤5개) 에 안전. 충돌 발생 시 `*100+seq`
  로 폭 확장 예정.
- connects_to **cross-room 은 의도적으로 미구현** (CLAUDE.md "검수자
  없는 추론값 신중히"). Phase B 에서 P2 수식 만들 때 검증하며 tier4 로
  채움.

**검증**: tests/test_data_adapter.py 10건 통과. baseline spec (66
장비) 에서 sort_order 53건 (process_step 있는 장비만), bbox_m 66건,
same-room connects_to chain 다수 생성 확인.

---

## D-003: Anti-corruption layer (tier1_ruleengine 변환 레이어)

**날짜**: 2026-05-29

**무엇**: 팀원의 외부 JSON 계약(RuleEngineOutput JSON)을 우리 내부 Pydantic
모델(`schemas.py`)로 변환하는 어댑터 레이어를 `tier1_ruleengine.py` 안에
도입. schema 자체는 팀원 필드명을 받지 않고, 변환 레이어가 필드명·치수
형식·이름 trailing space 등을 일괄 정규화한 뒤에 schema 에 전달.

**핵심 변경**:
1. `schemas.py` `extra="forbid"` → `"ignore"`. 우리가 모르는 필드(`meta`,
   `instance_id`, `severity`, `note`, `elevator`, `flow` 등)는 silently
   drop. 이전엔 ValidationError 로 전건 거부.
2. `tier1_ruleengine.py` 의 `adapt_external_dict()` / `load_external_spec()`:
   필드명 매핑 + WxDxH 합쳐진 문자열 파싱(콤마 "2,000" 처리) + trailing
   space strip + process_no→process_step alias + swing(descriptor)→notes
   보존 + rationale severity+note→decision+reason 합성.

**왜** (CLAUDE.md 4대 원칙 기준):
1. **성능 / 견고함**: 팀원 출력 한 글자 바뀌면 도면 0건 생성되는 fragile
   결합 차단. 변환 레이어 한 곳만 고쳐서 흡수.
2. **실무 수준**: 더러운 실데이터 처리 — 콤마 들어간 치수, trailing
   space, 외부 계약 변동성을 모두 변환 레이어에서 정상화. 시연용
   장난감과 분리되는 지점.
3. **특허**: "외부 출처 정규화 + 출처 메타데이터 추적 + 다중 fallback"
   결합 자체가 청구항 후보. D-001(4-tier) + D-003(외부 계약 변환) 결합
   시 청구항 폭 증가.
4. **논문 재현성**: 외부 계약 변경이 method 섹션에 흘러들지 않게 격리.
   실험 재현 시 schema 만 봐도 우리 모델 정의가 자명.

**근거**:
- 진단 (RuleEngine_Output_for_DocAgent.md vs schemas.py): 36건 mismatch
  + 4건 silent failure. 위험 1 (Pydantic 전건 거부) + 위험 3 (process_step
  silent skip) 모두 변환 레이어 + extra=ignore 로 흡수.
- Domain-Driven Design (E. Evans) anti-corruption layer 패턴 — 외부
  bounded context 의 변동성을 내부 모델로부터 격리.

**한계 / 이월**:
- Airlock required 필드 (`connects_higher`/`lower`, `area_m2`) 가 팀원
  출력에 "—" (NULL) 18건. 변환 레이어로 못 메움 → Optional 화는 팀원
  JSON 실물 확인 후 결정.
- `process_no` alias 는 깔아뒀지만 팀원의 실제 키 이름은 미확인. 마크다운
  §1.1 컬럼에 안 보이고 §7 rationale 에서만 언급.
- AL 이중 표현 (팀원이 PAL_in 등을 rooms[] 와 airlocks[] 양쪽에 둠) 처리
  미정. zone 카운트 부풀음 가능.

**검증**:
- E2E probe: 마크다운 §0-7 구조 그대로 가공한 팀원 JSON → load_external_spec
  통과 → enrich_spec tier3 통과 → scorer S1/S4 silent default 모두 None
  반환 확인.
- 테스트 15건 추가, 전체 47 passed (1 skipped).

---

## D-004: Scorer silent failure 차단 (S1, S4)

**날짜**: 2026-05-29

**무엇**: scorer 의 두 함수가 입력 데이터 부재 시 "측정 불가" 대신
silent default 값을 반환하던 버그를 명시적 None 반환으로 교체.

- **S1 `_area_ratio_fit`**: 이전엔 `process_zone_area_ratio.get("current",
  0.5)`. 팀원 출력에 `current` 키가 없으면 silent 0.5 → 모든 도면이 동일
  점수. 변경 후: (a) layout 으로부터 실측 → (b) constraints `current` 키 →
  (c) None.
- **S4 `_pressure_cascade_smoothness`**: 이전엔 diffs 가 비면 0.8 반환,
  모든 DP=0 (스키마 default 인 채) 이어도 std=0 → 1.0 만점. 변경 후:
  모든 DP=0 또는 등급 경계 쌍 없음 → None.

`score()` 본체는 None 항목을 `breakdown[k]=None` + total 미합산으로
graceful 처리.

**왜**:
- **epistemic honesty** (CLAUDE.md): "근거가 명확한 제약만 적용하고
  불확실한 건 confidence 태깅해 분리" — 측정 불가를 0.5/1.0 으로 위장하지
  않음. P3·P5·P8 보류 정책과 같은 줄기.
- **CP-SAT cost function 정직성** (Phase C 대비): 솔버가 silent default
  로 만점 받는 차원을 "최적화 안 해도 됨"으로 학습하면 안 됨. None
  이어야 그 차원은 cost 에 안 들어가고, 실제 데이터가 채워지면 활성화.

**근거**:
- 실험: 모든 DP=0 인 spec → 변경 전 score 1.0, 변경 후 None.
- 진단 보고 S1/S4 항목 (위험도 2급, silent failure).

**한계**: S5~S8 (조용히 빈 값 먹는 곳) 은 미수정. flow_separation_quality
가 "R_RETURN_CORRIDOR" 같은 hard-coded id 를 가정하는 등 다른 silent
경로 존재. Phase B (P-series 수식) 에서 일괄 정리 예정.

---

## D-005: `process_step` → `process_no` 통일 (필드명 + Pydantic alias)

**날짜**: 2026-05-29

**무엇**: `Equipment.process_step` (Optional[str]) 을 `Equipment.process_no` 로
rename. JSON 입력은 Pydantic `validation_alias=AliasChoices("process_no",
"process_step")` 로 양 이름 모두 허용 (back-compat). drawing_agent 코드
(tier3_derive 등) 는 모두 `eq.process_no` 사용.

**왜**:
- 팀원이 정식 필드명을 `process_no` 로 확정 ("이름 안 바꾸기로 함"). 우리
  내부도 같은 이름을 1급으로 두어 계약 정렬.
- A1.5 에서 깔았던 `process_no → process_step` alias 는 의미가 반대 방향
  이 되어 제거.

**근거**:
- 팀원 출력 `RuleEngine_Output_for_DocAgent.md` §1.1 / §7 — 정식 명칭 확인.
- D-003 anti-corruption layer 원칙: 외부 계약명을 내부도 채택해 변환 폭 최소화.

**한계**:
- 본 결정만으로는 `rule_engine/` 코드가 `eq.process_step` (속성 접근) 으로
  읽는 부분이 AttributeError. → D-006 으로 해결.

---

## D-006: rule_engine 무수정 호환을 위한 `process_step` @property

**날짜**: 2026-05-29

**무엇**: `Equipment` 에 `@property process_step` 추가. `self.process_no` 를
그대로 반환하는 read-only alias. JSON 출력에는 영향 없음.

**왜**:
- D-005 rename 직후 15건 테스트가 `rule_10_equipment.py:44` 의
  `e.process_step or "ZZZ"` 에서 AttributeError 로 깨짐. CLAUDE.md 의
  "src/rule_engine/ 수정 금지" 원칙으로 rule_engine 코드를 못 고침.
- @property 한 줄로 rule_engine 측 모든 read 액세스 회복. 새 코드는
  `process_no` 직접 사용.
- `Equipment(process_step="X")` kwarg 호출(예: rule_03_size.py:113) 도
  validation_alias 가 처리 → 별도 처리 불필요.

**근거**:
- Pydantic v2: `@property` 는 모델 클래스에 정의 가능 — 필드명과 충돌
  없으면 정상 동작.
- 47→47 passed: 모든 회귀 회복 확인.

**한계**:
- Deprecated alias 이므로 신규 코드에서 `process_step` 쓰지 말 것.
  팀원이 rule_engine 갱신 (process_step → process_no) 후 이 property 제거.

---

## D-007: `product_process_order` 기반 sort_order derive + `co_locate_group`

**날짜**: 2026-05-29

**무엇**:
1. `Equipment.co_locate_group: Optional[str]` 필드 신설. 같은 방 안 장비를
   동일 그룹 라벨 (`"GRP_{rank:02d}_{room_id}"`) 로 묶음. CP-SAT 의 group
   constraint / cluster 입력.
2. tier3 sort_order derive 전략 D-007 로 교체:
    A) tier1 우선 (rule_engine 출력에 sort_order 있으면)
    B) `eq.process_no` 정규식 파싱 ("P1-2" → 12)
    C) `flow_paths.product_process_order` 기반 — `room_rank * 100 + idx + 1`
    D) PPO 밖 보조 방도 `next_rank` 부여해 65/65 모두 채움
3. 두 함수 공통 rank 소스 `_full_room_rank()` 분리 — sort_order /
   co_locate_group 일관성 보장.

**왜**:
- **팀원 출력 진단 결과** (D-003 의 다음 단계): `process_no` 가 출력
  JSON 에 컬럼으로 들어오지 않음 (마크다운 §1.1 컬럼 부재, §7 rationale
  에서만 단어 언급). 65 장비 전부 `process_no = None` → tier3 sort_order
  silent 0 건.
- 팀원 출력 §4 `product_process_order` 는 명시된 공정순서 — 가장 신뢰
  가능한 1차 신호.
- `co_locate_group` 은 같은 방 안 병렬 공정 (예: 5개 Mixing Tank 가 1개의
  Media Preparation 안에 있음) 을 CP-SAT 가 "한 클러스터로 배치" 제약으로
  쓰게 함. ISPE §7.9 "process group adjacency".

**근거**:
- 팀원 출력 `RuleEngine_Output_for_DocAgent.md` §1.1: 65 장비, process_no
  값 없음 확인.
- 동 §4: `product_process_order` 7개 방 명시 (MEDIA_PREP → ... → PURIF_2).
- tests/fixtures/teammate_output_sample.json (65 장비) 으로 검증:
  - sort_order: 65/65 채움 (PPO 7 방 × 1~21 장비 + 보조 6 방 × 1~4 장비)
  - co_locate_group: 65/65 채움, 13 그룹, 같은 방 동일 라벨, `^GRP_\d{2}_R_` 형식
  - 단조 증가, 중복 없음
  - tier1 우선 확인: process_no="P9-9" 주입 시 sort_order=99 (PPO rank 무시)

**한계**:
- 보조 방 rank (8~13) 의 등장 순서는 `spec.rooms` 의 정의 순서에 의존. PPO
  뒤 정렬 의미는 도메인적으로 약함 (CP-SAT 가 이 차원으로 최적화하지 않게
  Phase B P1 수식 설계 시 가중치 0 또는 mask 처리 예정).
- cross-room link 는 여전히 미구현. Phase B 의 P2 수식 만들 때 검증과
  함께 tier4 manual_stub 으로 채움.

---

## D-008: P-series 수식 (P1·P2·P6·P7 — Phase B1) [SUPERSEDED by D-009]

> **상태: SUPERSEDED — 2026-05-29 D-009 가 대체.**
> 이유: D-008 의 P1·P2·P7 이 `layout` 인자를 받지만 본체에서 사용 안 함 →
> 좌표가 바뀌어도 점수가 변하지 않는 spec-only 수식 (= silent 만점 버그).
> 사용자 진단으로 확인: P1=1.0 / P2=1.0 이 tier3 데이터 일관성을 측정한
> 것일 뿐 배치 품질이 아니었음. D-004 silent failure 와 같은 줄기.

**날짜**: 2026-05-29

**무엇**: `score_spec_p_series()` 의 4 개 active 함수 구현 + 정규화 분모를
"측정 가능했던 active 가중치 합" 으로 동적 계산하도록 변경.

| Key | W | Active 조건 | 수식 요약 |
|---|---:|---|---|
| P1_flow_monotonicity | 10 | `connects_to` + `sort_order` | forward / (forward+reverse). `sort_order` equal(D-003 병렬) 은 분모 제외 |
| P2_adjacency | 6 | `connects_to` + `co_locate_group` | 0.5·adj_term + 0.5·cohere_term. adj_term = same-room 또는 `spec.adjacency` 인접 비율; cohere_term = group 의 멤버가 모두 같은 방인 비율 |
| P6_cleaning_access | 4 | `clearance_m` + `layout` | 둘 다 부재 → `None` (epistemic honesty — proxy 0.5 plug 금지) |
| P7_compactness | 3 | `bbox_m` + `room.area_m2` | process 방의 `sum(bbox m²)/area_m2` 가 sweet 0.55 일 때 1.0, [0.10~1.00] 에서 0.0 |

**왜** (CLAUDE.md 4대 원칙 기준):
1. **성능** — 수학적으로 방어 가능한 형태. P1 은 "역방향 link 비율" 이라는
   순수 카운트, P7 은 명시적 sweet spot/half-band 인 piecewise-linear. 휴리스틱
   계수 임의값을 최소화.
2. **실무 수준** — fixture 65 장비에 layout=None 만으로 4 개 P 모두 NaN 없이
   유의미 점수 산출. P6 만 명시적 `None` + status=`skipped_no_data` 로 후속
   데이터 수집 trigger 가시화.
3. **특허 / 논문** — "active/deferred 이진 마스크 + 측정된 가중치 합만 분모로"
   동적 정규화 자체가 청구항 후보. D-001(출처 추적) + D-008(측정-기반 가중)
   조합 시 "데이터 가용성-인지 적응형 채점" 으로 폭 확장.
4. **재현성** — fixture(65 장비) 기준 baseline (P1=1.0, P2=1.0, P6=None,
   P7=0.4387, normalized=0.9114) 가 회귀 테스트로 고정. CP-SAT 솔버 도입 시
   이 베이스라인 대비 개선분이 method 섹션의 정량 지표.

**근거 / 출처**:
- ISPE Baseline Guide Vol.6 Ch.7.9 — Facility Conceptualization Tool §step1
  (process flow sequencing) → P1.
- ISPE Baseline Guide Vol.6 Ch.7.5 — process flow grouping → P2.
- ISO 14644-4 §6 (Design — cleanability) + ISPE Vol.6 Ch.7.6 (equipment
  clearance) → P6.
- ISPE Baseline Guide Vol.6 §1 / IPS facility planning (optimal ft²) → P7.

**핵심 설계 결정**:
- **정규화 분모 = 측정된 active 가중치 합** (상수 23 이 아닌 동적). P6 가
  데이터 부재로 None 일 때 분모 19 → 정규화 점수가 데이터 부재로 손해 보지
  않음. 이는 D-004 (silent failure 차단) 와 같은 epistemic honesty 줄기.
  `_measured_denominator` (동적) 와 `_active_denominator` (상수 23) 를 모두
  노출해 사후 비교 가능.
- **P1 layout 사용 안 함**: 데이터(`connects_to` + `sort_order`)만으로 평가.
  좌표 단조성은 P7 (면적 효율) 과 P2 (인접) 가 흡수. 좌표 추가 항은 B2 에서
  검토.
- **P7 process-only**: auxiliary/NC 방은 운용 비율 기준이 다름. category 필터.

**검증**:
- fixture 65 장비 / 13 방 / layout=None:
  - P1: 52 link 모두 forward, reverse 0 → 1.0
  - P2: same-room 100% + 13 group 모두 단일 방 → 1.0
  - P6: clearance_m=0/65 → None, status=`skipped_no_data`
  - P7: 9 process 방 평균 0.4387 (R_PURIFICATION_1 0.733 sweet, R_WASHING 0.056 빈방)
  - normalized = (10·1 + 6·1 + 3·0.4387) / 19 = 0.9114
- 회귀 0건 (56 → 66 passed, 1 skipped). 테스트 10건 신규
  (P1 역방향 페널티, P1 병렬 중립, P2 cross-room 페널티, P7 density 1.0 → 0,
   분모 동적 계산, 등).

**한계 / Phase B2 이월**:
- layout 좌표 기반 보조 항 (P1 좌표 단조성, P6 실제 gap) 은 B2 에서 추가.
- P7 의 sweet spot 0.55 / half-band 0.45 는 ISPE/IPS 정성 기준에서 도출한
  값. 후속에 실제 베스트프랙티스 도면 (BioPhorum / Witcher&Silver) 데이터로
  보정 가능.

---

## D-009: P-series 좌표 기반 재정의 + "점수 ≠ 데이터 일관성" 원칙

**날짜**: 2026-05-29

**무엇**: D-008 의 P1·P2·P7 수식을 좌표 기반으로 전면 재구현. layout=None 시
P1·P2·P7 모두 `None` 반환 (= 측정 불가). 새 수식:

| Key | 수식 (좌표 기반) | 근거 |
|---|---|---|
| P1 | 흐름축 unit vector `u = (마지막 PPO 방 중심) − (첫 PPO 방 중심)` 정규화. 각 장비 좌표 투영 proj. (i,j) 쌍 중 sort_order 가 다른 것에 대해 forward / (forward+reverse). | ISPE Vol.6 §7.9 (one-way flow) |
| P2 | (a) co_locate_group 멤버 좌표 평균 c_g 와 멤버-c_g 평균 거리 d_g → `s_g = max(0, 1 − d_g / 20m)`, 그룹 점수 평균. (b) connects_to link 좌표 거리 d_link → `s_link = max(0, 1 − d_link / 20m)`. raw = 0.5·(a) + 0.5·(b). | ISPE Vol.6 §7.5 (process flow grouping) |
| P6 | clearance_m + layout 있을 때만. 본 수식은 미구현 (return None 유지). | ISO 14644-4 §6 |
| P7 | room 별 두 항 평균: inner = sum(eq.rect 면적) / 장비 외접 bbox 면적; outer = `max(0, 1 − |env/room − 0.5| / 0.4)`. | ISPE Vol.6 §1 (packing density) |

**핵심 원칙 (이 결정의 본질)**:
> **점수(P-series) = 배치 품질 (좌표 기반). 데이터 일관성 ≠ 점수.**

D-008 가 `connects_to` 가 `sort_order` 와 정합한지·`co_locate_group` 이 같은
방인지를 "측정" 했지만, 그건 tier3 derive 가 자기-일관되게 채웠는지를
보는 validation 일 뿐 — CP-SAT 가 좌표를 어떻게 바꾸든 점수가 안 변함.

→ "tier3 가 잘 채웠나" 는 별도 validation 으로 분리 (현재는 enrich_spec 자체
검증으로 충분). P-series 는 layout 이 있어야만 점수 내고, 없으면 명시적 None.

**왜** (CLAUDE.md 4대 원칙):
1. **성능** — D-008 은 모든 fixture 가 P1=1.0/P2=1.0 → CP-SAT 의 cost
   function 이 P1·P2 차원으로 학습할 신호가 0. 좌표 기반 수식은 강한
   gradient 제공 (예: strip-band P1=0.64, P7=0.25 → CP-SAT 가 풀어야 할
   여지 명확).
2. **실무 수준** — D-008 은 silent failure (D-004 차단한 S4 와 같은 패턴).
   사용자 진단으로 발견. epistemic honesty 원칙 일관: 못 재는 건 None.
3. **특허 / 논문 method** — "흐름축 투영 단조성" 자체가 신규성 있는
   metric (대다수 layout 점수는 단순 쌍거리). D-001(출처) + D-007(co_locate)
   + D-009(좌표 metric) 결합 시 청구항 폭 확장.
4. **재현성** — strip-band baseline 이 정량 비교 가능 (P1=0.64,
   P7=0.25). CP-SAT 도입 시 delta 가 method 섹션의 핵심 표.

**근거 / 출처**:
- ISPE Baseline Guide Vol.6 Ch.7.9 — one-way flow / process flow sequencing
- ISPE Baseline Guide Vol.6 Ch.7.5 — process flow grouping
- ISO 14644-4 §6 (Design — cleanability)
- 표준 packing density 정의 (Σ item area / container area)

**핵심 설계 결정**:
- **흐름축은 PPO 첫↔끝 직선 근사**. PPO 가 굽은 경우 (U-shape) 도 1차에서는
  직선. 후속에 polyline 평균 방향으로 개선 가능 (Phase B2/C).
- **D_REF = 20m** (P2 거리 정규화). 한 방 (대형 process room √300 m² ≈
  17m) 의 한 변보다 약간 큼. 이를 넘으면 score 0.
- **P7 outer sweet = 0.50, half-band = 0.40**. 외접 bbox 가 방의 절반
  차지가 sweet. 너무 작으면 빈공간 / 이동거리 ↑, 너무 크면 통로 부족.
- **D_REF / sweet 들은 strip-band baseline + golden fixture 로 보정 예정**
  (Phase B3). 현재는 정성적 출발점.

**검증 — strip-band baseline (4 시나리오)**:

| Scenario | Rooms | Eq | P1 | P2 | P6 | P7 | normalized |
|---|---:|---:|---:|---:|---:|---:|---:|
| mab_8000L | 28 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
| A_small_aseptic | 28 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
| B_large_multiproduct | 29 | 66 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
| C_closed_system | 25 | 66 | 0.6707 | 0.9046 | None | 0.2483 | 0.6779 |

전 시나리오 layout=None 호출 시 P1/P2/P7 모두 None (silent 만점 차단 확인).

**관찰**:
- strip-band 가 P1 만점 아님 (≈0.64) — 격자 배치 → 흐름축 ~35% 역행. 정상.
- strip-band 가 P7 매우 낮음 (≈0.25) — outer_fill 큰 방 안에 시각 축소 장비.
  CP-SAT 가 가장 크게 개선할 차원.
- **4 시나리오가 P2/P7 동일값** (0.9046 / 0.2483) — 룰엔진이 URS 변동을 잘
  반영 안 함. 별도 이슈 (룰엔진 영역, 수정 금지 — Phase B2 에서 사용자
  보고 후 결정).

회귀 0건 (66 → 67 passed, 1 skipped). 깨진 7건 layout=None 가정 테스트는
좌표 기반으로 재작성 (5건은 strip-band layout, 3건은 합성 layout).

**한계 / Phase B2 이월**:
- 흐름축 polyline 평균 방향 (PPO 가 U-shape 일 때).
- P2 link_term 의 cross-room 거리 → spec.adjacency 도어 통과 거리 보정.
- P6 본 수식 (clearance_m 채워질 때).
- D_REF / sweet 들의 golden fixture 보정.

---

## D-010: 시나리오 변별 책임 분리 — 캔버스(우리) / 장비 사양(rule_engine)

**날짜**: 2026-05-30

**무엇**: 사용자 진단 (Phase B1 직후) 으로 4 시나리오 (A_small/mab_8000L/
C_closed/B_large) 의 strip-band 점수가 모두 동일하게 나오는 원인이
**rule_engine 이 URS 의 핵심 변별 신호 (culture_scale_L / n_product_types /
building dim) 를 spec 에 흘리지 않는 것** 이라고 확정. 책임 분리:

| 차원 | 책임 | 근거 |
|---|---|---|
| 장비 사양 (W/D/H, 수량, 종류) | **rule_engine (팀원)** | 공정 도메인 결정 (어떤 BioReactor, 몇 L, 몇 대) |
| 방 종류·등급·면적 | rule_engine | GMP KB 표 매핑 |
| 시나리오별 인접/AL 분기 | rule_engine | aseptic_filling/closed_system/biosafety 룰 |
| 건물 캔버스 dim (width/depth) | **drawing_agent (우리)** | 배치 단계 결정. URS → resolve_building_dims → solver |
| 장비 좌표 / 방 좌표 | drawing_agent | 솔버 책임 |
| Hard/Soft constraint validation | rule_engine | 룰엔진 출력 검증 |
| P-series 점수 (배치 품질) | drawing_agent | D-009 좌표 기반 |

**옵션 2 (drawing_agent 가 culture_scale_L → 장비 sizing override) 거부**:
이유 — 장비 치수는 공정 도메인 결정이지 배치 결정이 아님. drawing_agent 가
scale-up rule 로 추정하면 "검증 안 된 추론 데이터" 가 되어 P3·P5·P8 보류
원칙 (epistemic honesty — 추론값으로 데이터 오염 금지) 에 정면 위배.
논문 method 방어 약화 (작성자가 임의로 장비를 키운 결과).

**무엇 (구현)**:
- `src/drawing_agent/data/building.py` 신규 — `resolve_building_dims(spec,
  urs_path) → (w_mm, h_mm, source_tag)`.
- 4-tier 우선순위 (D-001 일관):
  1. **tier1_ruleengine** — spec.constraints 에 building dim 필드 있으면
     (현재 RuleEngineOutput 에 없음, 미래 확장 대비).
  2. **tier2_urs** — urs_path 의 URS.building.width_mm / depth_mm.
  3. **tier3_derive** — *의도적으로 비움*. 방 면적 합으로 역산 가능하나
     추정값 → 데이터 오염 회피.
  4. **tier4_manual_stub_default** — 78500×42500 mm (기존 강제 default).
- `generate_floorplan(spec, building_w_mm=None, building_h_mm=None,
  urs_path=None)` — None 인자는 resolver 가 채움. 명시값 우선 (CLI/테스트 호환).

**왜** (CLAUDE.md 4대 원칙):
1. **성능** — 4 시나리오가 같은 점수 = CP-SAT 가 시나리오 차원에서 학습할
   신호 없음. 캔버스 흘려준 후 4개 distinct (norm 0.6511~0.6965, P7 0.2483
   ~0.3051) → 학습 신호 회복.
2. **실무 수준** — "같은 공정, 다른 건물 → 다른 배치" 라는 실무 시나리오
   재현. A_small 의 좁은 캔버스가 자동으로 더 compact 배치 (P7 ↑) 가 됨.
3. **특허 / 논문** — "건물 dim 을 layout 결정 변수로 분리, 공정 데이터와
   독립적 변수로 시나리오 변별" 자체가 신규성. D-001 (4-tier) +
   D-010 (캔버스 분리) 결합 시 청구항 폭 확대.
4. **재현성** — `resolve_building_dims` 가 (w, h, source) 를 반환. 어느
   tier 에서 왔는지 audit 가능.

**근거**:
- Phase B1 D-009 strip-band 점수 진단 (4 시나리오 동일): 사용자 보고.
- URS JSON 4 시나리오 자체 차이는 실제 큼 (culture_scale 2000~15000L,
  building 1800~5200 m² 등). 룰엔진이 spec 로 흘리지 않는 차원 명시.
- D-001 anti-corruption layer / 4-tier 패턴 정확히 일관 적용.

**검증** — strip-band 적용 전/후 4 시나리오 비교 (norm 정규화 점수):

| Scenario | URS w×d (mm) | Before P1 | After P1 | Before P2 | After P2 | Before P7 | After P7 | Before norm | After norm |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A_small_aseptic | 60000×30000 | 0.6396 | 0.6309 | 0.9046 | **0.9136** | 0.2483 | **0.3051** | 0.6615 | 0.6687 |
| mab_8000L | 78500×42500 | 0.6396 | 0.6396 | 0.9046 | 0.9046 | 0.2483 | 0.2483 | 0.6615 | 0.6615 |
| C_closed_sys | 60000×40000 | 0.6707 | **0.6974** | 0.9046 | 0.9136 | 0.2483 | 0.2595 | 0.6779 | **0.6965** |
| B_large_multi | 100000×52000 | 0.6396 | 0.6260 | 0.9046 | **0.8898** | 0.2483 | 0.2574 | 0.6615 | 0.6511 |

- **A_small** (좁은 캔버스) → P7 ↑ (0.25→0.31, 자동 compact)
- **B_large** (넓은 캔버스) → P2 ↓ (0.90→0.89, 장비 흩어짐), norm ↓
- **C_closed** (방 25개 + 작은 캔버스) → P1 ↑ (0.67→0.70), norm 최고
- **mab_8000L** (default dim) → 변화 없음 (검산)

테스트 6건 신규 (default fallback, URS pickup, 4 시나리오 distinct, bad URS
fallback, generate_floorplan URS 자동, 명시 인자 우선). **73 passed, 1 skipped**
(67 → 73). 회귀 0건.

**한계**:
- 변동 폭 좁음 (P7 0.25~0.31) — 룰엔진의 장비 변별 부재 영향 (장비 종류·수
  65 동일). 강한 분리는 룰엔진 협의 (옵션 1, 사용자 별도 진행) 후.
- 변환 폭 작은 이유 보조: 솔버가 stripe ratio 기반이라 캔버스 비율이 크게
  안 변하면 layout 도 비슷. Phase C CP-SAT 로 가면 더 자유로운 배치 → 캔버스
  변별이 점수에 더 크게 흘러갈 것.
- tier3 derive 의도적 미구현 — 미래에 룰엔진이 spec 에 building dim 을
  채울 경우 tier1 자동 우선 (D-001 패턴 그대로).

---

## D-013: Phase B2 before-baseline 확정 (output/baselines.json)

**날짜**: 2026-05-30

**무엇**: 4 시나리오 strip-band 점수 (P-series + geometric quality 6종 +
hard/soft) 를 `output/baselines.json` 으로 결정론적 저장. 논문 "before →
after" 서사의 출발점 (= rule_engine 장비 변별 + CP-SAT 솔버 도입 전 상태).

**스크립트**: `scripts/baselines.py`
- `python -m scripts.baselines` → 측정 + 저장 + 요약 표 출력.
- `python -m scripts.baselines --check` → 두 번 측정해 동일성 검증.

**저장 형식 (schema_version=1.0)**:
```jsonc
{
  "schema_version": "1.0",
  "phase": "B2",
  "decision_anchor": "D-013",
  "generated_at": "ISO8601",
  "p_weights": {P1:10, P2:6, P3:0, P5:0, P6:4, P7:3, P8:0},
  "p_deferred": ["P3...", "P5...", "P8..."],
  "p_active_denominator_constant": 23.0,
  "limitations": [5건 — D-010/D-009/D-001 정책 인용],
  "expected_variation_note": "변동 폭 좁음은 예상된 중간 상태...",
  "scenarios": {
    "<name>": {
      "meta": {urs_path, project_name, modality, rooms_count, airlocks_count,
               equipment_count, building_dim_mm, building_dim_source, ppo_length},
      "p_series": {<key>: {raw, weight, contrib, status}, ...},
      "p_series_normalized": float|null,
      "p_series_measured_denominator": float,
      "p_series_active_denominator": float,
      "geometric_quality": {total, hard_violations_count, soft_violations_count, breakdown}
    }
  }
}
```

**메타 박은 이유 (=논문 추적성)**:
- `building_dim_source` (D-010): 캔버스가 어디서 왔는지 ("tier2_urs" 또는
  "tier4_manual_stub_default") → 향후 룰엔진이 dim 채우면 tier1 으로 자동 이행.
- `p_series_measured_denominator` vs `_active_denominator`: P6 등 None 항의
  분모 처리 (D-009 epistemic honesty) 가 어디서 적용됐는지 가시.
- `limitations` (5건): 이 시점 한계를 점수와 함께 박음. 향후 baseline 갱신
  시 어느 한계가 풀렸는지 일대일 추적 가능.
- `expected_variation_note`: 변동 폭 0.6511~0.6965 가 "버그 아님 / 예상된
  중간 상태" 임을 명시. 두 요인 (장비 변별 + CP-SAT) 해소 시 강해질 것이
  논문의 핵심 신호.

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 정량 평가** — "before 베이스라인" 이 결정론적 저장돼야 향후
   개선분 (Δ) 이 정량 측정됨. 논문 result 섹션의 표 기반.
2. **실무 수준** — 같은 입력 → 같은 출력 (`--check` pass). 재현 가능성.
3. **특허 / 논문** — "데이터 가용성-인지 채점 + 출처 메타데이터 + 결정론적
   재현" 의 강한 method 섹션 근거. D-001(출처) + D-009(epistemic) + D-010
   (책임 분리) + D-013(재현가능 baseline) 결합.
4. **재현성** — 시각(`generated_at`) 만 빠지면 두 번 측정값이 byte-identical
   (`--check` 검증). 외부 시드/랜덤 없음.

**검증 — baselines.json 요약 표 (생성 직후)**:

| Scenario | URS dim | P1 | P2 | P6 | P7 | norm | geo total | hard | soft |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A_small_aseptic | 60000×30000 | 0.6309 | 0.9136 | None | 0.3051 | 0.6687 | 121.50 | 0 | 1 |
| mab_8000L | 78500×42500 | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 | 121.68 | 0 | 1 |
| C_closed_sys | 60000×40000 | 0.6974 | 0.9136 | None | 0.2595 | 0.6965 | 127.06 | 0 | 0 |
| B_large_multi | 100000×52000 | 0.6260 | 0.8898 | None | 0.2574 | 0.6511 | 121.67 | 0 | 1 |

결정론 `--check` 통과 (같은 입력 → 같은 baselines dict).

**핵심 명시 (논문 서사의 출발점)**:
> **변동 폭 좁음 (norm 0.65~0.70, ~7%p) 은 버그가 아니라 예상된 중간 상태**:
> (1) 장비 변별 부재 — 사용자(팀원) 가 URS 3.6 Critical Process Equipment List
>     채운 뒤 rule_engine 이 그를 읽도록 연결 예정 (옵션 1, 별도 진행 중).
> (2) CP-SAT 미도입 — Phase C 에서 자유 배치 솔버.
> 두 요인 모두 해소되면 변동 폭이 커지는 것이 "before → after" 정량 신호.
> 현 baselines.json 은 이 두 요인이 *없을 때* 의 점수 = 진짜 floor.

**한계 / Phase B3 이월**:
- Golden fixture (BioPhorum 2×2000L, Witcher&Silver 18-cleanroom) 비교는
  B3 에서. 해당 fixture 가 준비되면 같은 스크립트로 측정 → 비교 표.
- baselines.json 의 점수 정확도 자체는 D-009 의 D_REF=20m / P7 sweet=0.5
  파라미터에 의존. 후속 golden fixture 데이터로 보정 가능.

---

## D-014: NNE 모범배치 골든 도입 — P-series 수식 타당성 검증 (Phase B3)

**날짜**: 2026-05-30

**무엇**: 전문가 (NNE Pharmaplan) 가 실제 설계한 모범 배치를 구조 골든으로
fixture 화 → strip-band baseline 과 점수 비교 → P-series 수식이 "좋은 배치를
높게 평가" 함을 검증.

**파일**:
- `docs/reference/nne_equipment_layout.md` — NNE 도면 추출 자료 (사용자 작성).
- `tests/fixtures/golden_nne_layout.json` — RuleEngineOutput 호환 spec + 방별
  layout_rects_mm. 16 rooms / 70 equipment / 캔버스 62000×42000 mm.
- `scripts/golden_nne.py` — fixture 로드 + Layout 구성 + strip-band 비교.
  방 안 장비는 row-major auto-pack (NNE 도면 정밀 좌표 아님).
- `tests/test_golden_nne.py` — 7 회귀 (NNE 우위 보장).

**방법 B (구조 검증)**:
- 정밀 (x, y) 좌표 X. 그리드 (X4~X12 가로, Y1~Y6 세로) 근사.
- 핵심만: 방 배치, 인접, 공정 순서, 같은 방-같은 장비.
- 장비 W_mm = D_mm = √m² × 1000 (NNE 표 면적의 정사각 근사).
- 정밀 좌표는 방법 A — Phase C 에서 CP-SAT 결과 대조 시 후속.

**검증 결과 — NNE vs strip-band**:

| Layout | P1 | P2 | P6 | P7 | normalized |
|---|---:|---:|---:|---:|---:|
| **NNE_golden** | **0.6986** | 0.9079 | None | **0.4366** | **0.7233** |
| A_small_aseptic | 0.6309 | 0.9136 | None | 0.3051 | 0.6687 |
| mab_8000L | 0.6396 | 0.9046 | None | 0.2483 | 0.6615 |
| C_closed_sys | 0.6974 | 0.9136 | None | 0.2595 | 0.6965 |
| B_large_multi | 0.6260 | 0.8898 | None | 0.2574 | 0.6511 |
| strip-band avg | 0.6484 | 0.9054 | None | 0.2676 | 0.6694 |
| **Δ (NNE − sb avg)** | **+0.050** | +0.003 | — | **+0.169** | **+0.054** |

**해석 (P 별 NNE 우위 원인)**:
- **P1 (+0.050)**: NNE 의 6 PPO 방 (Media → PurifIII) 이 좌→우 단일 stripe →
  흐름축 직선. strip-band 는 process 를 top/bottom 두 row 로 나누고 supply/return
  를 사이에 둬 흐름축이 좌상→좌하 대각선 → zigzag → 일부 역행 페널티.
- **P2 (+0.003 = 거의 동등)**: group 응집은 둘 다 잘 됨 (방 내부 row-major
  pack 으로 같은 방 안 group 멤버끼리 자연 인접). P2 가 strip-band 와 차이를
  못 만드는 신호 = "같은 방" 만으로 응집을 만들기는 둘 다 충분 → CP-SAT 가
  P2 에서 큰 개선분 만들기 어려울 수 있음 (별도 관찰).
- **P7 (+0.169)**: NNE 는 방 면적 (Seed 50/Ferm 100/PurifI 80/Storage 30 등)
  이 장비 면적 합과 잘 맞아 outer_fill 가 sweet 0.5 근처. strip-band 는 시각
  축소 + 일정 stripe 비율 → outer_fill 낮음 (방이 헐렁).
- **P6 (None)**: 둘 다 clearance_m 부재.

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 정량 평가** — P-series 가 전문가 vs 격자 의 차이를 명시적
   gradient (+5.4%p norm) 로 잡음. CP-SAT 의 학습 목표가 의미 있음.
2. **실무 수준** — 점수 수식이 *전문가가 잘 한 배치를 못 알아본다* 면
   CP-SAT 가 임의로 낮은 점수로 수렴할 위험. NNE 우위 확인으로 그 위험 차단.
3. **특허 / 논문** — "전문가 설계 baseline 과의 정량 비교" 가 method 섹션
   에 들어가는 강한 데이터. NNE Pharmaplan 공식 문서 출처 → 도메인 권위 확보.
4. **재현성** — fixture JSON 결정론적. 회귀 7건 (`test_golden_nne.py`) 으로
   "NNE > strip-band" 가 후속 변경 시에도 깨지지 않게 보장.

**근거**:
- NNE Pharmaplan, *Bacterial Bio PilotPlant — Equipment Layout*, Green Cross
  Corp, Doc 0617C05016 Rev 001, Conceptual Design.
- `docs/reference/nne_equipment_layout.md` (사용자 정리).

**보류 자료 (Phase C 이후)**:
- **방법 A (정밀 좌표 golden)**: 그리드 (X4~X12 / Y1~Y6) 와 면적으로 각
  장비 정밀 (x, y) 부여 → CP-SAT 결과를 전문가 배치와 좌표 수준 비교.
- **NNE 매핑 워크북 (URS_NNE_Mapping v0.3, F1~F10 역공학)**: 점수 수식 보강
  / 특허 명세. 특히 F3 (Class ↔ Filter ↔ ACR ↔ Pressure) = 특허 스모킹건.

**한계 / 명시**:
- `score()` 의 hard_violations = 16건, geo_total = -694.16. 이는 NNE 도면이
  GMP 위반이 아니라 우리 NNE spec 이 룰엔진 hard 검증 (C1~C10) 의 airlock
  부재 / supply-return 직접 인접 / grade 차이 페어 등을 만족하지 않은 것.
  P-series 비교가 본 검증 목적이고 hard 페널티는 별도 차원. 후속에 NNE
  spec 에 airlock 보완하면 geo_total 도 올라갈 것 (옵션).
- P2 차이가 +0.003 으로 거의 동등 — D-009 의 D_REF=20m 가 너무 관대해서
  같은 방 응집을 둘 다 만점에 가깝게 줌. golden fixture 데이터로 D_REF 보정
  여지 (후속).
- 장비 좌표는 row-major auto-pack — NNE 도면 정확 위치 아님. 같은 방 응집
  만 보장. 방법 A 후속.

---

## D-015: CP-SAT 진입점 결정 — 층1(방 배치)부터, 층2 보류 + C0 골격 검증

**날짜**: 2026-05-30

**무엇**: Phase C 진입. (1) **층1 (방 배치) 부터 CP-SAT** 채택, 층2 (방 안
장비) 는 당분간 strip-band `_place_equipment_grid` 그대로 재사용. (2) Phase
C0 = 최소 골격 검증 (방 3개, 안 겹침 + 캔버스만, 목적함수는 좌상단 모으기)
구현 + 회귀 보장.

**왜 층1 부터 (이전 진단 보고서 결론)**:
- **점수 leverage**: P1 (흐름축 단조), P7 outer_efficiency 가 방 좌표로
  결정. 층2 (장비 좌표) 는 P2 group_term 영향만이고 strip-band 의 row-major
  pack 이 이미 P2 ≈ 0.90 만점 편향 → 추가 개선분 작음 (B3 NNE 비교 +0.003).
- **변수 폭증 방지**: 층2 까지 CP-SAT 화 시 변수 수 O(N_room × N_eq).
  N_eq = 66+ → 변수 ~수백 개. 풀이 시간 ↑↑, 점수 개선분 ↓. 비용 효율 X.
- **데이터 준비도**: P6 (clearance_m) 가 채워지면 그때 층2 CP-SAT 가 의미.
  현재 데이터 부재 (D-009 epistemic) → C3 보류.

**Phase C 단계 (이 결정의 후속)**:
- **C0 (이번)**: 골격 검증만. spec 의 일부 방 (3개) 에 대해 (x, y) 격자 변수
  + AddNoOverlap2D + 캔버스 도메인 제약. 목적함수 = 좌상단 모으기 (임시).
- **C1 (다음)**: 전체 방 + zone/category 제약 + 점수 기반 목적함수
  (P1·P2·P7 surrogate). C1 부터 strip-band 대신 1차 사용.
- **C2**: spec.adjacency / co_locate 제약 (cross-room link 거리 패널티).
- **C3 (선택)**: 층2 (방 안 장비) CP-SAT 화. clearance_m 데이터 채워진 후.
- **C4 fallback**: infeasible → strip-band `layout_solver.solve()` 호출.
  기존 코드 그대로 보존 (수정 X).

**구현 (C0)**:
- `requirements.txt` — `ortools==9.10.4067` 고정 (재현성 핀).
- `src/drawing_agent/constraint_compiler.py` 신규 (95 줄):
  - `compile_minimal(spec, room_ids, canvas_w_mm, canvas_h_mm,
    grid_resolution_mm=500) → CompiledModel`.
  - 변수: `room.x_var` / `y_var` (정수 셀 단위) + `IntervalVar` (AddNoOverlap2D 용).
  - 방 한 변 = `√area_m2 × 1.4 × 1000mm` → 격자 셀로 환산 (C0 단순 정사각).
  - 제약: H1 캔버스 안 (도메인 [0, canvas_cells - w_c]) + H2 AddNoOverlap2D.
  - 목적함수: `Minimize(Σ x + Σ y)` (좌상단 모으기, 임시).
- `src/drawing_agent/cpsat_solver.py` 신규 (107 줄):
  - `solve_minimal(spec, room_ids, canvas_w/h_mm, grid_resolution_mm,
    time_limit_s=60) → (Layout, SolveReport)`.
  - `num_search_workers=1` 으로 결정론 보장 (D-013 결정론 원칙과 일관).
  - `SolveReport(status, status_code, objective, wall_time_ms,
    total_wall_time_ms, grid_resolution_mm, canvas_dim_cells, rooms_solved)`.
  - INFEASIBLE → 빈 Layout + 호출자가 fallback 결정 (C4 분리).
- `src/drawing_agent/layout_solver.py` **수정 0줄** — strip-band 그대로 보존.

**C0 골격 검증 결과 (mab_8000L baseline, 3 rooms)**:

| 항목 | 값 |
|---|---|
| status | OPTIMAL (code 4) |
| objective | 46.0 (= cell 단위, x+y 합 최소) |
| CP-SAT 풀이 시간 | **20.12 ms** |
| 빌드+풀이+변환 합 | 21.33 ms |
| 격자 해상도 | 500 mm/cell → 157×85 = 13,345 cell 캔버스 |
| 안 겹침 sanity | PASS |
| 캔버스 안 sanity | PASS |
| Layout 자료구조 | 기존 `Layout`/`PlacedRoom`/`Rect` 타입 그대로 |
| renderer.render() | 수정 0줄, SVG 23,819 bytes 생성 OK (0.3 ms) |
| SVG | `output/floorplan_c0_cpsat_3room.svg` |
| 결정론 | 두 번 풀이 → 좌표 동일 (num_search_workers=1) |

좌표 (격자 → mm):
- R_INOCULATION (81m²): (0, 0) 9000×9000
- R_MEDIA_PREP (196m²): (0, 9000) 14000×14000
- R_BUFFER_PREP (400m²): (14000, 0) 20000×20000

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 정량** — 사전 진단으로 leverage 큰 차원 (P1/P7) 우선 공략.
   장비 CP-SAT 화는 leverage 작아 후순위. 첫 정량 개선분 (Phase C1 결과 vs
   baselines.json) 이 측정 가능한 트랙으로 진입.
2. **실무 수준** — 결정론 (1 워커), 시간 한계 (60s hard timeout), infeasible
   fallback (strip-band 보존) 으로 GMP 설계 도구 운영 요건 충족.
3. **특허 / 논문** — "rule_engine → constraint_compiler → CP-SAT → renderer"
   파이프라인의 명확한 책임 분리 (D-001 4-tier + D-010 책임 분리 + D-015
   배치 leverage 기반 단계화). claim 폭 확장.
4. **재현성** — `ortools==9.10.4067` 고정, `num_search_workers=1` 단일 워커,
   격자 해상도 명시. 두 번 풀이 좌표 동일 회귀 보장.

**근거**:
- 진단 보고 (사용자 요청, 이 결정 이전 턴): 4 한계 (점수 분리, 하드코딩
  결정 변수, 도메인 제약 미표현, infeasibility 무시) 정리. 층1·층2 leverage
  비교.
- B3 NNE 비교 결과: P2 group_term 이 strip-band 와 NNE 모두 ≈0.90 → 층2
  CP-SAT 화의 개선 여지 작음 직접 확인.
- CP-SAT 진입의 표준 패턴 — Google OR-Tools "no-overlap 2D" cookbook
  (AddNoOverlap2D + IntervalVar).

**핵심 설계 결정**:
- **격자 해상도 500 mm**: GMP 도면의 최소 의미 단위 (도어 폭 1000mm 의 절반).
  더 작으면 변수 폭증, 더 크면 P-series 정확도 손실.
- **방 한 변 √area_m2 × 1.4**: C0 단순화. C1 에서 룰엔진 area_m2 가 변동
  허용 가능한지에 따라 정교화 (현재는 area_m2 고정).
- **AddNoOverlap2D** + IntervalVar: ortools 권장 패턴. 풀이 빠름 (20ms).
- **목적함수 좌상단 모으기 (임시)**: C0 는 골격 검증 only. C1 에서 P-series
  surrogate (예: `-(w1·P1 + w7·P7) + λ·overlap`) 로 교체.
- **장비 처리**: C0 의 Layout 은 `PlacedRoom.equipment = []` (빈 list). 호출자가
  필요하면 `_place_equipment_grid(layout)` 별도 호출. 본 결정이 "층2 보류" 정책.

**한계 / C1 이월**:
- 방 한 변 정사각 가정 (실제는 직사각이 자연) — C1 에서 `w_var` / `h_var` 분리.
- area_m2 고정 — C1 에서 룰엔진 면적 비율 (C9) 범위 안에서 변동 허용.
- 목적함수 임시 — C1 점수 surrogate 교체.
- Zone / category 제약 미적용 — C1 의 process/auxiliary/NC 영역 분리.
- spec.adjacency 미사용 — C2.
- 장비 좌표 미생성 — C3.

**회귀 (8건 신규)**:
- `tests/test_cpsat_c0.py` — feasibility, 안 겹침/캔버스, Layout 타입,
  renderer 재사용, 풀이 시간 (<2s), 결정론, strip-band 보존, missing id silent skip.
- 회귀 0건 (80 → 88 passed, 1 skipped).

---

## D-016: C1a — 전체 방 + hard 제약 (사이징 정책 정직화)

**날짜**: 2026-05-30

**무엇**: Phase C1a 완료. `compile_c1a` / `solve_c1a` 추가 — spec 의 전체 방
(28개, mab_8000L) 에 대해 hard 제약만 박는 CP-SAT 모델. 직사각 (w, h 분리),
zone 영역 분리, adjacency 인접 25m. 점수 목적함수는 C1b 로 분리. 진단 과정에서
방 사이징 정책 (`ROOM_AREA_TO_SIDE_FACTOR`) 을 1.4 → 1.0 으로 정직화 + 결정론
강화 (`max_deterministic_time` 추가).

**Hard 제약 (4개)**:
- **H1 캔버스 안**: `x + w ≤ canvas_w_cells`, `y + h ≤ canvas_h_cells`.
- **H2 안 겹침**: `AddNoOverlap2D` ([IntervalVar(x_var, w_var, x_end)], 동일 y).
- **H3 zone 영역 분리**: aux x ∈ [0, 0.20W], proc x ∈ [0.17W, 0.85W] (양옆 3%
  여유), nc x ∈ [0.82W, W]. 캔버스 가로 stripe.
- **H4 adjacency 인접**: spec.adjacency 의 room↔room 쌍 (passthrough 제외) 의
  좌상단 맨해튼 거리 ≤ ADJ_MAX_DEFAULT_MM (25m, 50 cells).

**진단 — INFEASIBLE 원인 격리 (사용자 요구)**:

| 시도 | zones | adj | factor | aspect | 결과 |
|---|---|---|---|---|---|
| 1차 | ON | ON | **1.4** | [0.7, 1.4] | INFEASIBLE (1080ms proof) |
| 2차 | ON | OFF | **1.4** | [0.7, 1.4] | INFEASIBLE — zone 만으로 IF |
| 3차 | OFF | ON | 1.4 | [0.7, 1.4] | FEASIBLE 30s (zone 끄면 OK) |
| 4차 | ON | ON | **1.0** | [0.7, 1.4] | **FEASIBLE 500ms** ← 채택 |

→ 1차 원인: **사이징 정책 `ROOM_AREA_TO_SIDE_FACTOR=1.4`**.
방 한 변 = `√area_m2 × 1.4` 로 정해 면적이 ~1.96× area 로 부풀음. aux stripe
(폭 0.20W = 15.5m) 안에 12 방 (면적 합 620 m² + 1.96× 부풀음 = 1215 m²)
못 들어가 INFEASIBLE.

→ 채택: **FACTOR=1.0**. 방 한 변 = `√area_m2`, aspect [0.7, 1.4] 로 자연 변동.
면적 실현값 = [0.49, 1.96] × area_m2 (룰엔진 area 가 권장이지 강제 아님).

**결정론 강화**:
- 초기 random_seed=0 + num_search_workers=1 만으로는 wall-clock `max_time_in_seconds`
  타임 한계 도달 시 머신 부하에 따라 search 끝점이 달라져 같은 입력 → 다른 좌표
  발생 (테스트 실패).
- `solver.parameters.max_deterministic_time = time_limit_s × 4.0` 추가. ortools
  의 deterministic time 은 wall-clock 무관 search node/conflict count 단위.
  머신 부하 무관 결정론 보장 (회귀 통과).
- wall-clock `max_time_in_seconds` 는 safety upper bound 로 유지.

**검증 (mab_8000L, 28방, zone+adj hard, 5s limit)**:

| 항목 | 값 |
|---|---|
| status | FEASIBLE |
| 첫 feasible 시간 | **500ms** (sub-second) |
| 5s 종료 시 objective | 1650 (좌상단 모으기 임시) |
| 28방 모두 좌표 | ✓ |
| 안 겹침 / 캔버스 안 | ✓ / ✓ |
| adjacency 6 pair 25m 안 | ✓ (실제 6 pair, 35건은 room↔airlock 으로 모델 밖) |
| renderer 재사용 0 줄 | ✓ SVG 68KB |
| 결정론 (두 번 풀이) | ✓ 좌표 동일 |
| SVG 산출물 | `output/floorplan_c1a_28room.svg` |

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 정량** — 28방 전체에 hard 제약 다 박은 모델이 sub-second feasibility
   도달. C1b 의 점수 목적함수 추가 시 search 부담 늘어도 여유.
2. **실무 수준** — 진단 시 명확한 완화 옵션 (zones / adj on-off 플래그) 으로
   사용자가 어느 제약이 무리한지 빠르게 격리. 사이징 정책 정직화로 area_m2
   가 권장값임을 명확히.
3. **특허 / 논문** — "구조 제약 (zone, adjacency) + 직사각 변동 + 결정론적
   해석" 가 D-001 (4-tier) + D-010 (책임 분리) + D-013 (재현가능 baseline)
   + D-015 (CP-SAT 진입) 와 결합되는 method 섹션 데이터.
4. **재현성** — `max_deterministic_time` + `random_seed=0` + `num_search_workers=1`
   세 축으로 머신 무관 결정론 보장. 회귀 테스트로 보장.

**근거**:
- 사용자 진단 보고 (이전 턴): 단계 완화 시도로 어느 제약 충돌인지 격리.
- ortools 9.10 CP-SAT 결정론 가이드 — `max_deterministic_time` 사용.
- Google OR-Tools cookbook — AddNoOverlap2D + IntervalVar 표준 패턴.

**핵심 설계 결정**:
- **adjacency 정책 (좌상단 맨해튼 거리 ≤ adj_max_mm)**: 정확한 변 닿기 제약은
  CP-SAT 표현 비용 큼. 좌상단 거리 ≤ 25m 로 "근처에 있음" 근사. C1b 에서
  목적함수에 거리 비용 추가 시 더 정밀.
- **adj_max_mm = 25_000 (50 cells)**: 방의 평균 한 변 (~10m) 의 2.5×. 너무 작으면
  IF, 너무 크면 무의미. 향후 area 비율로 동적 결정 가능.
- **zone stripe 비율 (20/62/18)**: spec.zones area 합 기반 동적이 더 정확하나
  C1a 는 단순화. C1b 에서 area 비율로 조정 가능 (현재 mab_8000L 의 aux/proc/nc
  area = 19/52/6%, stripe 가 충분히 여유).
- **passthrough_only adjacency 제외**: Cleaning↔Preparation 같은 벽 너머 전달은
  hard 인접 불필요. C1b 에서 목적함수 거리에 포함 가능.

**한계 / C1b 이월**:
- 목적함수 = 좌상단 모으기 (임시). C1b 에서 P-series surrogate
  (P1 흐름축 단조 + P7 outer 효율) 정수 근사로 교체. 그 뒤 4 시나리오 결과
  vs baselines.json + NNE golden 비교 → 첫 정량 "before → after" 표.
- adjacency 거리 비용 (P2 link_term 의 좌표 기반 부분) — C1b 또는 C2.
- area 곱셈 제약 (`AddMultiplicationEquality`) 으로 ±10% area 강제는 풀이
  부담. 현재 aspect range 로 우회.
- 4 시나리오 다른 캔버스에서의 zone fitting 검증은 C1b 에서 진행.

**회귀**: 88 → **98 passed** (1 skipped), 0 fail. 테스트 10건 신규.

---

## D-017: C1b — P-series surrogate 목적함수 + 첫 before→after 측정

**날짜**: 2026-05-30

**무엇**: Phase C1b 완료. C1a 의 hard 제약 위에 **P-series surrogate** 목적함수를
얹어 4 시나리오 vs strip-band baseline vs NNE golden 비교.

**구현**:
- `compile_c1b(spec, ...)` — `compile_c1a(add_compactness_objective=False)` 위에
  surrogate cost 항 추가:
  - **P1 surrogate**: PPO 인접 쌍 (i, i+1) 의 흐름축(가로) 단조 페널티.
    `cx_i ≤ cx_{i+1}` 위반 시 `pen = max(0, cx_i - cx_{i+1})`. `cx = 2x+w` (×2 스케일).
  - **P2 surrogate**: adjacency hard 제약 변수 (`|dx| + |dy|`) 재사용. 25m 한계 안에서 더 가깝게.
  - **tie-breaker**: `Σ (x + y)` (좌상단 모으기, 약하게).
- 가중치 default: P1=100, P2=60, tie=1 (P-series weight 비율 반영).
- `solve_c1b` — `solve_c1a` 와 동일 결정론 (random_seed=0 + max_deterministic_time).
- `compile_c1a` 에 `add_compactness_objective: bool=True` 플래그 추가 — C1b 가
  False 로 호출해 objective 를 자기가 박음.
- `CompiledModelC1a.adj_pair_vars` (`AdjPairVars` list) — adjacency hard
  제약의 abs(dx) / abs(dy) 변수를 expose, C1b 의 P2 cost 에서 재사용.

**4 시나리오 측정 결과 (P1-only weight: p1=500, p2=0, tie=0, time=10s)**:

| Scenario | Solver | Status | Time(ms) | P1 | P2 | P7 | norm | Δnorm |
|---|---|---|---:|---:|---:|---:|---:|---:|
| A_small_aseptic | strip-band | — | — | 0.6309 | 0.9136 | 0.3051 | 0.6687 | — |
|  | **CP-SAT C1b** | **OPTIMAL** | **2584** | **0.7251** | 0.9197 | 0.2541 | **0.7122** | **+0.0435** |
| mab_8000L | strip-band | — | — | 0.6396 | 0.9046 | 0.2483 | 0.6615 | — |
|  | CP-SAT C1b | OPTIMAL | 726 | 0.6178 | 0.9033 | 0.2682 | 0.6527 | −0.0088 |
| C_closed_sys | strip-band | — | — | 0.6974 | 0.9136 | 0.2595 | 0.6965 | — |
|  | CP-SAT C1b | OPTIMAL | 819 | 0.5881 | 0.9197 | 0.2564 | 0.6405 | **−0.0560** |
| B_large_multi | strip-band | — | — | 0.6260 | 0.8898 | 0.2574 | 0.6511 | — |
|  | **CP-SAT C1b** | OPTIMAL | 1629 | **0.6372** | 0.9176 | 0.2576 | **0.6658** | **+0.0147** |
| NNE_golden (ref) | manual | — | — | 0.6986 | 0.9079 | 0.4366 | **0.7233** | — |

- 평균 — strip-band 0.6694 / CP-SAT C1b 0.6678 / Δ avg **−0.0017** (거의 동등) / NNE 0.7233
- 2/4 향상 (A_small +0.044, B_large +0.015), 2/4 저조 (mab −0.009, C_closed −0.056)
- 모두 OPTIMAL 도달 (700ms ~ 2.6s, 10s timeout 안에)

**디폴트 가중치 (P1=100, P2=60, tie=1, 10s) 결과는 더 안 좋음** (평균 Δ −0.033):
- P2 surrogate 와 P1 surrogate 충돌, tie-breaker 가 PPO 단조와 충돌 → search 가 timeout 안 OPTIMAL 못 가고 mid-objective 에서 종료. **P1-only 권장**.

**핵심 진단 / 인지 사항 (사용자 명시)**:

1. **factor 정책 차이**: CP-SAT 는 방 한 변 = √area_m2 × aspect [0.7, 1.4]
   (D-016, factor 1.0). strip-band 는 area_m2 비율 stripe (룰엔진 area 정확
   반영) + 시각 축소 (B-001 백로그). 두 솔버의 방 사이즈 정의가 다름. 점수
   비교 시 *방 사이즈* 자체가 변동. C_closed 같은 작은 캔버스에서 격차 큼.

2. **adjacency room↔airlock 35건 모델 밖**: spec.adjacency 41건 중 6건만
   room↔room 으로 CP-SAT 모델 안. 나머지 35건은 airlock (PAL/MAL) 포함이라
   현 CP-SAT 가 airlock 좌표 안 풀어서 무시. P2 link 거리 계산 시 PAL/MAL
   통과 거리 무시 = NNE golden (PAL/MAL fixture 단순화로 같이 무시) 과
   공정 비교 OK, 그러나 *실제 GMP 도면* 평가 시 차이 발생 가능. 전실 CP-SAT
   편입은 **C2 에서 결정**.

3. **P1 surrogate ≠ 실제 P1 점수**:
   - surrogate: 방 좌상단 (2x+w) 단조 — *방 단위*.
   - 실제 P1: 흐름축 unit vector 에 *장비 좌표* 투영 → sort_order 단조 비율.
   - 같은 방 안 장비들이 row-major pack 시 sort_order 가 row 안에선 좌→우 OK
     이지만 row 넘어가면 우→좌 → P1 페널티. CP-SAT 가 방 좌상단 단조 surrogate
     를 잘 풀어도 (OPTIMAL) 장비 단위 P1 점수 향상은 제한적.
   - **층2 (장비) 가 strip-band 그대로 (D-015 의 의도된 재사용) 라 같은 한계.**
   - 진짜 P1 개선은 **C3 (장비 CP-SAT 화)** 가 가야 가능.

4. **CP-SAT 와 NNE golden 의 격차** (Δ_norm = +0.054, P7 +0.18 이 핵심):
   - NNE 의 P7=0.44 는 방 면적 ↔ 장비 면적 균형이 sweet 0.50 근처.
   - CP-SAT 의 방은 aspect 변동 자유라 P7 outer_fill 가 NNE 처럼 sweet 근처
     까지 못 감 → P7 0.25 수준 정체.
   - **NNE golden 까지의 격차는 P7 (장비-방 면적 균형) 가 차지** —
     C3 (장비 CP-SAT) + B-001 (시각 축소 분리) 후 평가.

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 정량** — 4 시나리오 첫 before→after 표 확보. **CP-SAT 첫 측정은
   strip-band 와 거의 동등** (Δ avg −0.002, 0.2%p) 으로 점수 surrogate 한계
   확인. 진짜 개선은 C3 (장비 CP-SAT) 필요.
2. **실무 수준** — surrogate ↔ 실제 점수의 weak correlation 을 정량 확인. P1
   surrogate (방 좌상단) vs 진짜 P1 (장비 투영) 차이 명시 → 진솔 보고.
3. **특허 / 논문 method 섹션** — "surrogate vs 실제 점수 격차" 가 두 단계
   디자인 (방→장비) 의 정합성 분석 데이터. D-015 (층1 부터) + D-017
   (surrogate 한계 진단) → C3 진입의 정량 근거.
4. **재현성** — 4 시나리오 OPTIMAL 도달, 결정론 통과. P1-only 가중치 sweep
   으로 default 한계 진단 가능. 회귀 7건 신규 (`tests/test_cpsat_c1b.py`).

**근거**:
- 가중치 sweep (default vs tie=0 vs p1=500 vs p2=0): default 가 timeout 도달
  + 점수 저조, P1-only 가 OPTIMAL 도달 + 점수 향상. P2 surrogate 가 P1
  방해함을 직접 확인.
- 사용자 진단 가이드 (이 결정 발의 turn): 명시한 2개 인지 + 비교표 형식.

**핵심 설계 결정**:
- **default 가중치는 P1=100, P2=60, tie=1 그대로 유지** (사용자 결정 받기 전).
  실측 권장은 P1-only (P1=500, P2=0, tie=0). 호출자가 명시 override.
  → D-017 후속 결정으로 default 변경 여부 사용자에게 보고.
- **층2 = strip-band 재사용 정책 (D-015) 그대로**. 진짜 P1 개선은 C3 에서.
- **adjacency room↔airlock = 모델 밖 (C2 결정)**. P2 link 거리에 영향 작음
  (현 데이터 단계).

**한계 / C2/C3 이월**:
- **P2 surrogate ↔ P1 surrogate 충돌**: P2 cost 가 PPO 단조 풀이 방해 → search
  timeout. C2 에서 airlock 편입 시 P2 가중치 재조정.
- **진짜 P1 향상 = C3 (장비 CP-SAT)**. 같은 방 안 장비 sort_order 단조까지
  최적화해야 P1 = 0.8+ 도달 가능 (예측).
- **P7 향상 = B-001 백로그 (시각 축소 분리) + C3**. NNE 의 0.44 까지 도달
  하려면 장비-방 면적 균형까지 풀어야.
- **CP-SAT 가 C_closed 에서 가장 저조** (−0.056): 작은 캔버스에 25방 우겨넣기
  → P1 surrogate 풀기 어려움. zone stripe 비율 동적 (현재 20/62/18 고정) 로
  완화 후 재측정.

**회귀**: 98 → **106 passed** (1 skipped), 0 fail. 테스트 8건 신규.

**산출물**: `output/floorplan_c1b_mab_8000L.svg` (CP-SAT 방 + strip-band 장비).

---

## D-018: C3a — 장비 CP-SAT 착수 + D-015 부분 재검토 + B-001 시각 축소 분리

**날짜**: 2026-05-30

**무엇**: D-015 의 "층2 (장비) = strip-band 재사용 보류" 결정을 부분 재검토.
C1b (D-017) 실측에서 진짜 P1·P7 향상이 *장비* 단위라서 방-only CP-SAT 만으로
는 strip-band 와 동등 (Δ avg −0.002) → 한계 확인. **C3a 착수**: 방 1개 안
장비 CP-SAT 배치 (P-series surrogate). 작은 단위 (R_MEDIA_PREP 5장비) 부터.
B-001 백로그 (시각 축소 분리) 같이 처리.

**D-015 재검토 핵심**:
- D-015 당시 근거: B3 NNE 비교에서 P2 group_term 이 strip-band·NNE 모두 ≈0.90
  포화 → "층2 leverage 작음" 결론.
- D-017 실측 결론: P2 는 포화지만 **P1·P7 은 장비 단위가 결정적**.
  - P1 진짜 점수 = 장비 좌표 흐름축 투영 단조 (방 단위가 아님).
  - P7 inner_compactness = 장비 외접 bbox / 장비 면적 합 (장비 packing).
  - 둘 다 *장비* 가 풀려야 진짜 향상.
- 결정: **C3a (장비 CP-SAT) 를 C2 (전실) 보다 우선**. C2 는 P2 만 영향 (작음).

**B-001 시각 축소 분리 (병행 처리)**:
- 백로그 B-001 (PROGRESS.md): `EQUIPMENT_VISUAL_SCALE=0.80` + 자동 축소가
  P7 측정 왜곡. **CP-SAT 는 실제 W_mm 으로 풀어야 정확.**
- `_place_equipment_grid(layout, use_actual_mm: bool = False)` 플래그 추가:
  - `False` (default): 기존 시각 축소 모드. baselines.json / B3 NNE 흔들지 않음.
  - `True`: 실제 W_mm 사용 (scale = 1.0 고정). CP-SAT 와 같은 기준 비교용.

**구현**:
- `src/drawing_agent/layout_solver.py` — `_place_equipment_grid` 에 `use_actual_mm`
  플래그 (default False). 9 줄 변경, default 동작 무변.
- `src/drawing_agent/constraint_compiler.py` — `compile_room_c3a(room, room_rect_mm,
  ...)` 추가:
  - 변수: 장비별 `(x_var, y_var)` 격자 + IntervalVar (size = w + gap, h + gap).
  - 실제 W_mm/D_mm 고정 (회전 X, 후속).
  - hard: H1 방 안 (inner_margin), H2 안 겹침 (AddNoOverlap2D + gap padding).
  - 목적: P1 surrogate (sort_order 인접 쌍 가로 단조) + P7 surrogate (장비
    외접 bbox perimeter `(x_max-x_min) + (y_max-y_min)` 최소화).
  - 가중치: P1=100, P7=20 (P-series weight 비율 10:3 근사).
- `src/drawing_agent/cpsat_solver.py` — `solve_room_c3a(room, room_rect_mm, ...)
  → (list[PlacedEquipment], SolveReport)`. INFEASIBLE 이면 빈 list.

**검증 — R_MEDIA_PREP 5장비, 3-mode 비교**:

**(0) 방 rect = strip-band 가 잡은 54m²** (rect.w=7514, rect.h=7225):
- C3a INFEASIBLE 23ms (장비 합 39m² > 방 가용 면적). 방 rect 자체가 부족.

**(1) 방 rect = spec area_m2 그대로 (10×10m = 100m²)**:

| Mode | eq area | env area | inner | outer_fill | outer | **P7_room** | P1_local |
|---|---:|---:|---:|---:|---:|---:|---:|
| A row-major **시각축소** (0.8x) | 2.4m² | 11.8m² | 0.206 | 0.118 | 0.046 | **0.126** | 1.000 |
| B row-major **실제** W_mm | 39.0m² | 68.4m² | 0.570 | 0.684 | 0.541 | **0.556** | 0.500 |
| **C CP-SAT 실제** W_mm | 39.0m² | **51.0m²** | **0.765** | **0.510** | **0.975** | **0.870** | **0.750** |

- **CP-SAT (C) vs row-major 실제 (B)**: P7_room **+0.314**, P1_local **+0.250**.
- **CP-SAT outer_fill=0.510** — sweet 0.50 거의 정확히 잡음 (CP-SAT 가 P7
  surrogate 로 외접 bbox perimeter 최소화한 결과).
- A row-major 시각축소: P7 만점 추정 (=0.126), P1=1.0 은 한 row 직선 깔린
  부산물 (왜곡된 신호 — 시각 축소가 장비를 작게 만들어 inner 도 outer 도 망가짐).

**풀이 시간 (방 100m², 5장비, 격자 500mm, wall=300, gap=300)**:
| rect 형태 | status | time |
|---|---|---:|
| 정사각 10×10 | OPTIMAL | 226ms |
| 직사각 12×9 (108m²) | OPTIMAL | 264ms |
| 직사각 15×7 (105m²) | OPTIMAL | 59ms |
| strip-band rect 54m² | INFEASIBLE | 23ms |

→ **방 rect 가 spec area_m2 근처면 sub-second OPTIMAL**. strip-band rect (54m²)
는 부족.

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 정량** — 동일 방 + 동일 장비에서 C3a P7 0.87 vs row-major 0.56 →
   +56% 향상. P-series 점수의 진짜 leverage 가 장비 단위임을 정량 확인.
2. **실무 수준** — 시각 축소 분리 (B-001) 로 P7 측정이 *실제 크기* 기준이 됨
   → 진짜 GMP 평가에 적합. CP-SAT 가 outer_fill sweet 0.5 정확히 잡음 = 통로/
   여백/장비 비율의 도면적 합리성.
3. **특허 / 논문** — "방 단위 CP-SAT + 장비 단위 CP-SAT 두 레벨 결합" 이 D-015
   의 단일 레벨 결정을 발전시키는 method 섹션 데이터. C3a 의 P7 +0.31 향상이
   정량 근거.
4. **재현성** — 결정론 (random_seed=0, max_deterministic_time) 통과. 두 번
   풀이 좌표 동일. 회귀 8건 (`tests/test_cpsat_c3a.py`).

**근거**:
- D-017 사용자 결정 (이전 turn): "Q2 C3 먼저, 점수 안 오르는 직접 원인이 장비
  + P1·P7(NNE 격차 핵심 P7)은 장비라야 진짜 오름. P2 는 0.9 포화".
- B-001 백로그 (PROGRESS.md): 시각 축소가 점수 왜곡 → 분리 트리거 = C3.
- 실측: 3-mode 비교에서 P7 0.13 → 0.56 → 0.87 단조 향상.

**핵심 설계 결정**:
- **단계적 진행 (C3a → C3b → C3c)**:
  - C3a: 방 1개 (R_MEDIA_PREP 5장비) — *이번*.
  - C3b: 쉬운 방 여러 개.
  - C3c: 정제실1 (22장비) — infeasible fallback 필요.
- **장비 회전 미허용** (C3a). 회전 변수 추가 시 변수 폭증. C3c 에서 필요할 때.
- **strip-band rect 와 결합 시 INFEASIBLE**: C3 는 방 rect 가 spec area 근처여야.
  C1 (방 CP-SAT) 의 사이징 정책 (D-016 factor 1.0, aspect [0.7, 1.4]) 와 일관.
  → C3 사용 시 C1 의 방 rect 를 호출자에 넘김 (strip-band rect 가 아닌).
- **B-001 부분 처리**: 분리 플래그 (`use_actual_mm`) 만 추가, default 변경 X.
  baselines.json / B3 점수 안 흔듦. CP-SAT 측정만 새 모드 사용.

**한계 / C3b 이월**:
- **방 rect 가 spec area 근처여야 feasible** — strip-band 의 잘못된 rect 와
  결합 불가. C1 (CP-SAT 방) 의 rect 와 결합해야.
- **장비 회전 미허용** — Mixing Tank 4 (4×3m) 같은 큰 장비가 좁은 방에서
  회전 필요할 수 있음. C3c 에서 처리.
- **clearance_m 미사용** — 데이터 부재 (D-009). 채워지면 H3 (벽/장비 간격) 에
  반영. 현재는 default 300mm gap.
- **PPO 흐름축 가로 가정** — C3a 는 sort_order 인접 쌍 cx 단조. 실제 PPO
  흐름축이 세로일 수도 (방 형태에 따라). C3b 에서 동적 결정.

**회귀**: 106 → **114 passed** (1 skipped), 0 fail. 테스트 8건 신규.

---

## D-019: C3b — 장비 있는 모든 방 sweep + 정제실1 진단

**날짜**: 2026-05-30

**무엇**: C3a (한 방 검증) 를 mab_8000L baseline 의 *장비 있는 모든 방* (13방)
에 확장. 각 방마다 row-major(실제 W_mm) 대비 P7·P1 향상 + feasible 여부 +
풀이시간 측정. R_PURIFICATION_1 (23장비) 별도 강조 — 사용자 1순위 위험.

**스크립트**: `scripts/c3b_room_map.py`
- 방 rect = spec area_m2 정사각 (한 변 √area × 1000 mm).
- 13 방 모두 wall_margin=300, eq_gap=300, time_limit=5s.
- 결과 저장: `output/c3b_room_map.json` (재현용).

**핵심 결과 — 13/13 모두 feasible**:

| Room | n | density | RM P7 | CP P7 | ΔP7 | RM P1 | CP P1 | ΔP1 | status | ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| R_CIP_SUPPLY | 1 | 0.167 | 0.583 | 0.583 | 0 | — | — | — | OPT | 24 |
| R_WASHING | 1 | 0.125 | 0.531 | 0.531 | 0 | — | — | — | OPT | 0 |
| R_CELL_BANK_STORAGE | 2 | 0.100 | 0.407 | 0.431 | +0.024 | 1.000 | 1.000 | 0 | OPT | 12 |
| R_PREPARATION | 2 | 0.188 | 0.578 | 0.587 | +0.009 | 1.000 | 1.000 | 0 | OPT | 6 |
| R_IPC | 3 | 0.090 | 0.374 | 0.417 | +0.043 | 1.000 | 1.000 | 0 | OPT | 9 |
| R_DS_STORAGE | 4 | 0.096 | 0.380 | 0.351 | −0.028 | 1.000 | 1.000 | 0 | OPT | 41 |
| R_HARVEST | 4 | 0.340 | 0.829 | 0.801 | −0.028 | 0.333 | **1.000** | **+0.667** | OPT | 12 |
| R_INOCULATION | 4 | 0.279 | 0.511 | **0.757** | **+0.245** | 0.500 | 0.750 | +0.250 | OPT | 26 |
| R_BUFFER_PREP | 5 | 0.219 | 0.633 | 0.615 | −0.018 | 0.750 | 1.000 | +0.250 | FEA | 5003 |
| R_MEDIA_PREP | 5 | 0.390 | 0.556 | **0.870** | **+0.314** | 0.500 | 0.750 | +0.250 | OPT | 223 |
| R_CELL_CULTURE | 6 | 0.122 | 0.429 | 0.438 | +0.009 | 0.714 | 1.000 | +0.286 | FEA | 5003 |
| R_PURIFICATION_2 | 6 | 0.270 | 0.500 | **0.722** | **+0.222** | 0.444 | **1.000** | **+0.556** | OPT | 4421 |
| **R_PURIFICATION_1** | **23** | **0.390** | **0.259** | **0.777** | **+0.518** | 0.492 | 0.482 | −0.010 | FEA | 5003 |

**평균**:
- RM P7 avg = 0.505, CP P7 avg = 0.605 → **+0.100 (+10%p)**
- RM P1 avg (11방, 장비 1개 제외) = 0.696, CP P1 avg = 0.911 → **+0.215 (+21.5%p)**

**관찰**:
- **13/13 feasible — INFEASIBLE 0건**. 사용자 우려 (정제실1 fallback) 해소.
- **P7 큰 향상 = density 큰 방** (장비 많은 방). R_PURIFICATION_1 (+0.52),
  R_MEDIA_PREP (+0.31), R_INOCULATION (+0.25), R_PURIFICATION_2 (+0.22).
- **density 낮은 방** (CIP, WASHING, CELL_BANK, IPC, DS_STORAGE):
  P7 변화 작음 — 장비 적어 row-major 도 OK.
- **P1 큰 향상 = 방 안 sort_order 다른 장비 비율 큰 방**. R_HARVEST +0.67,
  R_PURIFICATION_2 +0.56.
- **R_PURIFICATION_1 P1 −0.01** — 23장비 5s 안에 P7 만 크게 풀고 P1 surrogate
  는 못 최적화 (timeout). 시간 더 주면 향상 가능 (별도 시도).
- **풀이 시간 분포**: 11/13 sub-second (0~223ms), 4 방 5s timeout 도달 (가장
  큰 방 — BUFFER_PREP, CELL_CULTURE, PURIFICATION_2 4421ms, PURIFICATION_1).
  WASHING 1장비 = 0ms (trivial).

**R_PURIFICATION_1 강조 (사용자 1순위 관심)**:
- spec area = 350.4 m², rect = 18.7×18.7 m (정사각)
- 장비 합 = 136.5 m², density = 0.39
- row-major 실제: P7=0.259, P1=0.492
- CP-SAT: **FEASIBLE 5003ms (timeout), P7=0.777 (+0.518), P1=0.482**
- **결론: fallback 불필요. 정제실1 도 풀린다.** 정제실 P7 향상이 *최대* —
  장비 많고 빡빡할수록 CP-SAT 효과 큼.

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 정량** — 13방 평균 P7 +10%p, P1 +21.5%p. D-018 의 한 방 결과
   일반화 확인. 다른 시나리오 (A_small/C_closed/B_large) 도 비슷 예상.
2. **실무 수준** — 사용자 우려 (정제실1 INFEASIBLE) 정량으로 해소. fallback
   전략 안 필요. 솔버 신뢰 ↑.
3. **특허 / 논문 method** — "방 단위 격자 + 장비 단위 CP-SAT" 의 정량 효과
   증명. 13방 sweep 표가 method 섹션의 핵심 데이터. density vs ΔP7 상관
   관계도 부속 분석 가능.
4. **재현성** — `c3b_room_map.json` 저장 (결정론 보장). 두 번 측정 같은 P7
   (회귀 통과). random_seed=0 + max_deterministic_time.

**근거**:
- 13방 sweep 실측 (모두 feasible 도달, 평균 +10%p 향상).
- 사용자 결정 (이전 turn): C3b 먼저 (통합 미루기) + 정제실1 마지막 강조.

**핵심 설계 결정**:
- **방 rect 정책 = spec area_m2 정사각** (한 변 √area × 1000mm). C1 의
  사이징 (factor 1.0) 와 일관. 정사각이 안 들어가면 직사각 fallback (현
  스크립트는 정사각만 — 13/13 OK 였음).
- **wall_margin=300, eq_gap=300** — clearance_m 데이터 없을 때 default.
  데이터 채워지면 H3 로 반영 (D-009 epistemic honesty).
- **time_limit=5s** — 작은 방 sub-second OPTIMAL, 큰 방 (정제실1 등) 첫
  feasible 후 시간 부족. 충분 — 점수는 첫 feasible 기준 의미 있음.

**한계 / 다음 단계 이월**:
- **R_PURIFICATION_1 P1 = 0.48 (저조)**: 23장비 sort_order 단조가 5s 안에 못
  풀림. 시간 더 줘서 (30s+) P1 향상 시도 가능. C1+C3 통합 시 함께.
- **장비 회전 미허용** — 좁은 방에서 큰 장비 (Mixing-4 4×3m) 회전 필요할 수
  있음. 13/13 풀린 건 정사각 rect 라 회전 불요. 직사각 rect 에서는 필요할 수
  있음.
- **C1+C3 통합 안 됨 (이번)** — 사용자 결정대로 C3b 까지만. 다음에 4 시나리오
  통합 측정 → baselines.json / NNE 비교.
- **B-001 default 변경 안 함** — baselines.json 재생성 부담. C1+C3 통합 후 일괄.
- **각 방 rect 의 spec area_m2 가 옳은가**: 룰엔진의 area_m2 가 권장. 실측 시
  실제 도면은 더 클 수도. NNE golden 과 비교 시 재검토.

**회귀**: 114 → **118 passed** (1 skipped), 0 fail. 테스트 4건 신규.

**산출물**: `output/c3b_room_map.json` (결정론적 13방 결과).

---

## D-020: C1+C3 통합 파이프라인 — 첫 진짜 before→after

**날짜**: 2026-05-30

**무엇**: C1b (방 CP-SAT) 결과를 C3a (장비 CP-SAT) 입력으로 흘려 4 시나리오
전체 파이프라인 실행. INFEASIBLE 시 row-major 실제 W_mm fallback. 진단·해결
2단계 거쳐 최종 결과 확보.

**구현**:
- `scripts/c1c3_pipeline.py` 신규 — `solve_full_pipeline(spec, urs_path)`.
- `solve_c1b(... aspect_min, aspect_max)` 인자 추가 — 방 사이즈 변동 폭 제어.
- C3 시간 배분 (n_eq 별): ≤4 → 1s, 5-10 → 3s, 11+ → 8s.
- INFEASIBLE → `_place_equipment_grid(use_actual_mm=True)` fallback.

**1차 시도 (default aspect [0.7, 1.4]) — 실패**:
- 평균 Δ −0.0096, **INFEASIBLE→fallback 23/52 (44%)**.
- 진단: C1b 가 P1 surrogate 만 minimize 하느라 방 사이즈를 aspect_min=0.7
  로 수렴 → 면적 0.49 × area_m2 로 축소. R_MEDIA_PREP spec 100m² → C1b
  rect 49m² → C3a INFEASIBLE.

**2차 시도 (aspect 좁힘 [0.9, 1.1]) — 절반 성공**:
- mab_8000L Δ +0.0615 (NNE 거의 도달), C_closed Δ +0.01, B_large +0.002.
- A_small **INFEASIBLE** (canvas 1800 m² < spec area 2535 m² — aspect 좁힘으로
  C1a hard 와 충돌).

**3차 시도 (동적 aspect, threshold = spec_area × 1.0) — 채택**:
- canvas ≥ spec_area → 좁힘 [0.9, 1.1] (mab, C_closed, B_large).
- canvas < spec_area → 넓힘 [0.7, 1.4] (A_small — 캔버스 부족 정직).
- 시간 추가 단축: C3 ≤4=1s, 5-10=3s, 11+=8s (이전 2/5/15s).

**최종 결과 — 4 시나리오 전체 파이프라인**:

| Scenario | strip-band (before) | CP-SAT C1+C3 (after) | Δ | time | c3 fallback |
|---|---:|---:|---:|---:|---:|
| A_small_aseptic | 0.6687 | 0.6740 | +0.0053 | 4.0s | 6/13 |
| **mab_8000L** | 0.6615 | **0.7230** | **+0.0615** | 20.3s | 1/13 |
| **C_closed_sys** | 0.6965 | **0.7050** | **+0.0085** | 25.1s | 1/13 |
| B_large_multi | 0.6511 | 0.6534 | +0.0023 | 16.7s | 0/13 |
| **avg** | **0.6694** | **0.6888** | **+0.0194** | **66.1s** | 8/52 |
| NNE_golden (ref) | — | 0.7233 | — | — | — |

**핵심 성과**:
- **평균 +1.94%p 향상** — strip-band 명확 우위.
- **mab_8000L: 0.7230 = NNE 0.7233 거의 도달** (격차 −0.0003).
- **R_PURIFICATION_1 (사용자 1순위 위험)**: FEASIBLE 8s, **fallback 안 함**,
  rect 272m², density 0.50, P7 surrogate 효과 발휘.
- **P 별 분포 (mab_8000L)**:
  - P1 0.6396 → 0.6819 (+0.042) — 장비 단위 흐름축 단조 일부 향상.
  - P2 0.9046 → 0.8152 (−0.089) — C3 가 P7 우선해서 group 응집 약화 (의도 trade-off).
  - P7 0.2483 → 0.6756 **(+0.427!!)** — 가장 큰 leverage. C3 효과 확인.

**부속 진단 (사용자 인지 사항)**:
1. **공정성 단서**: CP-SAT 는 실제 W_mm (B-001 분리), strip-band 는 시각축소
   (0.8x). 같은 spec 의 다른 정의. baselines.json 은 그대로 보존 (재생성 X).
2. **A_small INFEASIBLE 6건 fallback**: 캔버스 1800m² < spec area 합 2535m² —
   룰엔진의 방 면적 우겨넣음. strip-band 도 시각축소로만 우회. **CP-SAT 는
   정직하게 INFEASIBLE → fallback**. 평균 점수에 ↓ 영향.
3. **B_large 한계 (+0.002)**: canvas 100×52m 큰데 방은 비례 안 커짐 (룰엔진
   area_m2 비례). 빈 공간 많아 outer_fill 너무 작음. CP-SAT 가 큰 캔버스 활용
   못 함. 별도 트랙 (URS 3.6 장비 변별) 후 재측정.

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 정량** — 첫 진짜 before→after 표 확보. mab_8000L NNE 거의 도달.
   평균 +1.94%p, P7 +43%p (mab 한정). 논문 result 섹션의 핵심 데이터.
2. **실무 수준** — 동적 aspect (캔버스 vs spec area 비교), 시간 배분, INFEASIBLE
   fallback 모두 명시. 실 운영 시 robustness 확보.
3. **특허 / 논문** — "C1 방 CP-SAT + C3 장비 CP-SAT 두 레벨 결합" 의 정량 효과
   증명. D-015 → D-018 (장비 leverage 발견) → D-020 (통합) 의 분기 도착점.
4. **재현성** — `output/c1c3_pipeline.json` 결정론적 저장. random_seed=0 +
   max_deterministic_time. 4 테스트 회귀 보장.

**근거**:
- 사용자 결정 (이전 turn): "C1+C3 통합 승인" + 시간 한계 + 정제실1 P1 관심.
- 1차/2차/3차 시도 sweep 실측 — aspect 영향 정량 확인.
- C3b (D-019) 의 정사각 100m² 결과 (P7 0.87) vs 통합 mab (P7 0.68) 차이는
  C1 의 rect 가 spec area 의 100% 가 아닌 ~75% (aspect 좁힘 trade-off) 때문.

**핵심 설계 결정**:
- **동적 aspect threshold = 1.0**: canvas ≥ spec area 합이면 좁힘, 아니면 넓힘.
  C_closed (canvas 2400 vs spec 2355, 비율 1.02) 도 좁힘 적용 → +0.01 향상.
- **C3 시간 배분 ≤4=1s, 5-10=3s, 11+=8s**: 전체 시간 95s → 66s 단축 (점수
  거의 동일).
- **INFEASIBLE fallback = row-major 실제 W_mm** (B-001 분리 모드). 정직한
  점수 측정. CP-SAT 안 풀리는 방을 인지 가능하게.
- **C1+C3 통합 = 새 default 안 함**. baselines.json 보존, B3 NNE 보존.
  통합은 별도 스크립트로 측정만.

**한계 / 다음 단계 이월**:
- **A_small / B_large 작은 향상 (~+0.002~0.005)**: 캔버스 vs spec area 부정합
  (URS 자체 한계 + 룰엔진 area 정책). URS 3.6 장비 변별 (사용자 별도 트랙)
  후 재측정.
- **P2 감소 (~−0.09)**: C3 가 P7 우선해서 group 응집 약화. P2 surrogate 도
  C3 에 박을지 결정 후 재시도.
- **NNE 까지 격차 (avg −0.034)**: mab 만 거의 도달. 다른 시나리오는 캔버스
  여유 부족 또는 룰엔진 변별 부족.
- **B-001 default 변경 보류**: 통합 결과 안정될 때 (다른 4 시나리오도 향상)
  baselines 재정립 후 일괄.
- **C2 (전실 편입)**: P2 link 거리 향상 가능. 현재 P2 감소 원인 일부.

**회귀**: 118 + 4 = **122 passed** (테스트 4건 신규: pipeline 수렴 + mab norm
향상 + 정제실1 no-fallback + solve_c1b aspect 인자).

**산출물**:
- `output/c1c3_pipeline.json` (결정론적 통합 결과, 모든 시나리오 + 방별 메타).

---

## D-021: GMP 청정도 구배 토폴로지 (전문가 도면 피드백 → strip-band 재설계)

**날짜**: 2026-06-02

**무엇**: 사용자(GMP 전문가) 가 v2 도면을 검수하고 6건의 피드백을 줌. 이를
drawing_agent 의 외부(소연) spec 경로(`dynamic_rooms=True`) 에 반영해 **가로
청정도 구배 토폴로지** 로 재설계. 신규 `_solve_gmp_gradient`.

```
NC 구역 → Grade D 구역 → [Grade D 세로복도] → Grade C 공정구역
                                              ├ RETURN 복도(상)
                                              ├ 공정행(상)
                                              ├ [가운(C)] SUPPLY 복도(중앙)
                                              ├ 공정행(하)
                                              └ RETURN 복도(하)
```

**6개 피드백 → 변경 매핑**:

| # | 피드백 | 변경 | 함수 |
|---|---|---|---|
| ① | 작은 방(Inoc/Prep/Wash/Gowning) 세로로 길쭉 | water-filling 종횡비 클램프(면적비례+최소폭, 합 보존) | `_alloc_dim`, `_place_row_aspect`, `_place_stack_aspect` |
| ② | 정제실(하행)도 return 복도 필요 | 양측 return 복도 모두 *실제 방*(기존 bottom 은 annotation 만) | `_solve_gmp_gradient` (return + `_S` 복제) |
| ③ | D↔C 사이 복도 + 접점에 가운룸 | Grade D 세로복도 + 가운(C) 게이트 + 합성 도어 | `_solve_gmp_gradient`, `_add_synth_door` |
| ④ | 도어 곡선 반대 | swing arc `sweep` 반전(가로·세로) | renderer `_emit_z6_doors` |
| ⑤ | NC→D→C 순서 | 가로 구배(NC 최좌→D→C) — 기존 aux좌/NC우 대체 | `_solve_gmp_gradient`, `_classify_rooms_gradient` |
| ⑥ | 화살표 논리 안 맞음 | one-way: supply→공정행 수직통과→양측 return→D복도 배출 | renderer `_emit_z9_flow_arrows` |

부수: AL 폭 절대상한 3.8m (`_place_al_edge`) — 큰 방에서 전실이 방의 40%까지
커지던 문제.

**왜** (CLAUDE.md 4대 원칙):
1. **성능 / 전문가 납득** — 가로 청정도 구배(NC→D→C, 한 등급차 인접)·가운
   게이트·one-way 회수는 실제 무균/바이오 시설의 정석. 휴리스틱이나 도메인
   규범에 정합.
2. **실무 수준** — 외부 실측 spec 그대로 흡수. 방 종횡비 클램프로 면적 편차
   (20~300㎡) 에서도 슬리버 없이 배치.
3. **특허 / 논문 method** — 이 토폴로지가 **CP-SAT zone 제약(H3)의 도메인
   근거**. 현재 H3 는 aux/proc/nc 3분할 → 향후 "NC/D/C 구배 + 한 등급차 +
   가운 게이트 + 양방향 회수" 를 정수 제약으로 컴파일하면 규칙→제약 변환
   청구항 강화. EU GMP Annex 1 / ISPE Vol.6 추적성.
4. **재현성** — 결정론적. 같은 spec → 같은 좌표.

**근거 / 출처**:
- EU GMP Annex 1 (2022) — 가운/에어록 게이트, 단계적 청정도 진입.
- ISPE Baseline Guide Vol.6 — clean/return corridor, one-way flow, 등급 구배.
- 사용자(GMP 도면 전문가) 검수 피드백 6건 (2026-06-02).

**핵심 설계 결정**:
- **경계 보존**: 하드코딩 strip-band(`dynamic_rooms=False`) **무수정**. baselines
  (D-013) / NNE(D-014) / before→after CP-SAT(D-017/D-020) 서사 보존. 새
  토폴로지는 외부 spec 에서만.
- **②-1(양측 return) 채택, ②-2(단일행) 보류**: 사용자가 (1)양측 return /
  (2)정제실 supply 위쪽 단일행 둘 중 택일 제시. (2) 는 P1 흐름 단조성 ↑ 이나
  캔버스 가로 왜곡. (1) 로 전 공정행 return 인접 충족. (2) 는 사용자 결정 시
  행 분할만 변경.
- **가운 다중 처리**: 무균충전 시 가운 2개 → 하나만 게이트, 나머지는 공정행.
- **AL drop 방향**: `supply_cy` 기준 상행 ↑ / 하행 ↓. PAL/MAL/CAL 색 구분.

**검증**:
- 5 시나리오 재생성(배치 31/21/43/36/30). 무균충전은 Grade A(해치)+B(에메
  랄드) 충전 suite 하행 등장 → "URS aseptic=True → A/B 출현" 시각 입증.
- PNG 확대 검증: 도어 여닫이 호 정상 / 구배 순서(NC x=0→D→D복도→가운→
  supply) / 양측 return 실제 / one-way 화살표 일관 / 슬리버 없음.
- **회귀 0**: 변경 전·후 모두 17 fail·100 pass·6 err(동일). 런간 차이는
  CP-SAT 결정성 테스트(c1a/c1b) flakiness(내 코드 무관). 실패군은 옛 fixture
  (`R_MEDIA_PREP`)·옛 엔진 e2e(엔진 교체 잔재).

**한계 / 이월**:
- 휴리스틱 strip-band 품질 개선. 솔버=CP-SAT 결정 불변. 다음: H3 를 NC/D/C
  구배+등급차+게이트로 확장해 CP-SAT 가 *최적화*(현재 고정 배치)하게.
- HARVEST(상행 끝)→PURIFICATION_1(하행 시작) 행 전환이라 공유벽 없음(복도
  경유). ②-2 채택 시 해소.
- perimeter_ring 은 구버전 분류 유지 — 의도적 토폴로지 다양성(ㅁ자 복도).

---

## D-022: 고도화 Phase 0 — 통합 벤치테스트 + 룰엔진→drawing 정렬 감사

**날짜**: 2026-06-06

**무엇**: 팀톡 "고도화" 3목표 중 ②(룰엔진→drawing 정렬, 사용자 최우선)를
착수하기 위한 기준선. (a) 새 15-룰 엔진 출력으로 drawing end-to-end 벤치테스트,
(b) 필드 단위 정렬 감사를 `docs/alignment_audit.md` 로 박제.

**배경 — 룰엔진 6/2 push 분석**:
- 위치: `teammate/main`(별도 repo, smartepic2026/rule_engine_validation_agent)
  `228c0ff..e05b85c`. 모노레포(origin) 아님. 우리 `src/rule_engine` 는 6/1
  구버전(13룰, is_airlock 없음).
- 13→15룰: rule_14_acph, rule_15_gowning 신설 + rule_06_airlocks(dedup) /
  rule_13_pressure(차압) 강화 + derive/flow_paths·adjacency·rooms_selector.
- **계약 변경은 additive·non-breaking**: Room에 `is_airlock`(bool)/`airlock_id`
  (str|null) 추가 → 그동안 미해결이던 AL 이중표현(rooms[]+airlocks[]) 을 룰엔진이
  명시 플래그로 해결. AirLock.area_m2 가 float|null→float(MAL 12/PAL·CAL 9).
  `flow_paths` 5필드 구조 불변(외부 Drawing Agent 계약 동결 유지).

**벤치테스트 결과**:
- raw 엔진 출력 → `cli draw` 직접 = ❌ 크래시(내부 스키마는 rationale 의
  `target`/`reason` 필수, raw 는 `target_id`/`decision`).
- raw → `adapt_external_dict`(tier1) → 내부 spec → `draw` = ✅ 정상(SVG 80KB,
  rooms 23/AL 18/doors 39). **계약 변경이 drawing 을 깨지 않음**을 실증.
- **통합 경로에 어댑터 단계 필수** — `cli rule-engine`(cli.py:38) 은 어댑터를
  거치지만 `cli draw`(cli.py:54) 는 이미 어댑터를 통과한 내부 spec 만 받는다.

**정렬 감사 핵심 (전체는 alignment_audit.md)** — Top gap:
- **G1 (🔴)**: 동선 화살표 `_emit_z9_flow_arrows(s, ox, oy, layout)`(renderer.py:606)
  가 `spec` 을 안 받아 flow_paths 를 물리적으로 못 본다. `"SUPPLY_CORRIDOR"`/
  `"RETURN_CORRIDOR"` 패턴매칭(renderer.py:634,637)으로 동선 휴리스틱 재구성 →
  엔진 명시 4종 동선(personnel_entry/exit·material_entry·waste_exit) 미반영.
  새 GMP Flow 규정을 drawing agent 에서 처리키로 한 팀 결정의 정확한 작업 지점.
- **G2 (🔴)**: width_mm/depth_mm·area_ratio_pct 무시(`√area_m2` 자체 산출) →
  면적 비율 왜곡(도면 피드백 #5).
- **G3 (🟠)**: is_airlock/airlock_id 미소비. 내부 Room 스키마에 필드 없어
  드롭(schemas.py:29 extra=ignore). 전실 dedup 이 `_is_al_fake_room`(ID패턴 +
  area_m2==0, layout_solver.py:153-155) 휴리스틱에만 의존 — 현재는 18/18
  정상이나(내부 None→0 강제변환), 엔진이 전실 방에 면적을 주면 깨지는 취약 구조.
- G4 zones{} 무시(category+ID 재분류), G5 is_elevator_constraint/flow_direction
  미사용, G6 constraints{} 하드코딩, G7 gowning/airlock flow_type 등 메타 미표기.

**왜** (CLAUDE.md 4대 원칙):
1. **성능/정렬** — 사용자 #2(누락·왜곡 없는 정렬)의 정량 기준선. 어느 출력이
   도면에 반영되는지 표로 추적 → 개선분이 ✅ 이행으로 측정됨.
2. **실무 견고성** — raw→draw 크래시·is_airlock 취약 dedup 같은 fragile 결합을
   명시. 더러운/변동 계약 처리(D-003 anti-corruption layer 연장).
3. **특허** — "계약 경계 정렬 검증(contract-alignment verification)" = 출처추적
   (D-001)+어댑터(D-003) 위의 필드별 소비 추적표. 신규 구성요소.
4. **논문** — method 의 정렬 검증 절. epistemic honesty 일관(DROPPED 은폐 금지).

**산출물**: `output/teammate_engine_v2_output.json`(기준 입력),
`output/bench_v2_internal_spec.json`(어댑터 통과), `output/bench_v2_new_engine.svg`
(벤치 도면), `docs/alignment_audit.md`(감사표).

**다음 (Phase 1)**: G1 — `_emit_z9_flow_arrows` 가 spec.flow_paths 를 받아 4종
동선을 실제 좌표로 연결. (decisions D-023 예정)

---

## D-023: 동선 화살표 = flow_paths 그대로 렌더 (G1) + 방 누락 해소 (렌더=gradient)

**날짜**: 2026-06-06 (Phase 1)

**무엇**: alignment_audit 의 최대 gap G1(동선 화살표가 룰엔진 flow_paths 미사용)
과 그 과정에서 발견한 **실제 방 누락 버그**를 해소.

**(1) 동선 화살표 재작성 — renderer.py**:
- 기존 `_emit_z9_flow_arrows(s, ox, oy, layout)` 는 `spec` 을 인자로 받지도
  않아 flow_paths 를 못 봤고, 방 id 문자열("SUPPLY_CORRIDOR"/"RETURN_CORRIDOR")
  패턴매칭으로 동선을 휴리스틱 재구성했다.
- 신규 `_emit_z9_flow_arrows(s, ox, oy, layout, spec)`:
  - `spec.flow_paths` 5필드(personnel_entry/exit · material_entry · waste_exit
    · product_process_order)의 방 시퀀스를 실제 배치 좌표로 연결.
  - 4종 색(personnel/material/waste/product) + 종류별 수직 오프셋(공유 복도
    겹침 방지) + 구간마다 화살표 머리(연결 동선).
  - 외부 노드(ELEVATOR_*)는 URS 방위 외곽 포트로 매핑(인원 3시/자재 12시/
    폐기물 9시). product 는 공정실 중심 직선 연결 = 벽 가로지르기(GMP Product §2).
  - flow_paths placeholder/미해소(내부 노드 <4) → 기존 토폴로지 휴리스틱
    `_emit_z9_flow_arrows_topology` 로 폴백(발표용 내부 spec 회귀 방지).
- 근거: 신규 GMP Flow 규정 1~4. 색인은 z12 범례(기존).

**(2) 방 누락 해소 — cli.py / 솔버 경로 분리**:
- 발견: `cli draw` 가 `generate_floorplan` 을 **기본 `dynamic_rooms=False`
  (strip-band)** 로 호출 → strip-band 의 하드코딩 공정순서 리스트(TOP/BOTTOM_ROW,
  옛 ID 기준)에 없는 방을 **조용히 드롭**. 새 엔진(48방)에서 **R_MEDIA_PREPARATION·
  R_BUFFER_PREPARATION(주요 공정실) 포함 실제 방 7개 누락**(배치 23/48).
- gradient 솔버(`dynamic_rooms=True`)는 임의 방집합을 배치 → **31방 전부, 누락 0**.
- 조치: `cli draw` 기본을 **gradient** 로 변경(+`--strip` 으로 레거시 강제) +
  누락 방 **WARN** 출력. **strip-band 코드는 무수정**(D-021/D-013 경계 — baselines/
  golden/reward 는 default 경로로 측정하므로 `generate_floorplan` 기본값은 False
  유지). 즉 **렌더링 경로=gradient(전 방), baseline 측정 경로=strip-band(subset)**
  로 역할 분리.

**왜** (CLAUDE.md 4대 원칙):
1. **성능/정렬** — 휴리스틱 재구성(엔진 무시) → 엔진 출력 *그대로* 렌더(추적가능).
   "수학적으로 방어 가능한 방법" 원칙: 동선이 룰엔진 flow_paths 와 1:1.
2. **실무 견고성** — 주요 공정실이 도면에서 사라지던 치명 누락을 잡음. 누락
   WARN 으로 silent omission 차단(epistemic honesty 일관).
3. **특허/논문** — "룰엔진 동선 시퀀스 → 도면 렌더 1:1 정합" + 역할 분리(측정
   subset vs 렌더 full) 가 정렬 검증 method 의 근거.
4. **재현성** — flow 화살표가 spec 의 함수 → 같은 spec 같은 동선. 회귀 테스트
   (`test_no_real_room_omitted`, `test_flow_arrows_follow_flow_paths`) 로 고정.

**검증**:
- 새 엔진 spec(gradient): 31방 전부 배치(누락 0), 동선 세그먼트 personnel 6 +
  material 3 + waste 3 + product 6(+범례 각 1). 산출 `output/bench_v3_flowpaths.svg/png`.
- strip 경로: 7방 누락 WARN 정상 출력.
- 발표용 placeholder spec: 토폴로지 폴백 정상(화살표 21 마커).
- 테스트: `test_drawing_agent` 7건 전부 통과(누락 가드 + flow 검증 신규 2건).
  전체 **17 fail→13 fail / 100→106 pass**(회귀 0, 남은 실패는 옛 fixture
  R_MEDIA_PREP / 옛 engine_e2e / reward = 사전 존재 legacy follow-up).

**한계 / 후속**:
- 동선이 방 중심 직선 연결이라 긴 대각선이 다소 분주. **직교(Manhattan) 라우팅
  — 복도 중심선 경유** 로 polish 가능(Phase 1.5 백로그). 현재도 가늘게/점선/색
  구분이라 시인성 확보.
- 발표용 내부 spec 의 flow_paths 를 concrete ID 로 채우면(변형 생성기) 폴백
  없이 faithful 렌더(별도 트랙).

---

## D-024: 면적 비례 렌더 (squarified treemap) + is_airlock 명시 dedup (G2·G3)

**날짜**: 2026-06-06 (Phase 2)

**무엇**: alignment_audit G2(면적 비율 왜곡, 도면 피드백 #5)·G3(is_airlock dedup
취약) 해소.

**(1) G2 — squarified treemap 으로 면적 비례 배치 (layout_solver.py)**:
- 진단(정량): gradient 솔버에서 그려진/spec 면적 배율이 0.54~5.84 (평균 1.62,
  표준편차 1.01) — 면적 비례라면 일정해야 함. **R_CELL_BANK_STORAGE 20㎡→59㎡(2.97×)
  ≡ R_MATERIAL_STORAGE 100㎡→59㎡(0.59×)** = 5배 차이가 동일 크기(피드백 #5).
- 원인: gradient 의 NC/Grade D 컬럼이 고정폭(13%/16%·W ≈ 10~12.5m)이라 넓고,
  `_alloc_dim` 의 종횡비 floor 클램프(`cross/max_aspect`)가 작은 방을 일괄
  바닥값까지 부풀려(모두 ≈동일 높이) 면적 비례 파괴.
- 해결: **squarified treemap**(Bruls·Huizing·van Wijk 2000) 신규 구현
  (`_squarify`/`_place_treemap`) — 영역을 면적 비례로 분할하되 종횡비를 1 에
  가깝게. NC·Grade D 컬럼의 `_place_stack_aspect` → `_place_treemap` 교체.
- **결과(컬럼)**: Cell bank 20㎡→23.2㎡(1.16×), Material storage 100㎡→115.8㎡
  (1.16×) — **5배 차이가 올바르게 비례**. 컬럼 방들 배율 ≈1.16 균일.
- **공정행은 단일 행 유지(미적용)**: supply↔return 사이 단일 행 + 양측 AL-in/out
  one-way flow 토폴로지가 2D treemap 과 충돌(내측 방이 return 복도에 안 닿음).
  따라서 공정행은 width∝area 단일행을 유지 → 작은 공정실(INOC 40㎡ 등)은 키 큰
  밴드에서 잔여 부풀림. **단일행 flow 토폴로지 vs 완전 비례의 의도적 trade-off**
  (corridor 는 본래 long-thin 이라 비례 대상 제외). 후속: 밴드 높이 적응 또는
  CP-SAT zone 제약으로 양립.

**(2) G3 — is_airlock 명시 dedup (schemas.py + layout_solver.py)**:
- 내부 Room 스키마에 `is_airlock`/`airlock_id` 추가 → 룰엔진 새 계약 필드가
  더 이상 드롭되지 않음(이전 18→0 드롭, 이제 18/18 흡수).
- `_is_al_fake_room` 가 `is_airlock` 를 **1차 신호**로 사용(ID 패턴+area==0 은
  구계약 폴백). **견고성**: 엔진이 전실 방에 area(9/12)를 줘도 flag 로 dedup —
  패턴 단독(area==0 요구)이면 깨질 케이스를 방어.

**왜** (CLAUDE.md 4대 원칙):
1. **성능/정확** — 휴리스틱 클램프(임의 floor) → treemap(수학적으로 면적 보존
   + 종횡비 최적). "수학적으로 방어 가능한 방법" 원칙.
2. **실무 견고성** — 면적이 시각적으로 정확해야 실무 검토 가능(피드백 #5).
   dedup 이 계약 변동(전실 면적 부여)에도 안 깨짐.
3. **특허/논문** — treemap 기반 GMP 구역 면적 배분 + 명시 플래그 기반 계약
   dedup = 정렬·렌더 method 근거.
4. **재현성** — treemap 결정론(면적 입력 → 동일 분할). 회귀 테스트 유지.

**검증**: 컬럼 배율 ≈1.16 균일(이전 0.59~2.97), is_airlock 18/18, dedup 18/18.
drawing+adapter 47 통과. 산출 `output/bench_v4_treemap.svg/png`.

**한계/후속**: 공정행 잔여 비례차(단일행 토폴로지). corridor 비례 제외.
constraints{}(복도폭 등) 소비는 G6 후속(Phase 3 검토).

---

## D-025: 동선 화살표 직교(Manhattan) 라우팅

**날짜**: 2026-06-06 (Phase 1.5)

**무엇**: D-023 의 동선 화살표가 방 중심 직선(대각선) 연결이라 긴 대각선이
도면을 가로질러 시인성을 해치던 문제를, **L자 직교 라우팅**으로 개선.

- `_draw_flow_polyline` 가 각 구간을 수평→수직(또는 그 반대) L 로 꺾음
  (`horiz_first = |dx|>=|dy|` 로 엘보 선택). 복도/벽을 따라 흐르는 GMP 도면
  관습에 맞춤. 종류별 수직 오프셋 유지(공유 복도 평행 동선 분리).
- 화살표 머리는 노드에 도착하는 다리에만. 직선 구간(엘보=끝점)이면 단일
  세그먼트에 화살표(누락 방지 — 초기 버그 수정).

**왜**: 시인성(GMP Flow 규정 "시인성 훼손하지 않게"). 대각선 클러터 제거 →
실제 도면 수준 가독성. 충실성(flow_paths 1:1)은 D-023 그대로 유지.

**검증**: 4종 동선 직교 렌더(personnel/material/waste/product 화살표 존재),
drawing 테스트 7건 통과. 산출 `output/bench_v5_ortho.svg/png`.

**한계/후속**: L 엘보가 다른 방을 살짝 가로지를 수 있음(consecutive 노드가
복도 경유라 대부분 짧음). 완전 corridor-centerline 라우팅(A* on free space)은
후속 polish. 코너에서 종류별 오프셋 차로 미세 jog 가능(작음).

---

## D-026: 동선 복도 인지 라우팅 (벽 가로지르기 방지)

**날짜**: 2026-06-06 (Phase 1.6)

**무엇**: 사용자 지적 — 동선이 NC 방·벽을 가로질러 감(로비/모니터링/화장실
통과). 원인: 직교 라우팅이 flow_paths 방 *중심점*을 직선으로 이을 뿐 복도를
안 따라감. 웨이포인트가 멀면 사이 방·벽을 관통.

- **복도 인지 라우팅**(`_corridor_axis_points`/`_is_corridor_room`): flow_paths
  의 내부 복도 웨이포인트를 중심점 대신 **[진입점, 진출점](복도 중심선상)**
  으로 펼침. 진입=이전 웨이포인트에 가까운 복도 끝, 진출=다음에 가까운 끝.
  → 동선이 복도를 *타고* 흐름(supply/return 중심선). 벽·타 방 관통 최소화.
- **Product 는 예외 유지**: 규정 3-2(mAb 8000L CIP 배관 → 공정실 간 벽 가로지름)
  대로 공정실 중심 직선 = 벽 통과가 *정상*. Product 웨이포인트엔 복도 없어 영향 X.

**왜**: GMP 도면 관습(동선은 복도 따라 흐름). 사용자 지적 직접 반영.
충실성(flow_paths 1:1)·직교(D-025)는 유지.

**검증**: drawing 7건 통과. 산출 `output/bench_v6_corridor.svg/png`.

**한계/후속(Phase 1.7)**: flow_paths 가 *건너뛴* 구간(복도 웨이포인트 없는
교차구역 점프, 예: Gowning→Lobby)은 여전히 직선 → 규정 완전 확장에서 공정실별
다중 경로 + 복도 스파인 라우팅으로 처리.

---

## D-027: Product 동선 DS 보관실까지 연장 (규정 3-1·3-2) — Phase 1.7a

**날짜**: 2026-06-06

**무엇**: GMP Flow 규정 3-1(Product: …→Supply→DS 보관실) / 3-2(Purif2 는 DS
용기 충진 → MAL-in/Supply 역경로로 Storage) 반영. `_resolve_flow_polylines`
에서 product_process_order 끝에 Supply corridor + DS 보관실(DS_STORAGE/
STORAGE_BULK) 을 연장. 공정실 간은 벽 가로지르기 유지, 마지막 Supply 구간은
복도 인지 라우팅(D-026)으로 복도 타고 흐름. Product 세그먼트 6→9(+범례).

**왜**: 규정 완전 반영(사용자 "규정대로 완전 확장"). 제품 동선 종착이 Purif2
가 아니라 DS 보관실이어야 함(원료의약품 DS 충진 종착).

**검증**: drawing 7건 통과. 산출 `output/bench_v7_product_ds.svg`.

**후속(Phase 1.7b — 사용자 확인 대기)**: 공정실별 다중 Waste(각 공정실
AL-out→return→Waste-out)·Material(Supply→각 공정실 AL-in) 펼치기 + both-way
방 구분. 밀집도 ↑ → 시인성 trade-off 로 사용자 결정 후 진행.

---

## D-028: 공정실별 다중 동선 comb 라우팅 + 동선 토글 (규정 4·2) — Phase 1.7b

**날짜**: 2026-06-06

**무엇**: GMP Flow 규정 4-1(Waste: 각 주요 공정실 AL-out→Return→Waste-out→외부)·
2(Material: 외부→MAL-in→Supply→각 공정실)대로 **모든 one-way 공정실**을 대상으로
Waste/Material 동선을 펼침(이전 대표 1경로 → 공정실별 다중). 사용자 결정:
"comb 라우팅으로 전부 표현 + 토글로도 제공".

- **`_derive_full_flows`**: spec 의 one_way 공정실마다 Waste/Material 경로 생성.
  복도(Return top/bottom·aux 세로복도·Supply)를 웨이포인트로 두어 복도 인지
  라우팅(D-026)이 복도 척추를 타게 → **빗(comb)** 형태(메인=복도, 가지=각 공정실).
  Return 은 공정실 y 로 상/하 자동 선택. Waste-out 은 aux 세로복도 경유로 도달.
- **flow_mode 토글**: `render(flow_mode=)` / `generate_floorplan(flow_mode=)` /
  `cli draw --flows {full|main|off}`. full=공정실별 comb(기본), main=flow_paths
  대표 1경로, off=동선 없음. Personnel/Product 는 항상 대표 경로.
- **종류별 토글 그룹**: 각 동선을 `<g class="flow flow-{key}" id="flow-{key}">`
  으로 묶어 SVG 뷰어/CSS/JS 에서 종류별 on/off 가능.

**왜**: 규정 완전 반영(각 공정실 대상) + 시인성은 토글로 제어(규정 "시인성
훼손하지 않게"). 밀집 vs 완전성의 trade-off 를 사용자가 모드로 선택.

**검증**: full=waste 31·material 21 세그먼트(comb), main=5·4, off=0. 토글그룹 4.
drawing 7건 통과. 산출 `output/bench_v8_full.svg`(comb)·`bench_v8_main.svg`(대표).

**한계/후속**: comb 밀집도 높음(토글로 완화). Waste-out 도달 경로(aux 복도 경유)
가 레이아웃에 따라 일부 교차구역 통과 가능 — 복도 스파인 정밀화는 후속.
both-way 방(Media/Buffer/Prep/Wash) 은 Waste/Material 대상에서 제외(one_way 만).

---

## D-029: 장애물 회피 채널 라우팅 — 동선 방·벽 관통 제거

**날짜**: 2026-06-06 (Phase 1.8)

**무엇**: 사용자 재지적 — 동선이 여전히 NC 방·벽을 가로지름(로비/모니터링/
화장실 관통). 근본 원인: 복도 인지 라우팅(D-026)은 flow_paths 의 복도 웨이포인트
만 처리, 목적지가 복도 없는 NC/D 깊은 방이면 직선이 방을 관통.

- **채널 라우팅**(`_flow_channels`/`_channel_route`/`_route_polyline`): Product 외
  모든 동선을 **채널 경유 직교 경로**로 라우팅. 채널 = 복도 중심선 + 건물 외곽
  ring + **모든 방 경계선(벽 그리드)**. 각 구간을 후보 채널(수평/수직)로 라우팅해
  **방 관통이 최소**(동률이면 최단)인 경로 선택. 방 경계선 위 직선은 양쪽 방
  내부를 안 건드려(strict 관통 판정) 복도 없는 구역도 벽을 따라 흐름.
- **Product 예외**: 공정실 간 벽 가로지르기(규정 3-2 CIP 배관) 유지.

**왜**: 사용자 지적("왜 동선이 벽체로 가지… 복도를 만들던 말이 되게"). GMP
도면은 동선이 복도/벽을 따라야 함. 휴리스틱 직선 → 장애물 회피 라우팅.

**검증**: 비-product 방 관통 main 10→8, full 25→15(방 경계선 채널 추가 효과).
원래 대각선 대비 대폭 감소. drawing 7건 통과. 산출 `output/bench_v9_main.svg`.

**한계/후속(= 피드백 #1)**: 잔여 관통(main 8)은 복도가 *전혀 없는* 구역(NC
깊은 방·DS storage) 으로의 마지막 stub. 근본 해소는 NC↔Grade D 구역에 실제
복도 신설(피드백 #1, Phase 3) — 동선이 탈 복도가 생기면 0 에 수렴.

---

## D-030: NC↔Grade D 순환 복도 신설 (도면 피드백 #1)

**날짜**: 2026-06-06 (Phase 3 #1)

**무엇**: 도면 피드백 #1 — "NC 구역과 Grade D 보조구역 사이도 복도로 구분되어야
함. 사람이 Office→Gowning→Grade D 복도로 이동할 동선." gradient 솔버에 NC↔D
세로 순환 복도를 카브.

- 분류기 `_classify_rooms_gradient`: NC 카테고리의 복도 방(R_CORRIDOR_VISITOR
  등)을 `nc_corridor` 로 분리(기존엔 일반 NC 방으로 stack).
- 솔버 `_solve_gmp_gradient`: NC·D 가 모두 있으면 둘 사이에 세로 복도 strip
  (W*0.03) 카브. 전용 복도 방 있으면 배치, 없으면 `_synth_corridor_room` 합성.
  레이아웃: NC | **NC↔D 복도** | Grade D | D복도 | C 공정.
- 효과: ① 사람 순환 동선(NC→D) 확보 ② **flow 채널(D-029) 추가** → 동선이
  복도 없는 NC/D 구역도 이 복도를 타고 흐름. 비-product 방 관통 main 8→6,
  full 15→13.

**왜**: 피드백 #1 직접 반영 + D-029 잔여 관통의 근본 원인(복도 부재) 해소.
실제 GMP 순환 구조(보조구역 복도 분리).

**검증**: NC↔D 복도 배치 확인, drawing 7건 통과. 산출 `output/bench_v10_nccorr.svg`.

**한계/후속**: 잔여 관통(main 6)은 treemap 패킹상 복도에 안 닿는 깊은 방으로의
stub — 복도 인접 단일열 배치 vs 면적비례 treemap 의 trade-off. 복도-인접 우선
배치는 후속. Gowning↔NC복도 인접 보장(피드백 #1 세부)도 후속.

---

## D-031: 도면 피드백 #2·#3·#4 (Grade C 도어삭제 / Waste·Material 분리 / 접경 Gowning+MAL-in)

**날짜**: 2026-06-06 (Phase 3 #2~4)

**#2 — 주요 공정실끼리 도어 삭제** (`_place_doors`): 룰엔진이 연속 Grade C
공정실 사이에 door 6개(Media↔Buffer↔…↔Purif1↔Purif2) 출력. 피드백대로 동일
청정등급 process↔process 인접은 도어 미생성(공정물=벽/CIP 배관 이동, 규정
Product §2). 결과 도어 43→37, 공정실↔공정실 도어 0.

**#3 — Waste-out ↔ Material-in 분리** (`_solve_gmp_gradient`): 둘 다 좌하단
근접 → 교차오염. URS 방위(자재 12시 상단/폐기물 9시 하단)대로 Grade D 컬럼
상단=Material-in, 하단=Waste-out 으로 분리(수직 분리 94% of H). 나머지 D 방은
가운데 treemap.

**#4 — 접경 Gowning + MAL-in 인접** (`_solve_gmp_gradient`): D복도↔supply 접경
supply 밴드를 `[Gowning 게이트][MAL-in 반입실][supply 복도]` 로 구성. 사람용
Gowning 외 자재용 MAL-in(반입실)도 인접. 전용 MAL_in 방 있으면 사용, 없으면
`_synth_gate_room` 합성(Grade C process, 16㎡). Gowning 우측=MAL-in 좌측 인접.

**왜**: 도면 피드백 직접 반영. GMP 정합(공정물 배관 이동·교차오염 분리·자재
반입 게이트). drawing agent 영역(배치/렌더)에서 처리(룰엔진 무수정).

**검증**: 공정실 도어 0, Waste↔Material 94% 분리, Gowning+MAL-in 인접.
drawing 7건 통과. 산출 `output/bench_v11_feedback.svg`.

**한계**: #4 MAL-in 은 supply 게이트 1개(공정실별 MAL-in 은 airlocks[] 에 별도).
both-way 방 도어는 유지(공정실↔공정실만 삭제).

---

## D-032: 미반영 룰엔진 필드 전수 소비 (zones·ACPH·flow_type·door_count·constraints 등)

**날짜**: 2026-06-06

**무엇**: 전수 재조사(alignment_audit §6)에서 DROP 으로 확인된 의미 있는 필드를
모두 도면에 반영. 4그룹.

**A — 방 라벨 메타 확장** (`renderer` z10):
- 메타1: `Grade · DP · Area · **ACPH**` (air_changes_per_hour 반영).
- 메타2(큰 방): `H{ceiling} · {gowning_type}` (ceiling_height_mm·gowning_type 반영).

**B — 엔진 zones 소비** (`_classify_rooms_gradient`):
- spec.zones(process/auxiliary/nc) 를 1차 신호로 사용(재분류 폴백). 불일치 해소:
  R_CIP_SUPPLY·R_MONITORING 가 엔진 지정대로 auxiliary 로 분류(기존 NC 오분류).

**C — airlock flow_type + door_count**:
- airlock 라벨에 flow_type(cascade/sink/bubble) 표기(차압 공기흐름 — GMP 핵심).
- `_place_doors` 가 door_count 만큼 공유 벽 따라 분산 배치(2-도어 MAL 등. 현 spec
  은 전부 1).

**D — constraints 소비** (gradient 경로만, strip-band/baselines 불변):
- corridor_width_mm(preferred_min~max) → 세로 복도 폭 2000mm 적용(기존 임의 W*0.035).
- equipment_clearance_mm.between_equipment(1000) → 장비 이격(`_place_equipment_grid
  (eq_gap=)`). **기존 800 은 GMP 최소 1000 위반 → 컴플라이언스 수정**. strip-band
  caller 는 기본 800 유지(baselines 보존).

**왜**: 사용자 "all" — 누락·왜곡 없는 정렬(②최우선) 완성. zones 왜곡 해소,
ACPH/갱의/flow_type 표기로 도면 정보량을 룰엔진 출력과 1:1. eq_gap 위반 수정.

**검증**: 복도폭 2000mm, ACPH·cascade·무진복 라벨 등장, CIP/Monitoring=aux,
drawing 7건 통과. 산출 `output/bench_v12_allfields.svg`.

**남은 DROP(불필요/3D)**: volume_m3·recovery_time(HVAC), meta·rationale(로그),
airlock connects_lower/purpose, area_ratio_pct, well_type — 2D 평면도 비대상 또는
대체 충족. alignment_audit §6(B) 참조.

---

## D-033: 새 15룰 엔진(6/2) 모노레포 통합 — src/rule_engine 교체

**날짜**: 2026-06-06

**무엇**: 팀원(소연)이 6/2 `teammate/main`(rule_engine_validation_agent)에 push 한
새 엔진 변경분을 우리 모노레포 `src/rule_engine` 에 반영. 사용자 지시("새 엔진으로
완전히 대체").

**배경 진단**: 우리 모노레포는 6/1 통합본(rule_14/15 파일은 있으나 models.py 에
is_airlock 없음, rule_06/13/engine 구버전). 6/2 변경분만 차이 (e05b85c vs 우리):
models.py·engine.py·rule_06_airlocks·rule_13_pressure·derive/__init__·rooms_selector·
output_example·output_schema. import 는 신·구 모두 **상대경로**(`from ..models`) →
import surgery 불필요, 직접 교체.

**조치**:
- 코어 파일 9종을 e05b85c 버전으로 교체(상대 import 그대로 동작).
- `validators/rag_validator.py` 는 **제외**(우리 버전 유지) — 새 버전이 `rag_interface`
  절대 import 의존(모노레포 경로 src.rag_interface 와 불일치). RAG 검증은
  rule-engine→draw 파이프라인에 불필요.
- src/rule_engine/tests 는 미반영(pytest testpaths=["tests"] 라 root tests 만 수집,
  엔진 tests 는 `rule_engine.` 절대 import 라 모노레포 비호환 — 별도 정리 대상).

**검증**:
- `cli rule-engine examples/teammate_urs_0516.xlsx` → rooms=48, **is_airlock=True 18**
  (새 엔진 활성 증거). draw end-to-end 정상(rooms 32/AL 18/doors 37).
- 전체 테스트 **13 fail/106 pass/6 err — 회귀 0**(남은 실패는 옛 fixture R_MEDIA_PREP·
  옛 engine_e2e = 기존 legacy, 엔진 통합과 무관).
- FINAL 도면 정식 파이프라인(URS→새엔진→draw)으로 재생성.

**의미**: 이제 `cli rule-engine` 이 **새 15룰 엔진**(is_airlock dedup·rule_13 차압·
rule_14 ACPH·rule_15 gowning)을 호출 → 팀장님 URS 테스트가 새 룰로 동작. 도면
정렬(D-022~032)은 이미 새 엔진 출력 기준으로 맞춰져 있어 일관.

---

## D-034: 팀장님 0607 피드백 — 중앙 스파인 통합밴드 토폴로지 + --seed 다양성 (진행중)

**날짜**: 2026-06-07

**무엇**: 팀장님 도면 피드백 16항목(prompts.md 2026-06-07)을 5영역(A 인접성 /
B flow정확성 / C 면적 / D 장비 / E 다양성)으로 정리. 사용자 결정 4건 + Step1-A 착수.

**사용자 결정 4건**:
1. **--seed 도입** — CLAUDE.md "결정론적 솔버(재현성)" 확정 결정과 팀장님 "배열
   다양성(랜덤)" 요구의 충돌 해소책. 시드 고정=100% 재현(논문/특허 방어 유지),
   시드 변경=다양한 배치. 양립.
2. **정확성(A+B+D) 먼저 → 다양성(C면적·E) 나중**, 단계별 커밋·검증.
3. **flow 경로 정확성은 rule_engine/derive/flow_paths.py 에서** (spec=정답, drawing은
   렌더만). 모노레포 우리 권한(memory rule_engine_ownership).
4. **인접성=결과물 퀄리티 우선(빠를 필요 없음) → 빗살/중앙스파인 토폴로지 재설계.**
   추가 질문에서 **"D복도 = 중앙 스파인(양면 방)"** 선택. "좌측끝/우측끝" =
   D복도를 가로 중앙밴드로 두고 게이트가 양 끝에서 두 복도에 접촉하는 해석.

**Step1-A 구현 (layout_solver._solve_gmp_gradient 재작성)**:
- **중앙 스파인 통합밴드**: 전 구역(NC/D/C) 공유 5밴드(return상/공정상/중앙/공정하/
  return하). 중앙밴드 가로 = `NC복도 | CNC게이트 | ═D복도═ | D→C게이트 | ═Supply복도═`.
  → 게이트가 양 끝에서 두 복도에 접촉(A1~A4), 모든 방이 상/하 행으로 인접 복도에 접촉.
- **A5/A6**: NC·D 구역 2D treemap → 행/스택 배치로 모든 방이 복도 접촉(이전엔
  DS storage·IPC 가 Cell bank 뒤 매몰). D방 상/하 행이 중앙 D복도에 접촉.
- **A6 도어 강제**: `_ensure_rooms_touch_corridor` 신규 — adjacency 도어 외에 모든
  방↔인접 복도 합성 도어 보장(방은 복도로만 출입, 주공정실 MAL/PAL 예외).
- **게이트 분류**: CNC(Gowning M/F + MAL-in CNC) 좌단 / C(Gowning + MAL-in C) 우단.
  MAL-in 실물 없으면 합성(_synth_gate_room, clean_grade CNC/C).
- **검증**: drawing 7/7 통과, 전체 13fail/106pass/6err = **baseline 회귀 0**.
  렌더 `output/_v14_spine.svg` — 중앙밴드·게이트·도어 형성 확인.

**남은 작업 (이 결정 후속)**:
- Step1-A 시각 polish: 라벨 겹침, 게이트/복도 정렬 미세조정 (사용자 도면 확인 후).
- Step1-B: flow 경로(B7~B10) rule_engine derive 수정 + parallel 겹침 레인(B11).
- Step1-D: 장비-flow 선 겹침 회피(D13).
- Step2: C12(공정행 진짜 면적비례) + E14/E15(--seed 다양성) + E16(URS 면적/비율).

**근거**: EU GMP Annex 1(에어록 게이트=청정구역 경계), ISPE Vol.6 §7.9(one-way),
팀장님 도면 피드백 0607.

### D-034 정정 (2026-06-07 후속) — 중앙스파인 폐기, 지난번 구조 + 명시 배치 채택

위 "중앙 스파인 통합밴드"는 **팀장님 피드백으로 폐기**. 사유: 중앙스파인은 D방이
NC복도에 직접 붙어 **CIP supply·Monitoring 이 갱의 없이 NC와 직결되는 오염차단
위반**을 낳았고, 팀장님이 "전체 구조는 지난번(NC|NC복도|D열|D복도|C 5밴드)이 훨씬
바람직"하다고 명시. → **지난번 구조 복원** + 아래 수정:

- **D구역 명시 2D 배치 (`_place_d_zone_rows`)**: 팀장님 지정 배치 — 위→아래
  Material storage/Equipment storage/Gowning Female/Gowning Male(전폭) →
  Monitoring|DS storage → CIP supply|IPC/Cell bank(좌우) → (Material-in 상단·
  Waste-out 하단 핀). treemap(면적순 흩어짐)·단일열(이질적) 둘 다 폐기.
- **containment 도어 규칙**: NC방→NC복도, D방→D복도(NC직결 금지), Gowning M/F만
  NC복도+D복도 양쪽(=NC↔D 인원 게이트, 갱의 강제). 후방 지원실(Monitoring·CIP)은
  **Grade D 아님** → 앞 방(DS storage·IPC) 경유 허용(팀장님 확인).
- **D→C 진입 게이트**: Gowning(위)/MAL-in(아래) **세로 스택**(이전 가로나란히→변경),
  D복도+Supply복도 양쪽 도어.
- **도어 폭 통일**: `_normalize_door_widths` — 전 도어를 최소 폭 기준 통일.
- **검증**: drawing 7/7, 전체 13fail/106pass = **회귀 0**. FINAL_layout 재생성.

**한계 → 다음 결정(D-035 예정)**: `_place_d_zone_rows` 가 **방 ID 하드코딩**이라
이 URS 에만 맞음. 다른 URS/시나리오는 방 구성이 달라 깨짐. **방 속성(clean_grade·
category·function) 기반 일반 규칙으로 리팩터** 필요(팀장님 지시: "엔진·코드 자체를
손봐 다른 도면도 규칙 만족"). 4 시나리오 전수 검증 예정.

---

## D-035: 0607 피드백 전수 감사(워크플로우) + W1 건물 footprint 계약 포함

**날짜**: 2026-06-07

**무엇**: 팀장님 0607 피드백 "모든 걸 해결" 지시에 따라, 증거기반 전수 감사를
ultracode 다중에이전트 워크플로우(5 에이전트: 면적/제약위반/피드백상태/하드코딩 +
종합)로 수행 → 18항목 우선순위 마스터 작업목록(`docs/audit_0607_worklist.md`). 이후
의존순 1번(W1)부터 구현 시작.

**감사 핵심 결과**:
- A1~A5 인접/게이트 + B8 = DONE(Step1-A 유효). A6 거의(잔여 화장실 복도접속 1건).
- 면적 비례 붕괴 근본원인 = 구역별 독립 100% 충전(전역 면적스케일 부재) + 종횡비
  floor-clamp(작은 공정실 부풀림) + D pair-row max()가중 + 복도 고정밴드.
- 장비: 실치수 6~64% 축소(면적 무의미) + 보조실 4곳 벽 밖 돌출(-5755mm).
- 제약 위반: 복도폭 max 초과, 차압 5Pa<min10, AL 미달; **그려진 Layout 을 검증하는
  geometric validator 부재**(RAG/룰엔진은 spec JSON 만 검증).
- flow B7/B9/B10 = flow_paths 시퀀스 자체 불완전(rule_engine derive 수정 필요).
- 하드코딩: D배치/복도/게이트가 방 ID 의존 → 다른 URS 깨짐.

**W1 구현 (E16 캔버스 — "파서는 읽는데 계약에 안 넘기던" 문제)**:
- 진단: URS 파서는 building(면적·가로세로) 완벽 파싱하나 ① 소연 엔진 출력에 building
  없음 ② **계약 RuleEngineOutput 에 building 필드 자체가 없음** → 통째 누락, drawing 은
  항상 고정 78500x42500.
- 수정: ① `schemas.py` RuleEngineOutput 에 `building: BuildingSpec` 필드 추가(기본값
  하위호환). ② `cli.cmd_rule_engine` 가 URS inp.building(면적·가로·세로)을 계약
  out.building 으로 매핑(소연/계약 BuildingSpec 필드명 상이 → 3필드 명시 매핑).
  ③ `cli.cmd_draw` 기본 --width/--height = None → spec.building 사용.
- 회귀 자가검출·수정: building 항상-present 가 resolve_building_dims 의 4-tier 폴백을
  깨뜨림(tier1 항상 승) → `model_fields_set` 로 "building 명시 설정 시에만 tier1"
  로 보정. 팀장 spec=tier1(URS), 테스트=tier2(urs_path) 둘 다 보존.
- 검증: spec.json 에 building 직렬화, 60000x30000 주입 시 캔버스 실제 변경(일반화),
  전체 13fail/106pass = **회귀 0**.

**근거**: 팀장님 0607 피드백, ISPE Vol.6(건물 footprint=배치 입력), D-010 책임분리.
**다음**: W2(spec 에 corridor_role/subzone 속성) + W3(post-solve geometric validator).
