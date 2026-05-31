# 핸드오프 — RAG Validator + rag_interface + URS Parser + Doc Agent 정리 (2026-05-29)

> 이전 핸드오프(`handoff_validation_agent_integration.md`, 2026-05-28)의 후속.
> 이 문서는 그 이후 한 세션에서 완료된 작업과 다음 세션이 이어받을 일을 정리한다.
> **작업 규칙은 `CLAUDE.md` 를 먼저 읽을 것** (특히 §1 truncation 안전 조항).

---

## 0. 시스템 위치 (절대 경로)

- Rule Engine: `C:\Users\User\OneDrive - SKKU\claude_cowork_file\rule_engine\`
- RAG 인터페이스(완성): `C:\Users\User\OneDrive - SKKU\claude_cowork_file\rag_interface\`
- RAG DB(빌드됨): `C:\Users\User\OneDrive - SKKU\claude_cowork_file\RAG_DB_build\`
- 데모 URS: `C:\Users\User\OneDrive - SKKU\claude_cowork_file\URS_ConceptualDesign for layout_0516.xlsx`
- 운영 규칙: `C:\Users\User\OneDrive - SKKU\claude_cowork_file\CLAUDE.md`

---

## 1. 이번 세션에서 완료한 일 (요약)

### 1.1 RAG 기반 Validation Agent 구현
- `rule_engine/validators/rag_validator.py` — `make_rag_validator(rag_search, config)` factory. stub 과 동일 시그니처 `Callable[[Path], ValidationVerdict]`. 검색 백엔드는 의존성 주입.
- verdict 분기: top hit similarity 기준 confirmed_violation / needs_user_review / false_alarm. `severity=info` 는 RAG 호출 없이 false_alarm.

### 1.2 TF-IDF 환경 대응 3단계
RAG DB 가 (오프라인 제약) TF-IDF 로 빌드되어 cosine 분포 낮음(0.05~0.13). 대응:
1. **canonical 영문 쿼리** (`_CANONICAL_QUERIES`, 15룰) — 한국어 flag note → 영문 KB 매칭 우회. 평균 cosine +0.097.
2. **source metadata 필터** (`_RULE_TO_SOURCES`, 15룰) — 룰별 관련 regulatory 문서로 범위 한정.
3. **percentile threshold calibration** (`calibrate_thresholds`, `make_calibrated_rag_validator`) — 분포 기반(95/80 percentile).

### 1.3 ⭐ rag_interface backend + search 구현 완료 (이번 세션 핵심)
ARCHITECTURE.md v0.2 §3.2~3.3 명세대로 구현:
- `rag_interface/backend.py` — 추상 베이스 `RetrievalBackend` + `TfidfBackend`. `RAG_DB_build/vector_store.py` 의 `PersistentClient` 만 import. **metadata_filter `{"source": [list]}` OR/IN 지원** — vector_store 는 단일 값 where 만 되므로 source 별 fan-out 후 similarity merge·top_k 절단. distance→similarity = 1 − d/2.
- `rag_interface/search.py` — 단일 진입점 `search(query: SearchQuery) -> SearchResult`. 흐름: profile 로드 → 컬렉션·필터 결정 → backend → confidence → fallback(broaden_filter/warn) → audit → return. `calling_agent` 가 프로필 선택. **`Callable[[SearchQuery], SearchResult]` 시그니처라 `make_rag_validator(rag_search=search)` 로 그대로 주입 가능.**
- `rag_interface/observability.py` — `log_search` / `append_audit` (JSONL).
- `rag_interface/profiles/{validation,design,layout}.yaml` — 에이전트별 라우팅·임계값·fallback. PyYAML 6.0.3 사용. ValidationAgent 는 D2(cross-collection 금지)대로 regulatory_docs 단일.
- `rag_interface/__init__.py` — `search` export.

### 1.4 ⭐ threshold 확정 + mock 교체 완료
- 실제 RAG DB calibration(95/80 percentile) 결과: **high=0.1272, medium=0.0974** — 수동 제안값 0.12/0.08 과 거의 일치(확정).
- `rule_engine/_demo_validation_run.py` 의 `_mock_rag_search` 를 **실제 `rag_interface.search` 로 교체**. `make_calibrated_rag_validator(rag_search=search)` 사용.
- end-to-end 결과: 실제 URS → Rule Engine → 실제 RAG 검색 → verdict(confirmed 1 / review 18 / false 5), 실제 인용(ISO 14644-4 등) 첨부.
- 참고: `RagValidatorConfig` 기본 임계값(0.5/0.2)은 MiniLM 가정값으로 유지(기존 단위테스트 호환). TF-IDF 환경은 calibration 또는 명시적 config 로 0.12/0.08 적용.

### 1.5 URS Parser 정식 모듈화
- `rule_engine/urs_parser.py` — Public API: `parse_urs_xlsx`, `build_rule_engine_input`, `load_urs_as_input`, `clock_from_text`, `URS_PATH`.

### 1.6 Documentation Agent 팀 요청 처리 (7건)
- **#1** airlock connects 역채움 (`backfill_airlock_connections`) — connects_higher 18/18. connects_lower 는 corridor 측이라 None. area_m2 미처리(추후 룰).
- **#4** 이름 trailing space — `urs_parser._clean_name()` strip. warning 4→0, adjacency 23→27.
- **#5/#7** URS xlsx 직접 수정 — `Mateial-in→Material-in`(`R_MATERIAL_IN` 확정), 장비명/용량 정정 14건. 백업: `...backup_20260529.xlsx`.
- **#2** 장비 process_no — 이미 JSON 에 있음(필드명 `process_no`). DocAgent md 컬럼 추가.
- **#3** 에어록 rooms[]/airlocks[] 중복 — URS Room 시트에 에어록이 방으로 입력된 탓. Doc팀이 placeholder 처리. dedup 미결.
- **#6** 정제실 차압 동일 — v1 의도적 미구현(rule_13). v2 백로그.

### 1.7 L3 Golden 재박제
- 새 baseline: rooms 48 / airlocks 18 / **adjacency 27** / flag_counts **{info:3, suspected_violation:21}**.
- `test_golden_real_urs.py` 의 `_BASELINE_*` 상수·docstring 갱신 완료.

### 1.8 산출물·규칙
- `output_example.json`, `RuleEngine_Output_for_DocAgent.md` 재생성.
- `CLAUDE.md` 신규(운영 규칙). Notion: [Validation RAG 연동 보고](https://www.notion.so/36e5b274338b816cbdc2d2483701f9a1), [TF-IDF 회의 안건](https://www.notion.so/36e5b274338b81af9477ed856cc04cc1).

---

## 2. 현재 테스트 상태

- rule_engine 단위 테스트 **183/183 통과** (`python3 -m rule_engine.tests._minirunner`). L3 golden 3/3 통과.
- rag_interface: `python3 -m rag_interface.tests.test_search_backend` (backend+search, 9건) + `test_models` 통과.
- 데모 `_demo_run`, `_demo_validation_run`(실제 RAG) 정상.

---

## 3. 시스템 통합 현황 (Documentation Agent 제외) — ✅ 전 구간 연결됨

| 컴포넌트 | 상태 |
| --- | --- |
| Rule Engine (15룰 + 7블록 + urs_parser) | ✅ 동작 |
| validation_interface (JSON I/O + retry) | ✅ 동작 |
| rag_validator (canonical+filter+calibrate) | ✅ 동작 |
| **rag_interface.search / backend** | ✅ **구현 완료** (실제 RAG DB 연결) |
| RAG_DB_build (TF-IDF 벡터스토어) | ✅ DB 빌드됨 (regulatory 238 / design 295) |
| Documentation Agent | 외부 팀, 연동 협의 중 (출력 계약은 전달됨) |

**URS → Rule Engine → validation_interface → rag_validator → rag_interface.search → RAG DB** 전 구간이 실제로 흐른다. mock 없음. Documentation Agent 만 외부 팀 작업으로 남음.

---

## 4. 다음 세션이 이어받을 일 (우선순위)

1. **#3 에어록 중복 dedup 설계 결정** — rooms[] 의 area=null placeholder 유지/제거. Doc Agent 팀과 합의 후 구현.
2. **#1 airlock area_m2 산출 룰** — 현재 None. 전실 면적 권장치 KB 보강 또는 룰 추가.
3. **rag_interface 12-쿼리 회귀 테스트** (아키텍처 §5) — `RAG_DB_build/evaluate.py` 의 표준 쿼리로 P@5/MRR ±0.02 재현 테스트.
4. (선택) **#6 rule_13 정제실 차등 차압** v2 구현.
5. (선택) **rag_validator confirmed/review 기본값** — 현재 MiniLM 가정(0.5/0.2). TF-IDF 를 기본 환경으로 굳히려면 기본값을 0.12/0.08 로 바꾸고 관련 단위테스트 갱신(현재는 calibration 으로 우회).

---

## 5. 회의/결정 대기 안건

- **TF-IDF vs MiniLM 표현** (외부 논문/보고서) — [회의 안건 페이지](https://www.notion.so/36e5b274338b81af9477ed856cc04cc1). 안건 A(팀 인지), 안건 B(외부 표현) 합의 필요.
- **#3 에어록 dedup**, **#6 v2 차압** 스코프 결정.
- **confidence threshold** — calibration(0.127/0.097) 을 도메인 전문가가 정성 확인(아키텍처 §7 D1).

---

## 6. 알려진 제약·함정 (CLAUDE.md 참조)

- **긴 한글 파일 Edit → truncation**: heredoc 분할 작성 기본(CLAUDE.md §1). 이번 세션에도 다수 발생, 전부 head/tail 복구.
- **pycache stale**: 수정 후 `touch`(§2).
- **pytest 설치 불가**: rule_engine 은 minirunner, rag_interface 는 자체 `__main__` 러너.
- **RAG echo chamber**: Validation 은 검색 결과만 후처리(KB 직접통합 X) — 준수.
- **rag_interface fallback on_empty**: 프로필 기본은 `warn`(insufficient_evidence 반환). `raise` 로 두면 validator loop 가 깨지므로 의도적 채택.

---

## 7. 노션 참고 페이지

- [Validation Agent ↔ Rule Engine 실제 연동 구현 보고 (2026-05-28)](https://www.notion.so/36e5b274338b816cbdc2d2483701f9a1)
- [회의 안건 — RAG 임베딩 백엔드(TF-IDF) 결정 사항 (2026-05-28)](https://www.notion.so/36e5b274338b81af9477ed856cc04cc1)
- [회의 결정 구현 보고 v0.3](https://www.notion.so/36d5b274338b81ea916de64c63876ad6)
- [아키텍처 v0.2](https://www.notion.so/3675b274338b8132be39c02ba1d264fa)

---

> 작성일: 2026-05-29 / rag_interface(backend+search) 구현 + threshold 확정 + mock 교체 완료. 전 구간(Doc Agent 제외) 실제 연결됨.
