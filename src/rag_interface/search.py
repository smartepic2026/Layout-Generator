"""search — 에이전트가 직접 부르는 메인 함수 (ARCHITECTURE.md §3.3).

라우팅 + 검색 + 신뢰도 + fallback 을 한 흐름으로 묶는다. 에이전트가 이
레이어에서 import 하는 거의 유일한 이름은 `search` 하나다.

공개 함수:
    search(query: SearchQuery, *, trace_id=None, audit_path=None) -> SearchResult

내부 흐름 (§3.3):
    profile YAML 로드 → 컬렉션·필터 결정 → backend 호출 → confidence 계산
    → 임계값 미달이면 fallback 발동 → Citation 으로 감싸기(=Chunk 그대로)
    → audit 기록 → return.

rag_validator 연동 (2026-05-29):
    `search` 는 `Callable[[SearchQuery], SearchResult]` 시그니처를 만족하므로
    `make_rag_validator(rag_search=search)` 로 그대로 주입 가능하다.
    SearchQuery.calling_agent 가 프로필을 선택한다.
"""
from __future__ import annotations

import time
import uuid
from functools import lru_cache
from pathlib import Path

import yaml

from .backend import TfidfBackend
from .models import SearchQuery, SearchResult
from .observability import append_audit, log_search


_PROFILE_DIR = Path(__file__).resolve().parent / "profiles"

# agent 이름 → profile 파일. 미등록 agent 는 validation 으로 fallback.
_AGENT_TO_PROFILE = {
    "ValidationAgent": "validation.yaml",
    "DesignAgent": "design.yaml",
    "ProcessDesignAgent": "design.yaml",
    "LayoutAgent": "layout.yaml",
}
_DEFAULT_PROFILE = "validation.yaml"


@lru_cache(maxsize=8)
def _load_profile(profile_file: str) -> dict:
    """profiles/<file> YAML 로드 (캐시). 없으면 빈 dict."""
    p = _PROFILE_DIR / profile_file
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def _get_backend() -> TfidfBackend:
    """TF-IDF 백엔드 싱글턴 (DB 로딩 1회)."""
    return TfidfBackend()


def _resolve_profile(agent: str | None) -> dict:
    profile_file = _AGENT_TO_PROFILE.get(agent or "", _DEFAULT_PROFILE)
    return _load_profile(profile_file)


def _primary_collection(query: SearchQuery, profile: dict) -> str:
    """질의에 쓸 컬렉션 결정.

    query.collection 이 'both' 가 아니면 그대로 우선.
    'both' 면 profile 의 첫 컬렉션(최고 weight) 사용.
    """
    if query.collection and query.collection != "both":
        return query.collection
    cols = profile.get("collections") or [{"name": "regulatory_docs"}]
    return cols[0]["name"]


def _confidence_status(avg_sim: float, n_hits: int, min_threshold: float) -> str:
    """avg_similarity 기반 상태 판정."""
    if n_hits == 0:
        return "insufficient_evidence"
    if avg_sim < min_threshold:
        return "low_confidence"
    return "ok"


def search(
    query: SearchQuery,
    *,
    trace_id: str | None = None,
    audit_path: str | Path | None = None,
    verbose: bool = False,
) -> SearchResult:
    """에이전트용 단일 검색 진입점.

    Args:
        query: 검색 요청 (text, collection, top_k, metadata_filter,
            calling_agent, context_tags).
        trace_id: 추적 ID. None 이면 자동 생성.
        audit_path: 지정 시 해당 경로에 JSONL audit append.
        verbose: True 면 stdout 로 검색 1줄 로그.

    Returns:
        SearchResult (chunks, avg_similarity, status, warning, ...).
    """
    t0 = time.perf_counter()
    trace_id = trace_id or uuid.uuid4().hex[:12]

    profile = _resolve_profile(query.calling_agent)
    conf = profile.get("confidence", {})
    min_threshold = float(conf.get("min_threshold", 0.10))
    fallback = profile.get("fallback", {})
    top_k = query.top_k or int(profile.get("top_k_default", 5))

    collection = _primary_collection(query, profile)
    backend = _get_backend()

    where = dict(query.metadata_filter) if query.metadata_filter else None

    # 1차 질의.
    chunks = backend.search(query.text, collection, top_k, where)
    warning: str | None = None

    avg_sim = (
        sum(c.similarity for c in chunks) / len(chunks) if chunks else 0.0
    )
    status = _confidence_status(avg_sim, len(chunks), min_threshold)

    # fallback — low_confidence 시 source 필터 해제 후 재질의 (broaden_filter).
    if (
        status == "low_confidence"
        and fallback.get("on_low_confidence") == "broaden_filter"
        and where is not None
    ):
        broadened = backend.search(query.text, collection, top_k, where=None)
        if broadened:
            b_avg = sum(c.similarity for c in broadened) / len(broadened)
            if b_avg > avg_sim:
                chunks = broadened
                avg_sim = b_avg
                status = _confidence_status(b_avg, len(chunks), min_threshold)
                warning = "broaden_filter: source 필터를 해제해 재질의함."

    # fallback — empty 시 정책. on_empty=warn 이면 insufficient_evidence 반환
    # (raise 는 validator loop 를 깨므로 의도적으로 채택하지 않음).
    if not chunks:
        status = "insufficient_evidence"
        warning = warning or "no hits — KB 에서 근거를 찾지 못함."
        if fallback.get("on_empty") == "raise":
            # 프로필이 명시적으로 raise 를 원하면 존중 (기본 프로필은 warn).
            raise LookupError(
                f"RAG search empty for query={query.text!r} "
                f"collection={collection}"
            )

    # min_similarity 후필터 (query 가 명시한 경우).
    if query.min_similarity is not None:
        chunks = [c for c in chunks if c.similarity >= query.min_similarity]
        avg_sim = (
            sum(c.similarity for c in chunks) / len(chunks) if chunks else 0.0
        )

    duration_ms = (time.perf_counter() - t0) * 1000.0

    result = SearchResult(
        query=query,
        chunks=chunks,
        total_hits=len(chunks),
        avg_similarity=avg_sim,
        status=status,
        warning=warning,
        search_duration_ms=duration_ms,
    )

    if verbose:
        log_search(result, trace_id=trace_id)
    if audit_path is not None:
        append_audit(result, audit_path, trace_id=trace_id)

    return result
