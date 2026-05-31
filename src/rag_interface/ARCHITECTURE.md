# `rag_interface` — Architecture v0.2

> Status: **DRAFT v0.2** (2026-05-12) — v0.1을 간소화. 검토 후 v1.0으로 동결.
> v0.1은 `archive/ARCHITECTURE_v0.1.md`에 보존.

---

## 1. 이 레이어가 하는 일

에이전트(ProcessDesign / Validation / Layout …)가 RAG DB에 질문을 던질 때
거치는 단일 통로다. 다음 다섯 가지만 한다.

1. 백엔드 차이를 가린다 (지금 TF-IDF, 나중에 MiniLM이어도 호출부 동일).
2. 에이전트마다 어느 컬렉션을 어떻게 조회할지 결정한다 (라우팅).
3. 검색 결과의 신뢰도를 점수화하고, 미달이면 정해진 fallback을 발동한다.
4. 결과를 인용 가능한 형태로 감싸 돌려준다.
5. 호출 내역을 audit 파일에 남긴다.

LLM 호출, 룰 평가, 최적화 알고리즘은 이 레이어 밖이다. 본 레이어는 순수
검색 컴포넌트로 격리한다.

---

## 2. 폴더 구조

```
rag_interface/
├── ARCHITECTURE.md
├── __init__.py
├── models.py
├── backend.py
├── search.py
├── observability.py
├── profiles/
│   ├── process_design.yaml
│   ├── validation.yaml
│   └── layout.yaml
├── archive/
│   └── ARCHITECTURE_v0.1.md
└── tests/
    ├── conftest.py
    ├── test_backend.py
    ├── test_search.py
    └── test_end_to_end.py
```

분리 기준: **한 파일이 300줄 넘기 전까지는 나누지 않는다.** "언젠가 필요할
지도"는 분리 이유가 안 된다. 300줄을 넘는 시점에 그때 기준에서 다시 쪼갠다.

---

## 3. 모듈 4개

### 3.1 `models.py`

**한 줄 요약**: 이 레이어에서 주고받는 모든 데이터 구조를 모아둔 파일.

**왜 필요한가**: 데이터 클래스가 여러 파일에 흩어지면 import 순환과 시그니처
표류가 생긴다. 한 곳에 모아두면 v1.0 동결 시점에 "여기만 보면 된다"는
기준점이 된다. 에이전트 팀이 우리 레이어를 처음 읽을 때도 이 파일부터
보면 표면이 다 보인다.

**무엇을 안 하는가**: 로직 없음. 검증·변환·IO 일체 없음. 순수 데이터
클래스만.

들어가는 것: `Query`, `Hit`, `RetrievalResult`, `Citation`, `AgentProfile`,
`Decision`, `BackendInfo`.

### 3.2 `backend.py`

**한 줄 요약**: 벡터 DB에서 청크를 꺼내오는 코드. 추상 베이스 1개 +
TF-IDF 구현 1개를 한 파일에 둔다.

**왜 필요한가**: `RAG_DB_build/vector_store.py`는 인덱싱·persist 책임이
있고, 호출부에서는 그걸 알 필요가 없다. 이 분리가 없으면 백엔드 교체
PR이 에이전트 코드까지 휩쓸어버린다.

**무엇을 안 하는가**: 라우팅 결정 없음, confidence 계산 없음, 인용 포맷
없음. "쿼리 + 컬렉션 + 필터" 받아 "거리 붙은 청크 리스트"만 돌려준다.

`RAG_DB_build/`와의 유일한 접점이 이 파일이다. 메타데이터 스키마
(source, doc_type, scale, reliability, year, chunk_index, jurisdiction)는
두 폴더 사이의 약속으로 본다 — 한쪽이 바뀌면 다른 쪽도 같이 바뀐다.

### 3.3 `search.py`

**한 줄 요약**: 에이전트가 직접 부르는 메인 함수. 라우팅 + 검색 +
신뢰도 + fallback을 한 흐름으로 묶는다.

**왜 필요한가**: 라우팅·신뢰도 판정·fallback은 실전에서 항상 같이
호출된다. 별도 파일로 나누면 호출자가 순서·인자를 외워야 하고 같은
보일러플레이트를 매번 쓰게 된다 — v0.1에서 셋으로 나눴던 게 그 over-
engineering이었다.

**무엇을 안 하는가**: 데이터 모델 정의 없음 (models에 위임). 벡터 검색
자체 구현 없음 (backend에 위임). 로그 IO 자체 없음 (observability에
위임).

공개 함수는 사실상 하나다 —
`search(query, agent, top_k=5, extra_filters=None, trace_id=None)` →
`RetrievalResult`. 에이전트가 이 레이어에서 import하는 거의 유일한 이름.

내부 흐름: profile YAML 로드 → 컬렉션·필터 결정 → backend 호출 →
confidence 계산 → 임계값 미달이면 fallback 발동 → Citation으로 감싸기 →
audit 기록 → return.

### 3.4 `observability.py`

**한 줄 요약**: 호출 로그 출력과 audit 파일 append, 두 가지 단순 함수.

**왜 필요한가**: GMP 추적성과 논문 재현성 양쪽이 모든 검색의 기록을
요구한다. search.py 안에 인라인으로 쓰면 흐름이 흐려지고 테스트가
어렵다. 다만 메트릭 집계까지 넣으면 무거워지므로 **함수 두 개**로 한정.

**무엇을 안 하는가**: 메트릭 집계, Prometheus 익스포터, 분산 트레이싱
같은 거 없음. stdout 한 줄 + JSONL 한 줄이 전부.

함수 — `log_search(result)`, `append_audit(result, path)`. trace_id는
search.py에서 부여하고 여기서는 받기만 한다.

---

## 4. 모듈 간 흐름

```
  agent ─▶ search.search(query, agent)
              │
              ├─ models.AgentProfile (profiles/*.yaml)
              ├─ backend.TfidfBackend.search(...) ──▶ RAG_DB_build/vector_store
              ├─ (search 내부: confidence + fallback)
              ├─ models.Citation 으로 hit 감싸기
              └─ observability.log_search + append_audit
              ▼
          RetrievalResult
```

화살표는 한 방향. `models`가 leaf, `search`가 root. 순환 없음.

---

## 5. `RAG_DB_build/` 와의 연결

연결은 `backend.py`에서만 일어난다. `RAG_DB_build/vector_store.py`의
`PersistentClient`와 `Collection`만 import한다. `tokenize` 같은 내부
함수는 건드리지 않는다.

DB 경로 기본값은 `RAG_DB_build/data/`이며, 환경변수 `RAG_DB_PATH`로
오버라이드한다.

v0.3 구현 시 `RAG_DB_build/evaluate.py`의 12개 표준 쿼리를 그대로
가져와 `search.search`를 통과시키는 회귀 테스트(`tests/test_end_to_end.py`)를
만든다. 같은 쿼리로 P@5 / MRR이 기존 평가와 ±0.02 안에서 재현되면 통과.

---

## 6. 에이전트 프로필 (YAML)

에이전트별로 라우팅·임계값·fallback을 한 YAML에 담는다. 새 에이전트
추가 = YAML 1개 추가, 코드 0줄. `profiles/validation.yaml` 개념 예시:

```text
agent: ValidationAgent
backend: tfidf
collections: [{name: regulatory_docs, weight: 1.0}]
confidence: {min_threshold: 0.10}
top_k_default: 5
fallback: {on_low_confidence: broaden_filter, on_empty: raise}
citation: {style: inline_with_chunk_id}
```

---

## 7. 열린 결정 (4개)

코드 작성 전 확정 필요한 항목. 각 항목에 현재 디폴트 제안을 함께 적었다.

**D1. confidence 임계값** — 디폴트 0.10 (cosine). 현재 평가의
distance 평균 1.76 ↔ cosine ~0.12 기준 보수값. 너무 높이면 fallback
상시 발동, 너무 낮추면 게이트가 의미 없음. 도메인 전문가 정성 확인 1라운드.

**D2. ValidationAgent의 cross-collection 허용 여부** — 디폴트 **금지**.
규제 질의에 design 문서가 섞이면 인용 신뢰도가 깨진다. ProcessDesign·
Layout 에이전트는 허용해도 무방하지만 Validation만 예외. 도메인 전문가 확인.

**D3. Citation 표준 스타일** — 디폴트 `[Source, Year, §chunk_index]`
inline (예: `[EU_GMP_Annex1, 2022, §17]`). 논문·보고서 본문 양쪽에 그대로
사용 가능. BibTeX 출력은 필요해질 때 추가.

**D4. 설정 파일 형식** — 디폴트 **YAML**. JSON은 주석 불가 → 도메인
전문가 검토에 불편. PyYAML 의존성 비용을 받아들임.

---

## 8. 디폴트로 진행 (재검토 없이 v0.3 시작)

다음 항목은 문제 발생 시점에 재검토하기로 하고 지금은 디폴트로 간다.

- 설정 파일 위치: `rag_interface/profiles/`.
- 동기 API만 (async는 필요 시점에 추가).
- 캐싱 없음 (재현성과 충돌 가능).
- 영문 쿼리만 (현재 코퍼스 기준).
- chromadb 백엔드 스텁 만들지 않음 — 실제 필요해질 때 `backend.py`에
  클래스 하나 추가하면 된다.

---

## 9. 마일스톤

- **v0.2 (현재)** — 본 ARCHITECTURE.md. 리뷰어 승인이 게이트.
- **v0.3** — 4개 모듈 구현 + 12-쿼리 회귀 테스트 통과. P@5 ≥ 기존 평가
  −0.02가 게이트.
- **v1.0** — 첫 에이전트(ProcessDesign 추정)가 실제 호출에 사용 + audit
  파일이 실제 쌓이는 상태. 시그니처 동결, 첫 논문 실험 시작.

---

## 10. 비목표

LLM 호출·프롬프트, 청킹·임베딩·인덱스 빌드, 룰 평가·최적화, 인증·권한,
분산 배포, 자동 번역. 본 레이어는 일절 다루지 않는다.

---

## 작성 자가 점검

본 문서가 v0.1 회고에서 합의한 가이드라인을 만족하는지 자가 점검한다.
수치는 본 문서 본문(이 자가 점검 섹션 제외)에 대해 측정.

- [x] **모듈 수 = 4인가?**  → ✅ models, backend, search, observability
- [x] **GoF 패턴 용어 등장 횟수 ≤ 3인가?**  → ✅ 0회
  - "Facade / Adapter / Port / Strategy / Observer / Factory / Singleton /
    Dependency Inversion / Single Responsibility / Hexagonal" 모두
    본문에 등장하지 않음. "추상 베이스"라는 일반 표현 1회만 사용.
- [x] **열린 결정 = 4인가?**  → ✅ D1, D2, D3, D4 정확히 4개
- [x] **각 모듈마다 "왜 필요한가" 설명이 있는가?**  → ✅ 4개 모두 보유
  - models.py § "왜 필요한가" / backend.py § "왜 필요한가" /
    search.py § "왜 필요한가" / observability.py § "왜 필요한가"
- [x] **분량이 v0.1의 60% 수준인가?**  → ✅ 64.3% (v0.1 384줄 →
  v0.2 247줄). 본문(자가 점검 제외)만 보면 223줄, 즉 v0.1 대비 58%.
  목표 60% 안팎 달성. `wc -l ARCHITECTURE.md archive/ARCHITECTURE_v0.1.md`로 재확인 가능.

추가 자가 점검 (v0.1 회고에서 제기된 다른 문제들):

- [x] confidence와 fallback이 한 파일에 통합되었는가? → ✅ `search.py`에 통합
- [x] observability가 단순 함수 2개로 축소되었는가? → ✅ `log_search`,
  `append_audit`
- [x] cli/, stub_chroma 등 YAGNI 모듈이 제거되었는가? → ✅ 모두 제거
- [x] 팀원이 코드 없이 문서만 읽어도 의도가 이해되는가? → 검수자 확인 부탁
