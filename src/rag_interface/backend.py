"""backend — 벡터 DB에서 청크를 꺼내오는 코드 (ARCHITECTURE.md §3.2).

한 줄 요약:
    추상 베이스 1개 + TF-IDF 구현 1개. "쿼리 + 컬렉션 + 필터" 를 받아
    "유사도 붙은 Chunk 리스트" 만 돌려준다.

무엇을 안 하는가:
    라우팅 결정 없음, confidence 계산 없음, 인용 포맷 없음 (search.py 담당).

RAG_DB_build 와의 유일한 접점:
    `RAG_DB_build/vector_store.py` 의 PersistentClient / Collection 만 import.
    `tokenize` 같은 내부 함수는 건드리지 않는다 (§5).
    DB 경로 기본값은 RAG_DB_build/data/, 환경변수 RAG_DB_PATH 로 오버라이드.

metadata_filter source list 지원 (2026-05-29):
    vector_store.Collection.query 의 where 는 단일 값 매칭만 지원하므로,
    {"source": ["A", "B"]} 같은 OR/IN 필터는 source 별로 fan-out 질의한 뒤
    similarity 로 merge·정렬하여 top_k 를 취한다.
"""
from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from .models import Chunk

# RAG_DB_build 를 import 경로에 추가 (패키지가 아니므로).
_RAG_DB_BUILD = Path(__file__).resolve().parents[1] / "RAG_DB_build"
if str(_RAG_DB_BUILD) not in sys.path:
    sys.path.insert(0, str(_RAG_DB_BUILD))

from vector_store import PersistentClient  # noqa: E402


def _default_db_path() -> Path:
    """DB 경로. 환경변수 RAG_DB_PATH 우선, 없으면 RAG_DB_build/data/."""
    env = os.environ.get("RAG_DB_PATH")
    if env:
        return Path(env)
    return _RAG_DB_BUILD / "data"


def _distance_to_similarity(distance: float) -> float:
    """Squared L2 (정규화 벡터) → cosine. d = 2(1 - cos) → cos = 1 - d/2."""
    return max(0.0, 1.0 - distance / 2.0)


class RetrievalBackend(ABC):
    """검색 백엔드 추상 베이스.

    호출부(search.py)는 이 인터페이스만 알면 되고, 실제 구현(TF-IDF, 향후
    MiniLM 등)은 교체 가능하다.
    """

    @abstractmethod
    def search(
        self,
        query_text: str,
        collection: str,
        top_k: int,
        where: dict | None = None,
    ) -> list[Chunk]:
        """쿼리 → Chunk 리스트 (similarity 내림차순)."""
        raise NotImplementedError


class TfidfBackend(RetrievalBackend):
    """TF-IDF 벡터스토어 백엔드 — RAG_DB_build/vector_store 래핑."""

    def __init__(self, db_path: str | Path | None = None):
        self._client = PersistentClient(db_path or _default_db_path())

    @property
    def collection_names(self) -> list[str]:
        return list(self._client.collections.keys())

    def _query_single(
        self,
        query_text: str,
        collection: str,
        top_k: int,
        where: dict | None,
    ) -> list[Chunk]:
        """단일 where (또는 None) 로 한 컬렉션 질의."""
        col = self._client.collections.get(collection)
        if col is None:
            return []
        res = col.query(
            query_texts=[query_text],
            n_results=top_k,
            where=where,
            embedder=self._client.embedder,
        )
        chunks: list[Chunk] = []
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        ids = res["ids"][0]
        dists = res["distances"][0]
        for doc, meta, cid, dist in zip(docs, metas, ids, dists):
            chunks.append(Chunk(
                chunk_id=cid,
                text=doc,
                source=meta.get("source", "unknown"),
                section=None,
                page=None,
                similarity=_distance_to_similarity(dist),
                metadata=meta,
                collection=collection,
            ))
        return chunks

    def search(
        self,
        query_text: str,
        collection: str,
        top_k: int,
        where: dict | None = None,
    ) -> list[Chunk]:
        """쿼리 → Chunk 리스트.

        where 의 source 가 list 면 OR/IN 시맨틱으로 source 별 fan-out 후 merge.
        그 외 where 는 vector_store 의 단일 값 매칭에 그대로 전달.
        """
        # source list fan-out 처리.
        if where and isinstance(where.get("source"), list):
            sources = where["source"]
            other = {k: v for k, v in where.items() if k != "source"}
            merged: list[Chunk] = []
            seen_ids: set[str] = set()
            for src in sources:
                sub_where = dict(other)
                sub_where["source"] = src
                for ch in self._query_single(
                    query_text, collection, top_k, sub_where
                ):
                    if ch.chunk_id not in seen_ids:
                        seen_ids.add(ch.chunk_id)
                        merged.append(ch)
            merged.sort(key=lambda c: -c.similarity)
            return merged[:top_k]

        # 단일/无 필터.
        return self._query_single(query_text, collection, top_k, where)
