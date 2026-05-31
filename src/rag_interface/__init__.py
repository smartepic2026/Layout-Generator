"""rag_interface — agent-facing RAG search layer.

See ARCHITECTURE.md for the design overview. 공개 표면은 의도적으로 작다:
    models   — Chunk / SearchQuery / SearchResult 데이터 클래스
    search   — 에이전트가 부르는 단일 진입점 search(query)
    backend  — 벡터 DB 래핑 (보통 직접 쓰지 않음)
    observability — log_search / append_audit
"""
from rag_interface.models import (
    Chunk,
    SearchQuery,
    SearchResult,
)
from rag_interface.search import search

__all__ = ["Chunk", "SearchQuery", "SearchResult", "search"]
