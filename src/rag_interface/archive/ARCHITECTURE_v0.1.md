# `rag_interface` — Architecture Proposal

> Status: **DRAFT v0.1** (2026-05-12) — 코드 작성 전 합의용 문서.
> Reviewer 확정 후 v1.0으로 격상하고 그 시점부터 구현 시작.

---

## 1. 목적과 위치

본 레이어는 **하위 RAG 인프라(`RAG_DB_build/`)와 상위 에이전트(`ProcessDesignAgent`,
`ValidationAgent`, `LayoutAgent` …) 사이의 단일 진입점**이다. 프로젝트 전체
구조에서 보면 다음과 같다.

```
[ Agents ]   ─── 도메인 로직, 룰베이스, 최적화
    │
    ▼
[ rag_interface ]   ─── 본 문서가 정의하는 레이어
    │
    ▼
[ RAG_DB_build ]   ─── 청킹·임베딩·persist (현재 TF-IDF, 향후 MiniLM)
    │
    ▼
[ 원본 문서 ]   ─── ISPE, FDA, ISO, EU GMP …
```

이 레이어의 책임은 정확히 다섯 가지로 한정한다.

1. **백엔드 추상화** — TF-IDF든 MiniLM이든 Chroma든 같은 호출부에서 동일하게 보이게 한다.
2. **라우팅 정책** — "이 에이전트는 어느 컬렉션을, 어떤 메타 필터로, 어떤 가중치로 조회하는가"를 코드 한 곳에 모은다.
3. **신뢰도 게이팅** — 거리/스코어를 confidence로 환산하고, 임계값 미달이면 fallback을 발동한다.
4. **인용 가능한 결과 포맷** — 모든 hit는 표준화된 Citation 객체로 감싸 반환한다. 논문/규제 자료 작성에 그대로 들어갈 수 있어야 한다.
5. **호출 로깅과 추적성** — 모든 질의·결과·내부 결정(어느 fallback이 떴는지 등)을 audit log에 남긴다. GMP 추적성 요구와 논문 재현성에 둘 다 필요하다.

이 외의 책임(쿼리 재작성, LLM-답변 생성, 룰 평가)은 **본 레이어에 두지 않는다**.
neuro-symbolic 시스템에서 LLM 호출 최소화 원칙을 지키기 위해, 본 레이어는
순수 검색 컴포넌트로 격리한다.

---

## 2. 설계 원칙

| 원칙 | 어떻게 반영되는가 |
|---|---|
| **Dependency Inversion** | 에이전트는 추상 `VectorBackend`에만 의존. 구체 백엔드(`TfidfBackend`, 미래의 `ChromaBackend`)는 `__init__`에서 주입. |
| **Single Responsibility** | 한 파일 = 한 책임. routing은 routing만, citation은 citation만. |
| **Reproducibility** | 모든 호출에 backend version + DB snapshot hash + config hash를 기록. 논문 재현용. |
| **Auditability** | 모든 검색은 trace_id를 갖는다. fallback 발동, 임계값 미달, 컬렉션 라우팅 결과까지 audit로그에 남긴다. |
| **Offline-first** | 외부 호출 없음. 본 레이어 자체는 LLM API에 닿지 않는다. |
| **Configuration over code** | 임계값·에이전트 프로필은 YAML로. 하드코딩하지 않는다. |

---

## 3. 폴더 구조 제안

```
rag_interface/
├── ARCHITECTURE.md             # 본 문서
├── README.md                   # 사용 예시·설치 가이드 (v1.0 시점에 작성)
├── __init__.py                 # 공개 API 노출: RAGInterface, types
│
├── interface.py                # ★ 단일 진입점 (Facade)
│
├── types.py                    # 모든 데이터 클래스(Query, Hit, Citation, RetrievalResult, AgentProfile)
├── config.py                   # 설정 로딩(YAML), 기본값, 경로 해석
│
├── backends/
│   ├── __init__.py
│   ├── base.py                 # VectorBackend ABC (포트)
│   ├── tfidf.py                # TfidfBackend — RAG_DB_build/vector_store.py 를 어댑트
│   └── stub_chroma.py          # ChromaBackend 스텁 — 시그니처만, NotImplementedError
│
├── routing.py                  # AgentProfile, CollectionRouter
├── confidence.py               # ConfidenceScorer (distance → confidence + decision)
├── fallback.py                 # FallbackStrategy (none / broaden / cross-collection / raise)
├── citation.py                 # CitationFormatter, Citation 직렬화
├── observability.py            # QueryLogger, AuditTrail, trace_id 생성
│
├── profiles/
│   ├── process_design.yaml     # ProcessDesignAgent용 라우팅·임계값
│   ├── validation.yaml         # ValidationAgent용
│   └── layout.yaml             # LayoutAgent용
│
├── cli/
│   └── search.py               # `python -m rag_interface.cli.search ...`
│
└── tests/
    ├── conftest.py             # 합성 인덱스 fixture(작은 corpus)
    ├── test_backends_tfidf.py
    ├── test_routing.py
    ├── test_confidence.py
    ├── test_fallback.py
    ├── test_citation.py
    ├── test_interface_end_to_end.py
    └── test_audit_log.py
```

설계 의도 보충 설명. `cli/`는 디버깅 + 도메인 전문가 라벨링 작업 보조용
(쿼리 → 결과 표 출력)이며 production 의존성이 아니다. `profiles/`를 YAML로
분리한 이유는, 에이전트 추가 시 코드 수정 없이 파일 1개만 추가하면 되기
때문 — 이건 논문에서 ablation study 비용을 낮춘다.

---

## 4. 파일별 책임 (Single Responsibility)

| 파일 | 역할 | 의존 (이 레이어 내부) | 의존 (외부) |
|---|---|---|---|
| `types.py` | `Query`, `Hit`, `Citation`, `RetrievalResult`, `AgentProfile`, `Decision` 같은 데이터 모델만 정의. 비즈니스 로직 없음. | — | dataclasses, typing |
| `config.py` | `Settings` 로딩(env + YAML), 기본 경로(`RAG_DB_build/data/`) 해석, profile YAML 디렉터리 인덱싱. | `types` | PyYAML 또는 stdlib(JSON fallback) |
| `backends/base.py` | `VectorBackend` 추상 베이스. 메서드: `search(query, collection, top_k, where) -> list[Hit]`, `info() -> BackendInfo`. | `types` | — |
| `backends/tfidf.py` | `RAG_DB_build/vector_store.py`의 `PersistentClient`/`Collection`/`TfidfEmbedder`를 감싸 `VectorBackend` 계약을 충족. **로딩만**, 추가 임베딩 없음. | `backends.base`, `types` | `RAG_DB_build/vector_store.py` |
| `backends/stub_chroma.py` | 미래 sentence-transformers + chromadb 백엔드의 시그니처 자리표시자. v1.0에서는 `NotImplementedError` raise. | `backends.base`, `types` | (미래) chromadb |
| `routing.py` | `AgentProfile`(YAML→dataclass) + `CollectionRouter`. 입력: agent_name, query. 출력: `[(collection, where_filter, weight), ...]` 호출 계획. | `types`, `config` | — |
| `confidence.py` | distance(squared L2, 0~2) → confidence(0~1) 변환식 + threshold 판정. 변환식은 RAG_DB 문서에서 유도한 `confidence = max(0, 1 - d/2)` (=cosine) 사용. | `types` | numpy |
| `fallback.py` | 신뢰도 미달 시 정책: ① 필터 완화(다른 jurisdiction 허용), ② cross-collection 조회, ③ top-k 확대, ④ 빈 결과 + reason 반환. 정책 자체는 enum, 실행은 `Retriever`가 위임 호출. | `types`, `backends.base` | — |
| `citation.py` | `Hit` → `Citation`. 최소 필드: source, year, jurisdiction, chunk_index, snippet, retrieval_score, retrieval_distance. 출력 포맷 3가지: dict / inline-text / BibTeX-lite. | `types` | — |
| `observability.py` | `QueryLogger`(stdout/file), `AuditTrail`(JSONL append), `trace_id` 생성(`uuid4`). 호출별 latency 측정. | `types`, `config` | logging, json, uuid |
| `interface.py` | Facade 클래스 `RAGInterface`. 모든 컴포넌트를 DI 받아 보유. 공개 메서드: `search()`, `search_for_agent()`, `multi_query()`, `health_check()`. | 위 전부 | — |
| `cli/search.py` | argparse 기반 CLI. `--agent`, `--query`, `--top-k`, `--format`. | `interface` | argparse |
| `profiles/*.yaml` | 에이전트별 라우팅·임계값·citation 스타일 사전 정의. 코드 아님. | — | — |

각 파일은 한 가지 책임만 가지므로 단위 테스트가 1:1 매핑된다 (`tests/test_*.py`).

---

## 5. 의존성 다이어그램

```
                                                              ┌──────────────┐
                                                              │  agents      │
                                                              │ (외부)       │
                                                              └──────┬───────┘
                                                                     │ uses
                                                                     ▼
                                                              ┌──────────────┐
                                                              │ interface.py │  Facade
                                                              │ RAGInterface │
                                                              └──┬───────────┘
                  ┌─────────────────────┬──────────┬──────────┼───────────┬──────────────┬─────────────┐
                  │                     │          │          │           │              │             │
                  ▼                     ▼          ▼          ▼           ▼              ▼             ▼
            ┌───────────┐         ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌───────────┐  ┌────────────┐
            │ routing.py│         │backends/ │ │confid- │ │fallback│ │citation  │ │observabil-│  │ config.py  │
            │           │         │  base.py │ │ence.py │ │  .py   │ │   .py    │ │  ity.py   │  │            │
            └─────┬─────┘         └────┬─────┘ └───┬────┘ └───┬────┘ └────┬─────┘ └─────┬─────┘  └─────┬──────┘
                  │                    │           │          │           │             │              │
                  │   ┌────────────────┴──────┐    │          │           │             │              │
                  │   ▼                       ▼    │          │           │             │              │
                  │ ┌──────────────┐  ┌───────────────┐       │           │             │              │
                  │ │backends/     │  │backends/      │       │           │             │              │
                  │ │ tfidf.py     │  │ stub_chroma.py│       │           │             │              │
                  │ └──────┬───────┘  └───────────────┘       │           │             │              │
                  │        │                                  │           │             │              │
                  │        ▼ adapts                           │           │             │              │
                  │ ┌──────────────────────────┐              │           │             │              │
                  │ │ RAG_DB_build/            │              │           │             │              │
                  │ │  vector_store.py         │  (외부 폴더) │           │             │              │
                  │ │  (PersistentClient,      │              │           │             │              │
                  │ │   Collection,            │              │           │             │              │
                  │ │   TfidfEmbedder)         │              │           │             │              │
                  │ └──────────────────────────┘              │           │             │              │
                  │                                           │           │             │              │
                  └─────── reads ──── profiles/*.yaml ────────┴───────────┴─────────────┴──────────────┘
                                                  ▲
                                                  │ paths from
                                                  └──────────────────────────────── config.py

   types.py  ──▲────────────────────────────────  (모든 모듈이 의존)

   화살표 의미: A ──▶ B = "A가 B에 의존"
```

핵심 관찰:
- **사이클 없음.** `types`/`config`가 leaf, `interface`가 root.
- `RAG_DB_build/`는 `backends/tfidf.py`에서만 import한다. 즉 백엔드 교체는 이 파일 하나만 다시 쓰면 된다.
- `routing.py`는 YAML만 읽고 백엔드를 모른다. 라우팅 정책 변경이 검색 코드에 새지 않는다.
- `observability.py`는 다른 컴포넌트를 import하지 않는다(반대로 다른 곳에서 가져다 쓴다). 사이클 방지를 위해 단방향.

---

## 6. 공개 API 스케치 (시그니처만, 구현 X)

다음은 합의 확인용 의도 표현일 뿐 코드는 아니다.

```text
class RAGInterface:
    @classmethod
    def from_config(cls, settings_path: Path | None = None) -> "RAGInterface": ...

    def search(self, query: str, *, agent: str, top_k: int = 5,
               extra_filters: dict | None = None,
               trace_id: str | None = None) -> RetrievalResult: ...

    def multi_query(self, queries: list[str], *, agent: str,
                    top_k: int = 5) -> list[RetrievalResult]: ...

    def health_check(self) -> HealthReport: ...
```

```text
@dataclass(frozen=True)
class RetrievalResult:
    query: str
    agent: str
    hits: list[Hit]                  # ranked
    decision: Decision               # ok | low_confidence | fallback_triggered | empty
    fallback_used: FallbackKind | None
    trace_id: str
    backend_info: BackendInfo        # version, vocab size, db hash
    elapsed_ms: float

@dataclass(frozen=True)
class Hit:
    document: str                    # chunk text
    metadata: dict
    distance: float
    confidence: float                # 0..1
    citation: Citation
```

이 시그니처는 v1.0 합의 시점에 동결한다(에이전트 코드가 의존할 표면).

---

## 7. 한 호출의 데이터 흐름

```
agent.call("CIP cleaning validation product contact surface")
        │
        ▼
  RAGInterface.search(query, agent="Validation")
        │ trace_id 부여, latency 측정 시작
        ▼
  CollectionRouter.plan(agent="Validation", query)
        │  → [(regulatory_docs, {jurisdiction in {FDA,EMA,WHO}}, w=1.0)]
        ▼
  for each (coll, where, w):
      VectorBackend.search(query, coll, top_k=N, where)
        │  → raw_hits (with distances)
        ▼
  ConfidenceScorer.assign(raw_hits)
        │  confidence = max(0, 1 - d/2)
        ▼
  Decision: 모든 hit의 confidence < threshold?
        │
        ├─ no  → 그대로 통과
        └─ yes → FallbackStrategy.apply(...)
                   ├─ broaden_filter
                   ├─ cross_collection  → CollectionRouter 재호출
                   └─ raise / empty
        ▼
  CitationFormatter.wrap(each hit)  → Citation 객체
        ▼
  AuditTrail.write({trace_id, query, plan, decision, fallback, hits, elapsed})
        ▼
  return RetrievalResult(...)
```

---

## 8. 기존 `RAG_DB_build/` 와의 연결

연결은 **단 하나의 파일**에서만 일어난다 — `backends/tfidf.py`.

```text
backends/tfidf.py
    ├─ from RAG_DB_build.vector_store import PersistentClient
    ├─ __init__(self, db_path): self._client = PersistentClient(db_path)
    ├─ self._embedder = self._client.embedder    (이미 로드된 어휘 재사용)
    └─ search(...): self._client.collections[coll].query(..., embedder=self._embedder)
```

원칙:
- `RAG_DB_build/`는 **인덱싱·persist 책임만**. 본 레이어는 **읽기 전용**으로만 접근.
- 본 레이어는 `RAG_DB_build/vector_store.py`의 공개 클래스(`PersistentClient`, `Collection`)에만 의존. 내부 함수(예: `tokenize`)는 import하지 않는다.
- 메타데이터 스키마(source/doc_type/scale/reliability/year/chunk_index/jurisdiction)는 **불변 계약**으로 본다. 변경 시 `RAG_DB_build`에서 마이그레이션 + 본 레이어의 `types.py` 동기 업데이트.
- DB 경로는 `config.py`에서 기본 `RAG_DB_build/data/`로 해석. 환경변수 `RAG_DB_PATH`로 오버라이드.
- 향후 MiniLM 마이그레이션 시: ① `RAG_DB_build`에서 새 인덱스 빌드 → ② `backends/chroma.py` 구현(스텁→실구현) → ③ profile YAML에서 backend 키만 `tfidf` → `chroma`로 바꿈. **interface.py, routing.py, agent 코드는 일절 수정 없음.**

평가 스크립트(`RAG_DB_build/evaluate.py`)는 본 레이어가 안정되면 본 레이어를
호출하도록 리팩토링 — 같은 ground truth 셋이 백엔드 비교 실험에 그대로
재사용된다. 이건 paper용 ablation table 비용을 0에 가깝게 만든다.

---

## 9. 설정과 에이전트 프로필 (YAML 예시 의도)

`profiles/validation.yaml` (개념 예시 — 실제 값은 v1.0 시점에 도메인 검토):

```text
agent: ValidationAgent
backend: tfidf
collections:
  - name: regulatory_docs
    weight: 1.0
    where:
      jurisdiction: any         # FDA | EMA | WHO | ISO | any
confidence:
  min_threshold: 0.10           # cosine ~0.10
  prefer_above: 0.30
top_k_default: 5
fallback:
  on_low_confidence: broaden_filter
  on_empty: cross_collection    # design_standards 도 시도
citation:
  style: inline_with_chunk_id
audit:
  level: full
```

profile 추가 = 코드 0줄. 라우팅 정책 변경 = YAML 한 줄.

---

## 10. 관측성과 감사 추적

| 채널 | 무엇 | 어디로 |
|---|---|---|
| **structured log** | INFO/WARN 레벨 이벤트 (질의 시작, plan 결정, fallback 발동) | stdout + 회전 로그 파일 |
| **audit trail** | 모든 검색의 trace_id, query, plan, decision, hits(요약), latency | `audit/<YYYYMMDD>.jsonl` 추가 전용 |
| **metric** | 호출 수, 평균 latency, fallback 비율, low-confidence 비율 | Prometheus-style 카운터(in-memory; 추후 export) |

audit는 **추가 전용(append-only)** 으로 다룬다. GMP 추적성과 논문 재현성
양쪽에 필요하기 때문이다. JSONL이면 grep, jq, pandas 어디서든 분석 가능.

---

## 11. 테스트 전략

- **합성 corpus fixture**: 10\~20개 작은 청크를 가진 in-memory `Collection`을 만들어 백엔드 의존성을 없앤다. `conftest.py`에 정의.
- **유닛 테스트**: 모든 파일에 1:1 매핑.
- **End-to-end 테스트**: 실제 `RAG_DB_build/data/`를 읽어 `RAGInterface.search(query, agent="Validation")` 호출 → 알려진 source가 hits에 포함되는지 확인. (스모크 테스트 수준)
- **회귀 테스트**: 12개 표준 쿼리(이미 `RAG_DB_build/evaluate.py`에 정의됨)를 본 레이어를 통해 다시 돌려 P@5/MRR이 기준값 ±ε 안에 있는지 확인 → CI에 통합.

---

## 12. 열린 결정 (검토 부탁드림)

코드 시작 전 확정이 필요한 항목들. 각 항목에 대한 **현재 디폴트 제안**을
함께 적었다.

| # | 결정 항목 | 디폴트 제안 | 비고 |
|---|---|---|---|
| D1 | confidence 임계값 | 0.10 (cosine 기준) | 현재 평가에서 distance 평균 1.76 → cosine 0.12. 임계값을 너무 높이면 fallback이 상시 발동. 도메인 전문가 검토 필요. |
| D2 | fallback 우선순위 | low_conf → broaden_filter → cross_collection → empty | Validation은 cross_collection을 막아야 한다는 의견도 가능 (규제는 design 문서로 대체 불가). |
| D3 | Citation 스타일 표준 | `[Source, Year, §chunk_index]` inline | 논문 본문용 / 보고서용 두 가지 분리 필요할 수 있음. |
| D4 | YAML vs JSON 설정 | YAML | PyYAML 의존성 추가. JSON으로 가면 의존성 0이지만 주석 불가. |
| D5 | profile 위치 | `rag_interface/profiles/` | 에이전트가 자체 디렉터리에 보관하는 안도 가능 — DI로 경로 주입하면 어느쪽이든. |
| D6 | 캐싱 | v1.0에서는 미포함 | 결정론적 동일 쿼리 재실행을 캐시할지 여부. 논문 재현성과 충돌 가능. |
| D7 | 비동기 인터페이스 | sync only (v1.0) | 에이전트가 async 채택하면 v1.x에서 추가. |
| D8 | 다국어 쿼리 | 영문만 | 현재 코퍼스가 영문이므로 한글 쿼리는 routing에서 거부 or 경고. |

---

## 13. 마일스톤

| 단계 | 산출물 | 게이트 |
|---|---|---|
| **v0.1** (현재) | 본 ARCHITECTURE.md | Reviewer 승인 |
| v0.2 | `types.py`, `config.py`, `backends/base.py` 스켈레톤 + 시그니처 동결 | 시그니처 리뷰 |
| v0.3 | `backends/tfidf.py` + 기본 `interface.py` + 12-쿼리 회귀 통과 | P@5 ≥ 기존 평가 −0.02 |
| v0.4 | `routing.py` + `confidence.py` + `fallback.py` + profile YAML 3종 | 에이전트 1개가 실제 호출 성공 |
| v0.5 | `citation.py` + `observability.py` + CLI | 도메인 전문가 라벨링 워크플로우 가동 |
| **v1.0** | 시그니처 동결, 문서화 완료, CI 통합 | 첫 논문 실험 시작 |

---

## 14. 비목표 (Out of Scope)

본 레이어가 **하지 않는** 것을 명시한다. 추후 scope creep 방지용.

- LLM 호출, 프롬프트 템플릿화, 답변 생성
- 청킹·임베딩·인덱스 빌드 (이건 `RAG_DB_build/` 책임)
- 룰 평가, 최적화 알고리즘 (이건 agent 책임)
- 사용자 인증·권한 관리
- 분산 배포 (single-process 가정)
- 자동 한국어 번역

---

> **다음 액션**: 위 12절(열린 결정)의 8개 항목에 대한 회신을 받으면
> v0.2 시그니처 스켈레톤(`types.py`, `config.py`, `backends/base.py`)을
> 작성하겠다. 그 시점부터 코드를 쓰기 시작한다.
