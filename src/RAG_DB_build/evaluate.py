"""
evaluate.py — RAG 검색 성능 평가 (Notion STEP 3-5 기반)
==========================================================
Notion 문서의 "검색 정확도 테스트 — 방법론, 학술적 근거" 섹션에 명시된
지표를 자동 계산한다:

  * Precision@K — 상위 K 결과 중 관련 청크 비율
  * Recall@K    — 전체 관련 청크 중 K 안에 나온 비율
  * F1@K        — 두 지표의 조화평균
  * MRR         — 첫 관련 청크 순위의 역수 평균

# 평가 방법 결정 배경 (Ground Truth 부재 문제)
# ------------------------------------------------------
# Notion 가이드는 "도메인 전문가 라벨링 ground truth" 필요성을 명시하며,
# 자료 수집 단계에서는 자동 정량 평가가 어렵다고 설명한다.
# 본 평가에서는 그 한계를 우회하기 위해 **문서-수준 Pseudo Ground Truth**를
# 사용한다. 즉, 각 표준 쿼리에 대해 "관련 있다고 기대되는 source 문서들"을
# 명시한 뒤, 검색된 청크의 source가 그 집합에 포함되면 관련(positive)으로
# 본다. 청크 단위 라벨링이 없을 때 IR 평가에서 흔히 쓰는 "document-level
# relevance proxy" 방식이며, 도메인 전문가 라벨링이 완료되기 전 단계의
# 베이스라인 측정에 적합하다.
#
# 쿼리 셋은 Notion 문서의 STANDARD_QUERIES 컨셉을 따라 두 컬렉션을 균형 있게
# 커버하는 12개 쿼리로 구성했다 (regulatory 6 + design 6).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import numpy as np

# project-local
sys.path.insert(0, str(Path(__file__).parent))
from vector_store import PersistentClient


# ---------------- Standard query set + pseudo ground truth -----------------
# 각 쿼리에 대해 "정답으로 인정되는 source 문서 ID 집합" 정의.
# source ID는 ingest.py의 메타데이터 'source' 값과 일치한다.

QUERIES: List[Dict] = [
    # ── regulatory_docs ────────────────────────────────────────────────
    {
        "id": "Q01",
        "collection": "regulatory_docs",
        "query": "Annex 1 grade A B C D cleanroom classification particle limits",
        "category": "cleanroom_grade",
        "relevant_sources": {"EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022",
                             "ISO_14644_1", "ISO_14644_4"},
    },
    {
        "id": "Q02",
        "collection": "regulatory_docs",
        "query": "sterile drug products aseptic processing FDA guidance",
        "category": "aseptic",
        "relevant_sources": {"FDA_Sterile_Drug_Products_2004",
                             "EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022"},
    },
    {
        "id": "Q03",
        "collection": "regulatory_docs",
        "query": "monoclonal antibody manufacturing process validation",
        "category": "mab",
        "relevant_sources": {"FDA_mAb_Guidance_1996"},
    },
    {
        "id": "Q04",
        "collection": "regulatory_docs",
        "query": "ISO 14644 classification air cleanliness particle concentration",
        "category": "iso",
        "relevant_sources": {"ISO_14644_1", "ISO_14644_4"},
    },
    {
        "id": "Q05",
        "collection": "regulatory_docs",
        "query": "contamination control strategy pharmaceutical sterile manufacturing",
        "category": "contamination",
        "relevant_sources": {"EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022",
                             "FDA_Sterile_Drug_Products_2004"},
    },
    {
        "id": "Q06",
        "collection": "regulatory_docs",
        "query": "HVAC qualification design construction startup cleanroom",
        "category": "hvac",
        "relevant_sources": {"ISO_14644_4", "EU_GMP_Annex1_2022"},
    },

    # ── design_standards ──────────────────────────────────────────────
    {
        "id": "Q07",
        "collection": "design_standards",
        "query": "biopharmaceutical facility layout adjacency flow segregation",
        "category": "layout",
        "relevant_sources": {"ISPE_Biopharm_Facility_2005",
                             "ISPE_Baseline_Vol6_2023",
                             "Facility_Layout_GMP_Compliance",
                             "IPS_Biopharm_Layout",
                             "GMP_Facility_Layout_References"},
    },
    {
        "id": "Q08",
        "collection": "design_standards",
        "query": "personnel gowning protocol airlock transition zone",
        "category": "gowning",
        "relevant_sources": {"GMP_Gowning_TransitionZones",
                             "Biotech_Cleanroom_Guide"},
    },
    {
        "id": "Q09",
        "collection": "design_standards",
        "query": "bioreactor equipment layout clearance maintenance access",
        "category": "equipment",
        "relevant_sources": {"Equipment_Layout_Example",
                             "ISPE_Baseline_Vol6_2023",
                             "ISPE_Biopharm_Facility_2005"},
    },
    {
        "id": "Q10",
        "collection": "design_standards",
        "query": "cleanroom HVAC pressure cascade differential design biotech",
        "category": "cleanroom_design",
        "relevant_sources": {"Biotech_Cleanroom_Guide",
                             "ISPE_Biopharm_Facility_2005",
                             "ISPE_Baseline_Vol6_2023",
                             "BioPhorum_Improving_Biomfg"},
    },
    {
        "id": "Q11",
        "collection": "design_standards",
        "query": "GMP layout decision logic process flow material flow",
        "category": "decision_tree",
        "relevant_sources": {"GMP_Layout_DecisionTree_JSON",
                             "GMP_Layout_DecisionTree_MD",
                             "GMP_Layout_Logic_XLSX"},
    },
    {
        "id": "Q12",
        "collection": "design_standards",
        "query": "single use bioreactor disposable upstream downstream facility",
        "category": "single_use",
        "relevant_sources": {"BioPhorum_Improving_Biomfg",
                             "ISPE_Baseline_Vol6_2023"},
    },
]


# --------------------------- Metric functions -----------------------------

def precision_at_k(retrieved_sources: List[str], relevant: Set[str], k: int) -> float:
    if k == 0:
        return 0.0
    topk = retrieved_sources[:k]
    if not topk:
        return 0.0
    hit = sum(1 for s in topk if s in relevant)
    return hit / k


def recall_at_k(retrieved_sources: List[str], relevant_count_in_db: int,
                relevant: Set[str], k: int) -> float:
    """
    Document-level pseudo-recall: 관련 source가 top-K 안에서
    적어도 1번 등장하면 해당 source는 "회수"된 것으로 본다.
    """
    if relevant_count_in_db == 0:
        return 0.0
    topk = retrieved_sources[:k]
    recovered = len({s for s in topk if s in relevant})
    # 분모는 DB에 실제로 존재하는 관련 source 수
    return recovered / relevant_count_in_db


def f1(p: float, r: float) -> float:
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def reciprocal_rank(retrieved_sources: List[str], relevant: Set[str]) -> float:
    for i, s in enumerate(retrieved_sources):
        if s in relevant:
            return 1.0 / (i + 1)
    return 0.0


# ---------------------------- Run evaluation ------------------------------

def run(db_path: str, out_dir: str) -> Dict:
    client = PersistentClient(db_path)
    design = client.collections["design_standards"]
    regulatory = client.collections["regulatory_docs"]

    # Which sources actually exist in each collection?
    sources_in_collection: Dict[str, Set[str]] = {
        "design_standards": {m["source"] for m in design.metadatas},
        "regulatory_docs":  {m["source"] for m in regulatory.metadatas},
    }

    K_LIST = [1, 3, 5, 10]
    per_query_records = []

    for q in QUERIES:
        coll = client.collections[q["collection"]]
        res = coll.query(query_texts=[q["query"]], n_results=max(K_LIST),
                         embedder=client.embedder)
        retrieved_sources = [m["source"] for m in res["metadatas"][0]]
        retrieved_distances = res["distances"][0]
        retrieved_ids = res["ids"][0]

        # 관련 source 중 실제 DB에 존재하는 것만 카운트 (recall 분모)
        relevant_existing = q["relevant_sources"] & sources_in_collection[q["collection"]]
        record = {
            "id": q["id"], "query": q["query"], "category": q["category"],
            "collection": q["collection"],
            "relevant_sources": sorted(q["relevant_sources"]),
            "relevant_in_db": sorted(relevant_existing),
            "retrieved_top10": [
                {"rank": i+1, "source": s, "id": rid, "distance": d}
                for i, (s, rid, d) in enumerate(
                    zip(retrieved_sources, retrieved_ids, retrieved_distances))
            ],
            "metrics": {},
        }
        for K in K_LIST:
            P = precision_at_k(retrieved_sources, relevant_existing, K)
            R = recall_at_k(retrieved_sources, len(relevant_existing),
                            relevant_existing, K)
            record["metrics"][f"P@{K}"] = round(P, 4)
            record["metrics"][f"R@{K}"] = round(R, 4)
            record["metrics"][f"F1@{K}"] = round(f1(P, R), 4)
        record["metrics"]["MRR"] = round(reciprocal_rank(retrieved_sources,
                                                         relevant_existing), 4)
        record["metrics"]["mean_distance_top5"] = round(
            float(np.mean(retrieved_distances[:5])) if retrieved_distances else 0.0, 4)
        per_query_records.append(record)

    # aggregates
    def avg(key: str) -> float:
        vals = [r["metrics"][key] for r in per_query_records]
        return float(np.mean(vals)) if vals else 0.0

    summary = {
        "n_queries": len(per_query_records),
        "macro_avg": {
            **{f"P@{K}": round(avg(f"P@{K}"), 4) for K in K_LIST},
            **{f"R@{K}": round(avg(f"R@{K}"), 4) for K in K_LIST},
            **{f"F1@{K}": round(avg(f"F1@{K}"), 4) for K in K_LIST},
            "MRR": round(avg("MRR"), 4),
        },
        "by_collection": {},
    }
    for coll_name in ["design_standards", "regulatory_docs"]:
        sub = [r for r in per_query_records if r["collection"] == coll_name]
        if not sub:
            continue
        summary["by_collection"][coll_name] = {
            **{f"P@{K}": round(float(np.mean([r['metrics'][f'P@{K}'] for r in sub])), 4)
               for K in K_LIST},
            **{f"R@{K}": round(float(np.mean([r['metrics'][f'R@{K}'] for r in sub])), 4)
               for K in K_LIST},
            **{f"F1@{K}": round(float(np.mean([r['metrics'][f'F1@{K}'] for r in sub])), 4)
               for K in K_LIST},
            "MRR": round(float(np.mean([r['metrics']['MRR'] for r in sub])), 4),
            "n_queries": len(sub),
        }

    out = {"summary": summary, "per_query": per_query_records,
           "K_list": K_LIST}
    out_path = Path(out_dir) / "eval_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_path}")
    return out


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else \
        str(Path(__file__).resolve().parent / "data")
    out = sys.argv[2] if len(sys.argv) > 2 else \
        str(Path(__file__).resolve().parent / "eval")
    res = run(db, out)
    s = res["summary"]
    print("\n=== Macro Avg ===")
    for k, v in s["macro_avg"].items():
        print(f"  {k}: {v}")
    print("\n=== By Collection ===")
    for coll, m in s["by_collection"].items():
        print(f"  [{coll}] " + " | ".join(f"{k}={v}" for k, v in m.items()))
