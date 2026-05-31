# 핸드오프 — Validation Agent ↔ Rule Engine 실제 연동 + L3 실행

## 이 세션에서 해야 할 일 (한 줄)

`rule_engine/validation_interface.py`의 stub validator를 실제 RAG 기반 Validation Agent로 교체하고, L3 golden file test를 한 번 실행해 회귀 없음을 확인한다.

---

## 0. 시스템 위치 (절대 경로)

- Rule Engine: `C:\Users\User\OneDrive - SKKU\claude_cowork_file\rule_engine\`
- RAG 인터페이스: `C:\Users\User\OneDrive - SKKU\claude_cowork_file\rag_interface\`
- 데모 URS: `C:\Users\User\OneDrive - SKKU\claude_cowork_file\URS_ConceptualDesign for layout_0516.xlsx`
- 작업 디렉토리(scratchpad): `C:\Users\User\AppData\Roaming\Claude\local-agent-mode-sessions\...\outputs`

샌드박스에서는 위 경로가 `/sessions/<id>/mnt/claude_cowork_file/...`로 보입니다.

## 1. 현재 시스템 상태 (시작 전 반드시 파악)

**Rule Engine v0.1 prototype + 회의 #5 보강이 완료된 상태**입니다. 다음이 이미 구현·검증됨:

- 15개 룰 + 3개 derive 모듈, 4종 동선·존·인접 그래프 산출
- `RuleEngineOutput.to_dict()` / `to_json()` 직렬화 (회의 안건 #4)
- `validation_interface.py` — JSON 파일 인터페이스 + retry 3회 cutoff + stub validator (회의 안건 #3)
- L3 Golden file test 박제 완료 (`tests/golden/real_urs_baseline.json`, 248KB)
- **단위 테스트 138/138 통과** (`python3 -m rule_engine.tests._minirunner`)
- 실제 URS 데모 동작 확인: 48 rooms / 18 airlocks / 23 adjacency / 399 rationale / flag_counts {info:4, suspected_violation:20, warning:4}

## 2. 회의 #3 결정 사항 (변경 금지)

2026-05-26 회의에서 확정된 인터페이스 스펙:

- Rule Engine → Validation: **JSON 파일**로 전달 (메모리 객체 X)
- Validation → Rule Engine: **JSON verdict 파일**로 회수
- 최대 retry **3회** cutoff. 초과 시 `escalated_to_user=True`로 사용자 알림
- Validator는 callback 함수 추상화 — Rule Engine은 Validation 내부(LLM·RAG) 모름
- URS 우선 정책: retry 중에도 `input_spec` 미변경 (변경은 사용자 검토 후 새 라운드)

이 스펙은 이미 `validation_interface.py`에 박혀 있습니다. 새 작업은 **stub만 교체**.

## 3. 이번 작업 목표

### 3.1 RAG 기반 실제 Validator 구현

`rule_engine/validation_interface.py`의 `make_stub_validator()`를 모델로 삼아, 같은 시그니처 `Callable[[Path], ValidationVerdict]`를 만족하는 진짜 validator를 새 모듈로 작성:

권장 위치: `rule_engine/validators/rag_validator.py` (새 디렉토리)

동작:
1. 입력 JSON 파일 경로를 받아 `RuleEngineOutput` dict 로드
2. `rationale[]`의 각 `flag`에 대해 RAG DB에 의미 검색 질의 (rule_id + flag.note 기반)
3. RAG 결과로 판정: confirmed_violation / false_alarm / needs_user_review
4. Rule Engine이 놓친 추가 위반 탐지 (선택적, 우선순위 낮음)
5. `ValidationVerdict` 반환

### 3.2 데모 통합

`rule_engine/_demo_run.py`를 약간 확장하거나 새 데모 스크립트 작성:
- `run_with_validation_loop(input_spec, real_validator, ...)` 호출
- 실제 verdict JSON 생성 확인
- 콘솔에 retry 횟수·escalation 여부·acknowledged_flags 요약 출력

### 3.3 L3 검증

작업 끝나면 `python3 -m rule_engine.tests._minirunner` 실행 → 138/138 통과 + L3 baseline 변화 없음 확인.

만약 RAG validator 통합으로 출력에 영향이 가면 (예: rationale에 새 entry 추가) L3가 깨질 수 있음. 의도된 변경이면 `RULE_ENGINE_REGEN_GOLDEN=1`로 재박제하고 commit 메시지에 이유 명시.

## 4. 먼저 읽어야 할 파일 (우선순위 순)

1. `rule_engine/validation_interface.py` — 인터페이스 스펙·dataclass·retry 루프
2. `rule_engine/tests/unit/test_validation_interface.py` — 기대 동작 예시
3. `rag_interface/` 전체 구조 (디렉토리 ls 먼저, README 있으면 그것부터)
4. `rule_engine/output_example.json` — validator가 받을 JSON의 실제 모양
5. `rule_engine/output_schema.md` — 7 블록 + flag 스키마 설명

## 5. 알려진 제약·함정

- **샌드박스에 pytest 설치 불가**: `pip install` 차단됨. `tests/_minirunner.py`가 pytest 일부를 emulate. 새 테스트도 minirunner 호환으로 작성 (autouse·indirect parametrize 같은 고급 기능 X).
- **OneDrive 동기화 truncation**: 50줄 넘는 한글 포함 파일을 Edit tool로 쓰면 가끔 잘림. 큰 파일은 `cat > path << 'PYEOF' ... PYEOF` + `sleep 1`로 bash heredoc 사용.
- **`__init__.py` 캐시**: `rule_engine/__pycache__/*.pyc`는 rm 안 됨 (permission denied). `__init__.py` 수정 후 import가 안 되면 `touch __init__.py`로 mtime 갱신.
- **Validation Agent와 RAG DB 공유 주의**: Validation Agent가 사용하는 RAG는 Design Agent와 같은 KB. echo chamber 방지를 위해 build-time 동기화는 OK, runtime 직접 통합은 회의에서 권장 X (보고서 v0.2 §2.1 참조).

## 6. Out of Scope (절대 손대지 말 것)

- 기존 15개 룰의 로직
- RAG DB 자체 (검색 API만 사용)
- UI / 웹폼
- v0.3 회의 보고서 docx (사용자가 별도로 작성 예정)
- 5/26 회의 결정 사항 변경 (이미 확정)

## 7. 검증 체크리스트 (작업 끝낼 때)

- [ ] `python3 -m rule_engine.tests._minirunner` → 138개 이상 통과 (신규 테스트 추가했으면 증가)
- [ ] 새 validator + 실제 URS로 end-to-end 데모 1회 성공
- [ ] verdict JSON 파일이 schema 준수
- [ ] L3 golden test 통과 또는 의도적 재박제 + commit 메시지 명시
- [ ] `rule_engine/__init__.py` public API에 새 validator export
- [ ] 짧은 사용 예시를 `validation_interface.py` 모듈 docstring 또는 README에 추가

## 8. 노션 참고 페이지

- 5/26 원본 회의 자료: https://www.notion.so/36c5b274338b81c382f3ce150c6f792d
- 회의 결정 구현 보고 v0.3 (이전 세션 결과): https://www.notion.so/36d5b274338b81ea916de64c63876ad6
- L3 Golden Test 도입 안내: https://www.notion.so/36d5b274338b81edb697c7d3db3f75ba
- 아키텍처 v0.2: https://www.notion.so/3675b274338b8132be39c02ba1d264fa

---

> 작성일: 2026-05-28 / 이전 세션 (Rule Engine + validation_interface stub + L3 baseline 박제 완료) 의 후속 작업 핸드오프
