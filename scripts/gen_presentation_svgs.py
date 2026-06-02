"""발표용 다양한 floorplan SVG 생성 — 현실적 URS 변형 3종.

1) small_pilot_2000L  — 소규모 파일럿 (방 적음, 면적 축소)
2) large_multiproduct — 대규모 멀티프로덕트 (병렬 suite + QC/창고/유틸 추가)
3) perimeter_ring     — ㅁ자 외곽복도 + 중앙 방 그리드 (다른 토폴로지)

베이스: 소연 엔진 실측 출력(mAb 8000L). 변형은 랜덤이 아니라 도메인 현실적 조정.
실행: python -m scripts.gen_presentation_svgs   (또는 python scripts/gen_presentation_svgs.py)
"""
from __future__ import annotations

import copy
import json

import os

import cairosvg

from src.drawing_agent.blueprint_theme import to_blueprint
from src.drawing_agent.data import enrich_spec
from src.drawing_agent.data.tier1_ruleengine import load_external_spec
from src.drawing_agent.floorplan import generate_floorplan
from src.drawing_agent.layout_solver import solve_perimeter_ring
from src.drawing_agent.renderer import render

OUT = "output/presentation"

BASE_PATH = "/tmp/soyeon_output.json"
base = json.load(open(BASE_PATH))


# ──────────────────────────────────────────────────────────────────
# 1) SMALL — 파일럿 2000L: Purification_2 suite 제거 + 지원/NC 절반 + 면적 ×0.55
# ──────────────────────────────────────────────────────────────────
def build_small() -> dict:
    s = copy.deepcopy(base)
    rm = {r["room_id"] for r in s["rooms"] if "PURIFICATION_2" in r["room_id"]}
    aux = [r["room_id"] for r in s["rooms"] if r.get("category") == "auxiliary"]
    nc = [r["room_id"] for r in s["rooms"] if r.get("category") == "NC"]
    rm |= set(aux[len(aux) // 2:])     # 지원실 절반 제거
    rm |= set(nc[3:])                  # NC 3개만 유지
    s["rooms"] = [r for r in s["rooms"] if r["room_id"] not in rm]
    for r in s["rooms"]:
        if r.get("category") == "process" and r.get("area_m2"):
            r["area_m2"] = round(r["area_m2"] * 0.55, 1)  # 소규모 스케일
    s["airlocks"] = [a for a in s["airlocks"]
                     if a.get("connects_higher_room") not in rm
                     and a.get("connects_lower_room") not in rm]
    return s


# ──────────────────────────────────────────────────────────────────
# 2) LARGE — 멀티프로덕트: 병렬 suite B + QC/창고/유틸 + B suite 에어록
# ──────────────────────────────────────────────────────────────────
def build_large() -> dict:
    s = copy.deepcopy(base)
    proc_t = next(r for r in base["rooms"] if r["room_id"] == "R_CELL_CULTURE")
    al_t = base["airlocks"][0]

    def mk_room(rid, name, cat, grade, area, flow="Both-way"):
        r = copy.deepcopy(proc_t)
        r.update(room_id=rid, name_en=name, name_ko=name, category=cat,
                 clean_grade=grade, area_m2=area, room_flow=flow,
                 equipment=[], process_no=[])
        return r

    adds = [
        mk_room("R_CELL_CULTURE_B", "Cell Culture B", "process", "C", 150),
        mk_room("R_HARVEST_B", "Harvest B", "process", "C", 60),
        mk_room("R_PURIFICATION_B", "Purification B", "process", "C", 200),
        mk_room("R_QC_LAB", "QC Lab", "auxiliary", "C", 80),
        mk_room("R_MICRO_LAB", "Micro Lab", "auxiliary", "C", 60),
        mk_room("R_RAW_WAREHOUSE", "Raw Material WH", "auxiliary", "D", 120),
        mk_room("R_FINISHED_GOODS", "Finished Goods", "auxiliary", "D", 100),
        mk_room("R_SOLVENT_STORE", "Solvent Store", "auxiliary", "D", 50),
        mk_room("R_MECHANICAL", "Mechanical Rm", "NC", "NC", 150),
        mk_room("R_HVAC", "HVAC Rm", "NC", "NC", 100),
        mk_room("R_ELECTRICAL", "Electrical Rm", "NC", "NC", 60),
        mk_room("R_QC_OFFICE", "QC Office", "NC", "NC", 40),
    ]
    s["rooms"] += adds

    def mk_al(alid, kind, higher):
        a = copy.deepcopy(al_t)
        a.update(al_id=alid, kind=kind, connects_higher_room=higher)
        return a

    for k in ["PAL_in", "PAL_out", "MAL_in", "MAL_out"]:
        s["airlocks"].append(mk_al(f"R_{k.upper()}_CELL_CULTURE_B", k, "R_CELL_CULTURE_B"))
    return s


# ──────────────────────────────────────────────────────────────────
# 3b) ASEPTIC — URS aseptic_filling_onsite=True → Grade A/B 무균충전 suite 추가
#     (베이스는 전부 C/D → A/B 방 등장이 "입력→출력" 차이를 시각적으로 입증)
# ──────────────────────────────────────────────────────────────────
def build_aseptic() -> dict:
    s = copy.deepcopy(base)
    proc_t = next(r for r in base["rooms"] if r["room_id"] == "R_CELL_CULTURE")
    al_t = base["airlocks"][0]

    def mk(rid, name, grade, area, flow="One-way"):
        r = copy.deepcopy(proc_t)
        r.update(room_id=rid, name_en=name, name_ko=name, category="process",
                 clean_grade=grade, area_m2=area, room_flow=flow, equipment=[], process_no=[])
        return r

    s["rooms"] += [
        mk("R_FILLING", "Aseptic Filling", "A", 40),
        mk("R_FILLING_BACKGROUND", "Filling Background", "B", 90),
        mk("R_FILL_GOWNING", "Grade B Gowning", "B", 30),
        mk("R_CAPPING", "Capping", "C", 40),
        mk("R_LYO", "Lyophilizer", "C", 60),
    ]

    def mk_al(alid, kind, higher):
        a = copy.deepcopy(al_t)
        a.update(al_id=alid, kind=kind, connects_higher_room=higher)
        return a

    for k in ["PAL_in", "PAL_out", "MAL_in", "MAL_out"]:
        s["airlocks"].append(mk_al(f"R_{k.upper()}_FILLING", k, "R_FILLING"))
    return s


def _emit(svg, name, label, meta=""):
    """라이트 + 블루프린트(다크) SVG·PNG 동시 저장."""
    os.makedirs(OUT, exist_ok=True)
    bp = to_blueprint(svg)
    open(f"{OUT}/floorplan_{name}.svg", "w").write(svg)
    open(f"{OUT}/floorplan_{name}_blueprint.svg", "w").write(bp)
    for suf, s in [("", svg), ("_blueprint", bp)]:
        cairosvg.svg2png(bytestring=s.encode(), output_width=2200,
                         write_to=f"{OUT}/floorplan_{name}{suf}.png")
    print(f"{label}: {meta} → {name}.svg (+_blueprint) +png")


def gen_stripband(spec_dict, name, label):
    spec = load_external_spec(json.dumps(spec_dict))
    svg, layout = generate_floorplan(spec, dynamic_rooms=True, auto_canvas=True)
    _emit(svg, name, label,
          f"rooms={len(spec.rooms)} placed={len(layout.rooms)} doors={len(layout.doors)}")


def gen_ring(spec_dict, name, label):
    spec = load_external_spec(json.dumps(spec_dict))
    enrich_spec(spec)
    layout = solve_perimeter_ring(spec, auto_canvas=True)
    svg = render(spec, layout)
    _emit(svg, name, label,
          f"placed={len(layout.rooms)} doors={len(layout.doors)}")


if __name__ == "__main__":
    gen_stripband(base, "v2_soyeon", "BASE")
    gen_stripband(build_small(), "small_pilot_2000L", "SMALL")
    gen_stripband(build_large(), "large_multiproduct", "LARGE")
    gen_stripband(build_aseptic(), "aseptic_filling", "ASEPTIC")
    gen_ring(base, "perimeter_ring", "RING")
