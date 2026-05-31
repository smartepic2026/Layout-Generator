"""Data models for the rag_interface layer.

이 파일은 rag_interface가 주고받는 모든 데이터 구조를 정의한다.
ARCHITECTURE.md §3.1의 원칙대로 **로직은 두지 않는다** — IO·검증·변환 없음.
오직 데이터 클래스와, 그 데이터에서 곧장 파생되는 표현용 property만.

Public types:
    Chunk        — RAG에서 반환되는 단일 청크.
    SearchQuery  — 검색 요청.
    SearchResult — 검색 결과 컨테이너.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


# ---------------------------------------------------------------------------
# Type aliases — 호출부 시그니처에 의미를 부여하기 위한 alias.
# ---------------------------------------------------------------------------

CollectionName = Literal["regulatory_docs", "design_standards"]
SearchScope = Literal["regulatory_docs", "design_standards", "both"]
ConfidenceLevel = Literal["high", "medium", "low"]
SearchStatus = Literal["ok", "low_confidence", "insufficient_evidence"]


# ---------------------------------------------------------------------------
# Confidence thresholds — D1 결정의 디폴트.
# similarity는 코사인 (0~1). 향후 MiniLM 백엔드로 교체되면 이 값들의
# 자연스러운 분포가 상향되며, 그에 맞춰 임계값 재조정이 필요할 수 있음.
# ---------------------------------------------------------------------------

_HIGH_THRESHOLD: float = 0.5
_MEDIUM_THRESHOLD: float = 0.2


# ---------------------------------------------------------------------------
# Chunk
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Chunk:
    """RAG 검색에서 반환되는 단일 청크.

    Attributes:
        chunk_id: 고유 식별자 (예: "EU_GMP_Annex_1_2022_chunk_17").
        text: 청크 본문 텍스트.
        source: 원본 문서 식별자 (예: "EU_GMP_Annex_1_2022").
        section: 문서 내 섹션 번호 (예: "4.29"). 없으면 None.
        page: 문서 내 페이지 번호. 없으면 None.
        similarity: 쿼리와의 코사인 유사도, 0~1 범위.
        metadata: 부가 메타데이터 (jurisdiction, year, doc_type,
            reliability 등). 키는 RAG_DB_build의 스키마와 일치한다.
        collection: 청크가 속한 컬렉션 이름.

    Example:
        >>> chunk = Chunk(
        ...     chunk_id="EU_GMP_Annex_1_2022_chunk_17",
        ...     text="Grade A zones shall be ...",
        ...     source="EU_GMP_Annex_1_2022",
        ...     section="4.29",
        ...     page=17,
        ...     similarity=0.83,
        ...     metadata={"year": 2022, "jurisdiction": "EMA",
        ...               "doc_type": "regulatory"},
        ...     collection="regulatory_docs",
        ... )
        >>> chunk.citation_string
        'EU GMP Annex 1 (2022), §4.29, p.17'
        >>> chunk.confidence_level
        'high'
        >>> chunk.is_regulatory
        True
    """

    chunk_id: str
    text: str
    source: str
    section: str | None
    page: int | None
    similarity: float
    metadata: dict
    collection: str

    # ---- 표현용 property ----------------------------------------------------

    @property
    def citation_string(self) -> str:
        """인용 가능 형태의 문자열을 자동 생성.

        Format:
            "{Display Name} ({Year})[, §{section}][, p.{page}]"

        Display Name은 source의 underscore를 공백으로 치환한 결과이며,
        끝의 4자리 연도는 metadata.year 로 대체하기 위해 떼어낸다.

        Returns:
            인용 표기 문자열. 연도/섹션/페이지가 없으면 해당 부분 생략.
        """
        parts = self.source.split("_")
        if parts and parts[-1].isdigit() and len(parts[-1]) == 4:
            parts = parts[:-1]
        display = " ".join(p for p in parts if p).strip()

        year = self.metadata.get("year")
        head = f"{display} ({year})" if year else display

        tail = ""
        if self.section:
            tail += f", §{self.section}"
        if self.page is not None:
            tail += f", p.{self.page}"
        return head + tail

    @property
    def is_regulatory(self) -> bool:
        """규제 문서 청크인지 여부.

        컬렉션 이름이 "regulatory_docs" 이거나 metadata.doc_type 이
        "regulatory" 이면 True.
        """
        return (
            self.collection == "regulatory_docs"
            or self.metadata.get("doc_type") == "regulatory"
        )

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """similarity 기반 신뢰도 등급.

        Thresholds (D1 디폴트):
            high   : similarity >= 0.5
            medium : 0.2 <= similarity < 0.5
            low    : similarity <  0.2
        """
        if self.similarity >= _HIGH_THRESHOLD:
            return "high"
        if self.similarity >= _MEDIUM_THRESHOLD:
            return "medium"
        return "low"


# ---------------------------------------------------------------------------
# SearchQuery
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SearchQuery:
    """검색 요청을 표현하는 데이터 클래스.

    Attributes:
        text: 검색 쿼리 문자열.
        collection: 조회 대상 컬렉션. "both"는 양쪽 모두.
        top_k: 반환할 최대 hit 수.
        metadata_filter: where 절에 적용할 메타데이터 필터 (예:
            {"jurisdiction": "EMA"}).
        min_similarity: 이 값 미만의 hit는 결과에서 제외 (None이면 비활성).
        calling_agent: 호출자 식별자 (로깅·audit용).
        context_tags: 도메인 컨텍스트 태그 (라우팅 보조용).

    Example:
        >>> q = SearchQuery(
        ...     text="aseptic processing grade A",
        ...     collection="regulatory_docs",
        ...     top_k=5,
        ...     calling_agent="ValidationAgent",
        ...     context_tags=["aseptic", "grade_a"],
        ... )
        >>> q.top_k
        5
        >>> q.collection
        'regulatory_docs'
    """

    text: str
    collection: SearchScope = "both"
    top_k: int = 5
    metadata_filter: dict | None = None
    min_similarity: float | None = None
    calling_agent: str | None = None
    context_tags: list[str] | None = None


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SearchResult:
    """검색 결과 컨테이너.

    Attributes:
        query: 원래 검색 요청.
        chunks: 결과 청크 리스트 (similarity 내림차순).
        total_hits: 필터 적용 전 총 후보 수.
        avg_similarity: chunks의 평균 similarity. 비어있으면 0.0.
        status: 결과 상태. "ok" | "low_confidence" | "insufficient_evidence".
        warning: 사용자에게 노출할 경고 메시지 (없으면 None).
        search_duration_ms: 검색 소요 시간 (밀리초).
        timestamp: 검색 실행 시각. 미지정 시 생성 순간.

    Example:
        >>> from datetime import datetime
        >>> q = SearchQuery(text="grade A", collection="regulatory_docs")
        >>> result = SearchResult(
        ...     query=q, chunks=[], total_hits=0, avg_similarity=0.0,
        ...     status="insufficient_evidence", warning="no hits",
        ...     search_duration_ms=2.1,
        ...     timestamp=datetime(2026, 5, 12, 10, 0))
        >>> result.to_context_string()
        '[No relevant context retrieved.]'
    """

    query: SearchQuery
    chunks: list[Chunk]
    total_hits: int
    avg_similarity: float
    status: SearchStatus
    warning: str | None
    search_duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

    # ---- 변환 메서드 --------------------------------------------------------

    def to_context_string(self) -> str:
        """LLM 프롬프트에 그대로 넣을 수 있는 컨텍스트 문자열로 변환.

        각 청크는 헤더(인용 + similarity + confidence)와 본문이 함께
        표시되며, 청크 사이에 빈 줄이 들어간다. LLM이 출처를 그대로
        인용하기 좋은 포맷.

        Returns:
            여러 줄로 된 단일 문자열. 청크가 없으면 명시적 placeholder.
        """
        if not self.chunks:
            return "[No relevant context retrieved.]"
        lines: list[str] = [
            f"# Retrieved context "
            f"({len(self.chunks)} chunks, "
            f"avg_sim={self.avg_similarity:.3f}, status={self.status})"
        ]
        for i, ch in enumerate(self.chunks, start=1):
            lines.append("")
            lines.append(
                f"[{i}] {ch.citation_string}  "
                f"(similarity={ch.similarity:.3f}, "
                f"confidence={ch.confidence_level})"
            )
            lines.append(ch.text.strip())
        if self.warning:
            lines.append("")
            lines.append(f"WARNING: {self.warning}")
        return "\n".join(lines)

    def to_citation_list(self) -> list[str]:
        """인용 문자열만 추출. 중복은 제거하되 등장 순서는 유지.

        Returns:
            citation_string 문자열의 정렬-안정 unique 리스트.
        """
        seen: set[str] = set()
        out: list[str] = []
        for ch in self.chunks:
            cs = ch.citation_string
            if cs not in seen:
                seen.add(cs)
                out.append(cs)
        return out

    def filter_by_confidence(self, level: ConfidenceLevel) -> "SearchResult":
        """주어진 신뢰도 이상의 청크만 남긴 새 SearchResult 를 반환.

        Args:
            level: "high" | "medium" | "low" 중 최소 기준선.
                "medium"이면 medium·high가 포함되고 low는 제외.

        Returns:
            필터된 청크만 담은 새 SearchResult. 원본은 변경되지 않음
            (frozen 유지).
        """
        rank = {"low": 0, "medium": 1, "high": 2}
        threshold = rank[level]
        filtered = [
            c for c in self.chunks
            if rank[c.confidence_level] >= threshold
        ]
        new_avg = (
            sum(c.similarity for c in filtered) / len(filtered)
            if filtered else 0.0
        )
        return SearchResult(
            query=self.query,
            chunks=filtered,
            total_hits=len(filtered),
            avg_similarity=new_avg,
            status=self.status,
            warning=self.warning,
            search_duration_ms=self.search_duration_ms,
            timestamp=self.timestamp,
        )
