# 설계 결정 로그 (논문 method / 특허 청구항 원재료)

> CLAUDE.md "설계 결정 로그" 원칙 — 중요한 설계 결정마다 무엇·왜·근거를
> 기록. 후속 논문 method 섹션과 특허 명세서의 원재료.

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
