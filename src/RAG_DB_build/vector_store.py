"""
vector_store.py — Chroma-equivalent persistent vector store
=============================================================
Notion 가이드 (Phase 3-1)의 코드 구조를 그대로 따르되, 외부 네트워크 차단으로
chromadb / sentence-transformers 설치가 불가능한 환경이라 동일 인터페이스를
순수 Python(NumPy)으로 재구현합니다.

대응 매핑 (Notion → 본 모듈)
----------------------------
* chromadb.PersistentClient(path=...)          -> PersistentClient(path=...)
* client.get_or_create_collection(name, ...)   -> client.get_or_create_collection(...)
* collection.add(documents, metadatas, ids)    -> collection.add(...)
* collection.query(query_texts, n_results,     -> collection.query(...)
                   where=...)
* Squared L2 distance (정규화 벡터 기본 거리)  -> 동일 (정규화된 TF-IDF 벡터)

임베딩
------
Notion 문서는 Chroma 기본인 all-MiniLM-L6-v2(384-d, L2 정규화)를 사용하지만,
오프라인 환경에서는 모델 다운로드가 불가능하므로 **TF-IDF + L2 정규화** 벡터로
대체합니다. 정규화된 벡터에서 Squared L2 ↔ Cosine 관계
( d_L2^2 = 2(1 - cosθ) )가 동일하게 성립하므로 평가 지표 정의 자체는
원래 가이드와 호환됩니다.
"""

from __future__ import annotations
import json
import math
import os
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


# ----------------------------- Tokenization --------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-_/\.]*|\d+(?:\.\d+)?")

_STOP = set("""
a an the of and or to in on at for by with from is are was were be been being
this that these those it its as if then than so such not no nor do does did
have has had into out over under up down off too very can will would could should
may might must about between within without per via vs etc using used use
""".split())


def tokenize(text: str) -> List[str]:
    """간단한 도메인-친화적 토크나이저.
    - 영문/숫자/하이픈/언더스코어/슬래시/마침표를 보존 (예: '21 CFR 211.67', 'BR-101')
    - 짧은 stop word 제거, 소문자화
    """
    if not text:
        return []
    out = []
    for m in _TOKEN_RE.findall(text.lower()):
        if m in _STOP:
            continue
        if len(m) < 2 and not m.isdigit():
            continue
        out.append(m)
    return out


# ----------------------------- Embedder ------------------------------------

class TfidfEmbedder:
    """TF-IDF + L2 정규화 임베더.

    Notion 가이드에 명시된 all-MiniLM-L6-v2(정규화)와 동일한 후처리 규약을 따른다.
    -> 거리: Squared L2 / 유사도: Cosine 변환식 그대로 사용 가능.
    """

    def __init__(self, max_features: int = 30000, min_df: int = 1):
        self.max_features = max_features
        self.min_df = min_df
        self.vocab: Dict[str, int] = {}
        self.idf: np.ndarray = np.zeros(0, dtype=np.float32)

    def fit(self, corpus: Iterable[str]) -> None:
        df: Dict[str, int] = {}
        n_docs = 0
        for text in corpus:
            n_docs += 1
            seen = set(tokenize(text))
            for tok in seen:
                df[tok] = df.get(tok, 0) + 1
        # min_df / top-N 어휘
        items = [(t, c) for t, c in df.items() if c >= self.min_df]
        items.sort(key=lambda x: (-x[1], x[0]))
        items = items[: self.max_features]
        self.vocab = {t: i for i, (t, _) in enumerate(items)}
        idf = np.zeros(len(items), dtype=np.float32)
        for t, c in items:
            # smooth idf
            idf[self.vocab[t]] = math.log((1 + n_docs) / (1 + c)) + 1.0
        self.idf = idf

    def transform(self, text: str) -> np.ndarray:
        v = np.zeros(len(self.vocab), dtype=np.float32)
        if not self.vocab:
            return v
        toks = tokenize(text)
        if not toks:
            return v
        tf: Dict[int, int] = {}
        for t in toks:
            idx = self.vocab.get(t)
            if idx is not None:
                tf[idx] = tf.get(idx, 0) + 1
        if not tf:
            return v
        max_tf = max(tf.values())
        for idx, c in tf.items():
            # sublinear-ish: 0.5 + 0.5 * tf/max_tf
            v[idx] = (0.5 + 0.5 * c / max_tf) * self.idf[idx]
        n = float(np.linalg.norm(v))
        if n > 0:
            v /= n
        return v

    # serialize
    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump({"vocab": self.vocab, "idf": self.idf,
                         "max_features": self.max_features,
                         "min_df": self.min_df}, f)

    @classmethod
    def load(cls, path: Path) -> "TfidfEmbedder":
        with open(path, "rb") as f:
            d = pickle.load(f)
        e = cls(max_features=d["max_features"], min_df=d["min_df"])
        e.vocab = d["vocab"]
        e.idf = d["idf"]
        return e


# ----------------------------- Collection ----------------------------------

@dataclass
class Collection:
    name: str
    metadata: Dict[str, Any]
    documents: List[str] = field(default_factory=list)
    metadatas: List[Dict[str, Any]] = field(default_factory=list)
    ids: List[str] = field(default_factory=list)
    embeddings: Optional[np.ndarray] = None  # (N, D) after build

    def count(self) -> int:
        return len(self.documents)

    def add(self, documents: List[str], metadatas: List[Dict[str, Any]],
            ids: List[str]) -> None:
        assert len(documents) == len(metadatas) == len(ids)
        self.documents.extend(documents)
        self.metadatas.extend(metadatas)
        self.ids.extend(ids)
        # 임베딩은 일괄 build 단계에서 채움

    def build(self, embedder: TfidfEmbedder) -> None:
        if not self.documents:
            self.embeddings = np.zeros((0, max(1, len(embedder.vocab))),
                                       dtype=np.float32)
            return
        rows = [embedder.transform(d) for d in self.documents]
        self.embeddings = np.vstack(rows).astype(np.float32)

    def _filter_indices(self, where: Optional[Dict[str, Any]]) -> np.ndarray:
        n = len(self.documents)
        if not where:
            return np.arange(n)
        mask = np.ones(n, dtype=bool)
        for k, v in where.items():
            for i in range(n):
                if mask[i] and self.metadatas[i].get(k) != v:
                    mask[i] = False
        return np.where(mask)[0]

    def query(self, query_texts: List[str], n_results: int = 5,
              where: Optional[Dict[str, Any]] = None,
              embedder: Optional[TfidfEmbedder] = None) -> Dict[str, List[List[Any]]]:
        assert embedder is not None, "embedder required (Chroma는 내부적으로 자동)"
        out_docs, out_metas, out_ids, out_dists = [], [], [], []
        for q in query_texts:
            qv = embedder.transform(q)
            cand = self._filter_indices(where)
            if cand.size == 0 or self.embeddings is None or self.embeddings.shape[0] == 0:
                out_docs.append([]); out_metas.append([]); out_ids.append([]); out_dists.append([])
                continue
            E = self.embeddings[cand]               # (M, D)
            # Squared L2 distance for L2-normalized vectors: 2 - 2*cos
            sims = E @ qv                            # (M,)
            dists = 2.0 - 2.0 * sims
            k = min(n_results, len(cand))
            order = np.argsort(dists)[:k]
            sel = cand[order]
            out_docs.append([self.documents[i] for i in sel])
            out_metas.append([self.metadatas[i] for i in sel])
            out_ids.append([self.ids[i] for i in sel])
            out_dists.append([float(dists[o]) for o in order])
        return {"documents": out_docs, "metadatas": out_metas,
                "ids": out_ids, "distances": out_dists}


# ----------------------------- Client --------------------------------------

class PersistentClient:
    """Chroma의 PersistentClient와 동일한 시그니처."""
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.collections: Dict[str, Collection] = {}
        self.embedder = TfidfEmbedder()
        self._load_if_exists()

    def get_or_create_collection(self, name: str,
                                 metadata: Optional[Dict[str, Any]] = None
                                 ) -> Collection:
        if name not in self.collections:
            self.collections[name] = Collection(name=name,
                                                metadata=metadata or {})
        return self.collections[name]

    # build embedder over both collections together (shared vocab/idf)
    def build_embeddings(self) -> None:
        corpus: List[str] = []
        for c in self.collections.values():
            corpus.extend(c.documents)
        self.embedder.fit(corpus)
        for c in self.collections.values():
            c.build(self.embedder)

    def persist(self) -> None:
        meta = {
            "collections": {
                name: {
                    "metadata": c.metadata,
                    "ids": c.ids,
                    "metadatas": c.metadatas,
                } for name, c in self.collections.items()
            }
        }
        with open(self.path / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        for name, c in self.collections.items():
            with open(self.path / f"{name}.docs.json", "w", encoding="utf-8") as f:
                json.dump(c.documents, f, ensure_ascii=False)
            if c.embeddings is not None:
                np.save(self.path / f"{name}.emb.npy", c.embeddings)
        self.embedder.save(self.path / "embedder.pkl")

    def _load_if_exists(self) -> None:
        man = self.path / "manifest.json"
        if not man.exists():
            return
        with open(man, "r", encoding="utf-8") as f:
            meta = json.load(f)
        for name, info in meta["collections"].items():
            c = Collection(name=name, metadata=info["metadata"])
            c.ids = info["ids"]
            c.metadatas = info["metadatas"]
            docp = self.path / f"{name}.docs.json"
            if docp.exists():
                with open(docp, "r", encoding="utf-8") as f:
                    c.documents = json.load(f)
            embp = self.path / f"{name}.emb.npy"
            if embp.exists():
                c.embeddings = np.load(embp)
            self.collections[name] = c
        emb_path = self.path / "embedder.pkl"
        if emb_path.exists():
            self.embedder = TfidfEmbedder.load(emb_path)


# Convenience: mirrors Notion code's structure exactly
def init_db(path: str = "/data/chroma"):
    """Notion STEP 3-1 — Chroma DB 초기화 (대체 구현)."""
    client = PersistentClient(path=path)
    design_collection = client.get_or_create_collection(
        name="design_standards",
        metadata={"description": "ISPE, EPAR, NNE 설계 기준 — Design Agent용"}
    )
    regulatory_collection = client.get_or_create_collection(
        name="regulatory_docs",
        metadata={"description": "FDA, EMA, ICH 규정 — Validation Agent용"}
    )
    print("Chroma DB 초기화 완료 (TF-IDF backend)")
    return client, design_collection, regulatory_collection
