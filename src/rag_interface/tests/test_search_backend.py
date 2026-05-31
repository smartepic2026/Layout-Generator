"""rag_interface backend + search end-to-end 테스트.

실제 RAG_DB_build/data 의 TF-IDF DB 로 검증한다. DB 가 없으면 skip.

실행:
    python -m rag_interface.tests.test_search_backend
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rag_interface.backend import TfidfBackend, _distance_to_similarity  # noqa: E402
from rag_interface.models import SearchQuery  # noqa: E402
from rag_interface import search  # noqa: E402


def _db_available() -> bool:
    return (_ROOT / "RAG_DB_build" / "data" / "manifest.json").exists()


# ---------------------------------------------------------------------------
# backend
# ---------------------------------------------------------------------------

def test_distance_to_similarity():
    assert _distance_to_similarity(0.0) == 1.0
    assert _distance_to_similarity(2.0) == 0.0
    # 음수 방지
    assert _distance_to_similarity(3.0) == 0.0
    assert abs(_distance_to_similarity(1.0) - 0.5) < 1e-9
    print("OK  test_distance_to_similarity")


def test_backend_loads_collections():
    if not _db_available():
        print("SKIP test_backend_loads_collections (no DB)")
        return
    b = TfidfBackend()
    assert "regulatory_docs" in b.collection_names
    assert "design_standards" in b.collection_names
    print("OK  test_backend_loads_collections")


def test_backend_single_source_query():
    if not _db_available():
        print("SKIP test_backend_single_source_query")
        return
    b = TfidfBackend()
    chunks = b.search(
        "cleanroom differential pressure", "regulatory_docs", 3,
        where={"source": "EU_GMP_Annex1_2022"},
    )
    assert all(c.source == "EU_GMP_Annex1_2022" for c in chunks)
    # similarity 내림차순
    sims = [c.similarity for c in chunks]
    assert sims == sorted(sims, reverse=True)
    print("OK  test_backend_single_source_query")


def test_backend_source_list_fanout_merge():
    """source list 면 여러 source 가 섞여 나오고 top_k 로 잘림."""
    if not _db_available():
        print("SKIP test_backend_source_list_fanout_merge")
        return
    b = TfidfBackend()
    chunks = b.search(
        "cleanroom Grade classification", "regulatory_docs", 5,
        where={"source": ["EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022"]},
    )
    assert len(chunks) <= 5
    srcs = {c.source for c in chunks}
    # 두 source 중 하나 이상 (보통 둘 다)
    assert srcs.issubset({"EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022"})
    sims = [c.similarity for c in chunks]
    assert sims == sorted(sims, reverse=True)
    # 중복 chunk_id 없음
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    print("OK  test_backend_source_list_fanout_merge")


def test_backend_unknown_collection_returns_empty():
    if not _db_available():
        print("SKIP test_backend_unknown_collection_returns_empty")
        return
    b = TfidfBackend()
    assert b.search("x", "nonexistent_collection", 3) == []
    print("OK  test_backend_unknown_collection_returns_empty")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_search_returns_result():
    if not _db_available():
        print("SKIP test_search_returns_result")
        return
    q = SearchQuery(
        text="aseptic processing Grade A requirement",
        collection="regulatory_docs", top_k=5,
        calling_agent="ValidationAgent",
    )
    r = search(q)
    assert r.total_hits == len(r.chunks)
    assert r.status in ("ok", "low_confidence", "insufficient_evidence")
    # 모든 chunk 가 regulatory_docs (D2: cross-collection 금지)
    assert all(c.collection == "regulatory_docs" for c in r.chunks)
    print("OK  test_search_returns_result")


def test_search_source_filter_passthrough():
    """SearchQuery.metadata_filter 가 backend 까지 전달돼 source 제한."""
    if not _db_available():
        print("SKIP test_search_source_filter_passthrough")
        return
    q = SearchQuery(
        text="differential pressure cleanroom",
        collection="regulatory_docs", top_k=5,
        metadata_filter={"source": ["EU_GMP_Annex1_2022"]},
        calling_agent="ValidationAgent",
    )
    r = search(q)
    # broaden_filter fallback 가 발동하지 않은 경우 source 제한 유지.
    # 발동 시 warning 에 broaden 표시. 둘 중 하나는 성립.
    if r.warning and "broaden" in r.warning:
        pass  # fallback 발동 — 전체 컬렉션
    else:
        assert all(c.source == "EU_GMP_Annex1_2022" for c in r.chunks)
    print("OK  test_search_source_filter_passthrough")


def test_search_audit_written():
    if not _db_available():
        print("SKIP test_search_audit_written")
        return
    q = SearchQuery(
        text="gowning Grade B", collection="regulatory_docs", top_k=3,
        calling_agent="ValidationAgent",
    )
    with tempfile.TemporaryDirectory() as tmp:
        audit = Path(tmp) / "audit.jsonl"
        search(q, audit_path=audit)
        assert audit.exists()
        line = audit.read_text(encoding="utf-8").strip()
        import json
        rec = json.loads(line)
        assert rec["agent"] == "ValidationAgent"
        assert rec["collection"] == "regulatory_docs"
    print("OK  test_search_audit_written")


def test_search_as_validator_callable():
    """search 가 Callable[[SearchQuery], SearchResult] 로 rag_validator 에 주입 가능."""
    if not _db_available():
        print("SKIP test_search_as_validator_callable")
        return
    from rule_engine.validators import make_rag_validator
    validator = make_rag_validator(rag_search=search)
    assert callable(validator)
    print("OK  test_search_as_validator_callable")


if __name__ == "__main__":
    test_distance_to_similarity()
    test_backend_loads_collections()
    test_backend_single_source_query()
    test_backend_source_list_fanout_merge()
    test_backend_unknown_collection_returns_empty()
    test_search_returns_result()
    test_search_source_filter_passthrough()
    test_search_audit_written()
    test_search_as_validator_callable()
    print("\nAll rag_interface search/backend tests passed.")
