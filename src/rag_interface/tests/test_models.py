"""Unit tests for rag_interface.models.

테스트 실행:
    python -m rag_interface.tests.test_models
또는
    python rag_interface/tests/test_models.py

pytest 가 있다면 그것으로도 동작한다 (assert 기반).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# rag_interface 가 sys.path 에 없을 때를 대비.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rag_interface.models import Chunk, SearchQuery, SearchResult  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_chunk(**overrides) -> Chunk:
    """기본 Chunk를 만들고 overrides로 필드 일부만 덮어쓴다."""
    base = dict(
        chunk_id="EU_GMP_Annex_1_2022_chunk_17",
        text="Grade A zones shall be classified as ISO 5 (at rest).",
        source="EU_GMP_Annex_1_2022",
        section="4.29",
        page=17,
        similarity=0.83,
        metadata={
            "year": 2022,
            "jurisdiction": "EMA",
            "doc_type": "regulatory",
            "reliability": "high",
        },
        collection="regulatory_docs",
    )
    base.update(overrides)
    return Chunk(**base)


# ---------------------------------------------------------------------------
# Test 1 — Chunk 생성 및 citation_string 자동 생성
# ---------------------------------------------------------------------------

def test_chunk_creation_and_citation_string() -> None:
    """Chunk 생성과 citation_string의 자동 포맷팅을 검증."""
    c = _make_chunk()

    # 필드 보존
    assert c.chunk_id == "EU_GMP_Annex_1_2022_chunk_17"
    assert c.source == "EU_GMP_Annex_1_2022"
    assert c.section == "4.29"
    assert c.page == 17
    assert c.collection == "regulatory_docs"

    # 핵심: citation_string 포맷
    expected = "EU GMP Annex 1 (2022), §4.29, p.17"
    assert c.citation_string == expected, (
        f"citation_string mismatch.\n  expected: {expected!r}\n"
        f"  got:      {c.citation_string!r}"
    )

    # is_regulatory
    assert c.is_regulatory is True

    # section/page 없을 때
    c2 = _make_chunk(section=None, page=None)
    assert c2.citation_string == "EU GMP Annex 1 (2022)"

    # 연도 없을 때 (괄호 자체가 사라져야 함)
    c3 = _make_chunk(metadata={"jurisdiction": "EMA", "doc_type": "regulatory"})
    assert "(" not in c3.citation_string, c3.citation_string

    # collection이 design 이지만 metadata.doc_type가 regulatory 인 경우
    c4 = _make_chunk(collection="design_standards",
                     metadata={"year": 2022, "doc_type": "regulatory"})
    assert c4.is_regulatory is True

    # design_standard 청크는 is_regulatory False
    c5 = _make_chunk(
        source="ISPE_Baseline_Vol6_2023",
        collection="design_standards",
        metadata={"year": 2023, "doc_type": "design_standard"},
    )
    assert c5.is_regulatory is False
    assert c5.citation_string == "ISPE Baseline Vol6 (2023), §4.29, p.17"

    # frozen 검증
    from dataclasses import FrozenInstanceError
    try:
        c.text = "mutated"  # type: ignore[misc]
    except FrozenInstanceError:
        pass  # expected
    except Exception as e:  # pragma: no cover
        raise AssertionError(f"expected FrozenInstanceError, got {type(e).__name__}: {e}")
    else:
        raise AssertionError("frozen=True 인데도 필드 변경이 허용됨")

    print("OK  test_chunk_creation_and_citation_string")


# ---------------------------------------------------------------------------
# Test 2 — confidence_level 계산
# ---------------------------------------------------------------------------

def test_confidence_level_thresholds() -> None:
    """similarity → confidence_level 매핑이 D1 디폴트에 맞는지."""
    cases = [
        (1.00, "high"),
        (0.95, "high"),
        (0.50, "high"),    # boundary high
        (0.499, "medium"),
        (0.35, "medium"),
        (0.20, "medium"),  # boundary medium
        (0.199, "low"),
        (0.05, "low"),
        (0.00, "low"),
    ]
    failures = []
    for sim, expected in cases:
        got = _make_chunk(similarity=sim).confidence_level
        if got != expected:
            failures.append((sim, expected, got))
    if failures:
        msg = "\n".join(
            f"  similarity={s}: expected {e!r}, got {g!r}"
            for s, e, g in failures
        )
        raise AssertionError("confidence_level mismatches:\n" + msg)
    print(f"OK  test_confidence_level_thresholds  ({len(cases)} cases)")


# ---------------------------------------------------------------------------
# Test 3 — to_context_string() 육안 검증 + 부수 메서드 검증
# ---------------------------------------------------------------------------

def test_to_context_string_visual() -> None:
    """SearchResult.to_context_string() 출력의 LLM-적합성을 육안 검증."""
    chunks = [
        _make_chunk(
            chunk_id="EU_GMP_Annex_1_2022_chunk_17",
            text=(
                "Grade A is the critical zone for high-risk operations such "
                "as filling and aseptic connections. It shall be supplied "
                "with HEPA-filtered air at the first work position with "
                "particle counts corresponding to ISO 5."
            ),
            section="4.29",
            page=17,
            similarity=0.83,
        ),
        _make_chunk(
            chunk_id="ISO_14644_1_2015_chunk_3",
            text=(
                "ISO Class 5 corresponds to a maximum allowed concentration "
                "of 3,520 particles per cubic metre at >= 0.5 µm under at-rest "
                "conditions."
            ),
            source="ISO_14644_1_2015",
            section="4.2",
            page=8,
            similarity=0.62,
            metadata={
                "year": 2015, "jurisdiction": "ISO",
                "doc_type": "regulatory", "reliability": "high",
            },
        ),
        _make_chunk(
            chunk_id="WHO_TRS_Annex_2_2022_chunk_5",
            text=(
                "Aseptic processing requires validated environmental "
                "monitoring covering viable and non-viable particulates."
            ),
            source="WHO_TRS_Annex_2_2022",
            section=None,
            page=42,
            similarity=0.18,
            metadata={
                "year": 2022, "jurisdiction": "WHO",
                "doc_type": "regulatory", "reliability": "high",
            },
        ),
    ]

    q = SearchQuery(
        text="aseptic grade A particle limits",
        collection="regulatory_docs",
        top_k=5,
        calling_agent="ValidationAgent",
        context_tags=["aseptic", "grade_a"],
    )
    avg = sum(c.similarity for c in chunks) / len(chunks)
    result = SearchResult(
        query=q,
        chunks=chunks,
        total_hits=len(chunks),
        avg_similarity=avg,
        status="ok",
        warning=None,
        search_duration_ms=12.34,
        timestamp=datetime(2026, 5, 12, 10, 30, 0),
    )

    out = result.to_context_string()

    # 육안 검증용 출력 -- 실제 형식을 사람이 보고 LLM-적합성을 판단.
    print("\n" + "=" * 72)
    print("[VISUAL CHECK] SearchResult.to_context_string() ↓")
    print("=" * 72)
    print(out)
    print("=" * 72)

    # 구조 검증 (육안 외)
    assert "Retrieved context" in out
    assert "[1] EU GMP Annex 1 (2022), §4.29, p.17" in out
    assert "[2] ISO 14644 1 (2015), §4.2, p.8" in out
    assert "[3] WHO TRS Annex 2 (2022), p.42" in out  # section 없는 경우
    assert "confidence=high" in out
    assert "confidence=low" in out

    # filter_by_confidence
    # similarity 0.83 (high), 0.62 (high), 0.18 (low)
    high_only = result.filter_by_confidence("high")
    assert len(high_only.chunks) == 2, [c.similarity for c in high_only.chunks]
    assert all(c.confidence_level == "high" for c in high_only.chunks)
    assert high_only.total_hits == 2
    assert abs(high_only.avg_similarity - (0.83 + 0.62) / 2) < 1e-9

    medium_plus = result.filter_by_confidence("medium")
    # 0.18은 medium 미만이므로 제외 → 2개
    assert len(medium_plus.chunks) == 2

    low_plus = result.filter_by_confidence("low")
    assert len(low_plus.chunks) == 3

    # to_citation_list — 중복 없음, 순서 유지
    cites = result.to_citation_list()
    assert cites == [
        "EU GMP Annex 1 (2022), §4.29, p.17",
        "ISO 14644 1 (2015), §4.2, p.8",
        "WHO TRS Annex 2 (2022), p.42",
    ], cites

    # 빈 결과
    empty = SearchResult(
        query=q, chunks=[], total_hits=0, avg_similarity=0.0,
        status="insufficient_evidence", warning="no hits",
        search_duration_ms=2.1,
    )
    assert empty.to_context_string() == "[No relevant context retrieved.]"

    print("OK  test_to_context_string_visual")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_chunk_creation_and_citation_string()
    test_confidence_level_thresholds()
    test_to_context_string_visual()
    print("\nAll model tests passed.")
