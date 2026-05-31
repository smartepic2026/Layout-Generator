"""observability — 호출 로그·audit 기록 (ARCHITECTURE.md §3.4).

함수 두 개로 한정 (메트릭 집계·익스포터·트레이싱 없음):
    log_search(result)        — stdout 한 줄 요약.
    append_audit(result, path) — JSONL 한 줄 append.

GMP 추적성·논문 재현성 양쪽이 모든 검색 기록을 요구한다. trace_id 는
search.py 에서 부여하고 여기서는 받기만 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import SearchResult


def log_search(result: SearchResult, *, trace_id: str | None = None) -> None:
    """검색 1건을 stdout 한 줄로 요약 출력."""
    q = result.query
    print(
        f"[rag_search]"
        f" trace={trace_id or '-'}"
        f" agent={q.calling_agent or '-'}"
        f" collection={q.collection}"
        f" hits={len(result.chunks)}"
        f" avg_sim={result.avg_similarity:.3f}"
        f" status={result.status}"
        f" dur={result.search_duration_ms:.1f}ms"
    )


def append_audit(
    result: SearchResult,
    path: str | Path,
    *,
    trace_id: str | None = None,
) -> None:
    """검색 1건을 JSONL 한 줄로 audit 파일에 append."""
    q = result.query
    record = {
        "trace_id": trace_id,
        "timestamp": result.timestamp.isoformat(),
        "agent": q.calling_agent,
        "query_text": q.text,
        "collection": q.collection,
        "metadata_filter": q.metadata_filter,
        "top_k": q.top_k,
        "hits": len(result.chunks),
        "avg_similarity": round(result.avg_similarity, 4),
        "status": result.status,
        "warning": result.warning,
        "duration_ms": round(result.search_duration_ms, 2),
        "citations": result.to_citation_list(),
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
