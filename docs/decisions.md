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
