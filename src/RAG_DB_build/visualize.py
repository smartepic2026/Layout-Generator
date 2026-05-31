"""
visualize.py — RAG 성능 검증 결과 시각화
==========================================
시각화 결정 배경
----------------
1) 4-패널 대시보드를 단일 PNG로 생성한다. 보고서에서 한눈에 비교하기 위해.
2) 패널 구성과 그 이유
   - (1) Macro K-Curve : P@K / R@K / F1@K 의 K-스윕은 IR 평가의 표준 시각화.
                        검색기 동작이 "정밀도-재현율 트레이드오프" 어디에
                        위치하는지 한눈에 보여준다.
   - (2) Per-Collection bar : 두 컬렉션(설계 vs 규제)의 P@5/R@5/F1@5/MRR 비교.
                        본 가이드가 두 에이전트(Design vs Validation)를 분리해서
                        운영한다는 점을 고려하면 컬렉션별 성능 분리가 의사결정에
                        가장 유용하다.
   - (3) Per-Query F1@5 : 어느 쿼리가 잘 되고 못 되는지 식별. 약점 쿼리는
                        ground-truth 라벨링/청킹 튜닝의 우선순위가 된다.
   - (4) Distance distribution : 검색된 top-5 chunk 거리값(=2(1-cosθ))의
                        히스토그램. 클러스터링 품질을 정성적으로 확인하기 위함.
3) seaborn 미사용. matplotlib 기본 색상 (모노톤 + 강조) 사용.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def make_dashboard(eval_json: str, out_path: str) -> None:
    with open(eval_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    K_list = data["K_list"]
    macro = data["summary"]["macro_avg"]
    per_query = data["per_query"]
    by_coll = data["summary"]["by_collection"]

    fig = plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.30)

    # -------- (1) Macro P/R/F1 over K -------------------------------------
    ax1 = fig.add_subplot(gs[0, 0])
    P = [macro[f"P@{K}"] for K in K_list]
    R = [macro[f"R@{K}"] for K in K_list]
    F = [macro[f"F1@{K}"] for K in K_list]
    ax1.plot(K_list, P, marker="o", linewidth=2.2, label="Precision@K", color="#2E5BFF")
    ax1.plot(K_list, R, marker="s", linewidth=2.2, label="Recall@K", color="#F4511E")
    ax1.plot(K_list, F, marker="^", linewidth=2.2, label="F1@K", color="#2E7D32")
    ax1.axhline(y=macro["MRR"], linestyle="--", color="#6A1B9A",
                label=f"MRR={macro['MRR']:.3f}", alpha=0.75)
    ax1.set_xticks(K_list)
    ax1.set_ylim(0, 1.05)
    ax1.set_xlabel("K (top-K retrieved)")
    ax1.set_ylabel("Score")
    ax1.set_title("(1) Macro-avg Precision / Recall / F1 over K\n(standard IR K-sweep)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="lower right", fontsize=9)
    for x, y in zip(K_list, P):
        ax1.annotate(f"{y:.2f}", (x, y), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=8, color="#2E5BFF")
    for x, y in zip(K_list, F):
        ax1.annotate(f"{y:.2f}", (x, y), textcoords="offset points",
                     xytext=(0, -14), ha="center", fontsize=8, color="#2E7D32")

    # -------- (2) Per-collection comparison bars --------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    metrics_to_plot = ["P@5", "R@5", "F1@5", "MRR"]
    coll_names = list(by_coll.keys())
    x = np.arange(len(metrics_to_plot))
    width = 0.35
    color_map = {"design_standards": "#3949AB", "regulatory_docs": "#F57C00"}
    for i, c in enumerate(coll_names):
        vals = [by_coll[c][m] for m in metrics_to_plot]
        bars = ax2.bar(x + i * width - width / 2, vals, width, label=c,
                       color=color_map.get(c, None), edgecolor="white")
        for b, v in zip(bars, vals):
            ax2.text(b.get_x() + b.get_width() / 2, v + 0.015,
                     f"{v:.2f}", ha="center", fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(metrics_to_plot)
    ax2.set_ylim(0, 1.1)
    ax2.set_ylabel("Score")
    ax2.set_title("(2) Per-Collection Performance @ K=5\n(Design Agent vs Validation Agent)")
    ax2.grid(alpha=0.3, axis="y")
    ax2.legend(loc="lower right", fontsize=9)

    # -------- (3) Per-query F1@5 bars (sorted) ----------------------------
    ax3 = fig.add_subplot(gs[1, 0])
    pq_sorted = sorted(per_query, key=lambda r: r["metrics"]["F1@5"])
    labels = [r["id"] for r in pq_sorted]
    vals = [r["metrics"]["F1@5"] for r in pq_sorted]
    colors = ["#3949AB" if r["collection"] == "design_standards" else "#F57C00"
              for r in pq_sorted]
    bars = ax3.barh(labels, vals, color=colors, edgecolor="white")
    for b, v, r in zip(bars, vals, pq_sorted):
        ax3.text(v + 0.012, b.get_y() + b.get_height() / 2,
                 f"{v:.2f}", va="center", fontsize=8)
    ax3.set_xlim(0, 1.1)
    ax3.set_xlabel("F1@5")
    ax3.set_title("(3) Per-Query F1@5 (sorted: weakest -> strongest)")
    ax3.grid(alpha=0.3, axis="x")
    # legend proxy
    from matplotlib.patches import Patch
    ax3.legend(handles=[Patch(color="#3949AB", label="design_standards"),
                        Patch(color="#F57C00", label="regulatory_docs")],
               loc="lower right", fontsize=9)

    # -------- (4) Distance distribution of top-5 --------------------------
    ax4 = fig.add_subplot(gs[1, 1])
    all_dist = []
    coll_of_dist = []
    for r in per_query:
        for hit in r["retrieved_top10"][:5]:
            all_dist.append(hit["distance"])
            coll_of_dist.append(r["collection"])
    all_dist = np.array(all_dist)
    coll_of_dist = np.array(coll_of_dist)
    bins = np.linspace(0, 2, 21)
    ax4.hist(all_dist[coll_of_dist == "design_standards"], bins=bins,
             alpha=0.65, label="design_standards", color="#3949AB",
             edgecolor="white")
    ax4.hist(all_dist[coll_of_dist == "regulatory_docs"], bins=bins,
             alpha=0.65, label="regulatory_docs", color="#F57C00",
             edgecolor="white")
    ax4.axvline(np.mean(all_dist), color="black", linestyle="--",
                label=f"mean={np.mean(all_dist):.2f}")
    ax4.set_xlim(0, 2)
    ax4.set_xlabel("Squared L2 distance (=2(1−cosθ); 0=identical, 2=opposite)")
    ax4.set_ylabel("count (top-5 hits)")
    ax4.set_title("(4) Top-5 Retrieved Chunk Distance Distribution")
    ax4.grid(alpha=0.3, axis="y")
    ax4.legend(loc="upper right", fontsize=9)

    fig.suptitle("RAG DB Performance Dashboard - ISPE Biopharm Knowledge Base\n"
                 f"(queries={data['summary']['n_queries']}, "
                 f"chunks: design={295}, regulatory={238})",
                 fontsize=13, y=0.995)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    ej = sys.argv[1] if len(sys.argv) > 1 else \
        str(Path(__file__).resolve().parent / "eval" / "eval_results.json")
    op = sys.argv[2] if len(sys.argv) > 2 else \
        str(Path(__file__).resolve().parent / "charts" / "dashboard.png")
    make_dashboard(ej, op)
