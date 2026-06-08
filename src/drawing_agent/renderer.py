"""SVG renderer — DESIGN.md §5 Z-order로 layering.

의존성 없이 raw SVG 텍스트를 생성. 외부 라이브러리 X.
"""
from __future__ import annotations

import html
import math
from io import StringIO

from src.drawing_agent import design_tokens as T
from src.drawing_agent.layout_solver import (
    Layout,
    PlacedAirlock,
    PlacedDoor,
    PlacedRoom,
    Rect,
)
from src.contract.schemas import RuleEngineOutput


def render(spec: RuleEngineOutput, layout: Layout, flow_mode: str = "full") -> str:
    """Layout + spec → 단일 SVG 텍스트.

    구조 (DESIGN.md §5 Z-order):
        z0  배경
        z1  마이너 그리드
        z2  메이저 그리드
        z3  건물 외곽선
        z4  Room fill
        z5  Room border/벽
        z6  도어 + swing arc
        z7  Airlock (pattern)
        z8  장비
        z9  Flow 화살표 (D-023 — spec.flow_paths 4종 그대로 렌더)
        z10 텍스트 라벨
        z11 치수선 (v1 simplified)
        z12 범례 & 타이틀 블록
    """
    # 캔버스 크기 (mm → unit + padding)
    side_panel_w = 390
    w_unit = T.mm(layout.building_w_mm) + 2 * T.CANVAS_PAD + side_panel_w
    h_unit = T.mm(layout.building_h_mm) + 2 * T.CANVAS_PAD + 100   # 하단 title block

    s = StringIO()
    s.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w_unit:.0f}" height="{h_unit:.0f}" '
        f'viewBox="0 0 {w_unit:.0f} {h_unit:.0f}" '
        f'font-family={_q(T.FONT_BODY)} fill="{T.NEUTRAL["900"]}">\n'
    )

    _emit_defs(s)
    _emit_room_clips(s, T.CANVAS_PAD, T.CANVAS_PAD, layout)
    _emit_z0_background(s, w_unit, h_unit)

    # 건물 평면은 padding 안쪽에 그림
    ox, oy = T.CANVAS_PAD, T.CANVAS_PAD
    _emit_z1_minor_grid(s, ox, oy, layout)
    _emit_z2_major_grid(s, ox, oy, layout)
    _emit_z2b_axes(s, ox, oy, layout)
    _emit_z3_building_outline(s, ox, oy, layout)

    _emit_z4_room_fills(s, ox, oy, layout)
    _emit_z5_room_borders(s, ox, oy, layout)
    _emit_z6_doors(s, ox, oy, layout)
    _emit_z7_airlocks(s, ox, oy, layout)
    _emit_z8_equipment(s, ox, oy, layout)
    _emit_z9_flow_arrows(s, ox, oy, layout, spec, flow_mode)

    _emit_z10_labels(s, ox, oy, layout)
    _emit_z11_boundary_flow(s, ox, oy, layout, spec)

    # 우측 범례
    legend_x = ox + T.mm(layout.building_w_mm) + 24
    _emit_z12_legend(s, legend_x, oy, spec, layout)

    # 하단 타이틀 블록
    tb_y = oy + T.mm(layout.building_h_mm) + 24
    _emit_z12_titleblock(s, ox, tb_y, w_unit - 2 * ox, 64, spec)

    s.write("</svg>\n")
    return s.getvalue()


# ──────────────────────────────────────────────────────────────────────
# Helpers / quote
# ──────────────────────────────────────────────────────────────────────
def _q(v) -> str:
    if isinstance(v, str):
        return '"' + v.replace('"', '&quot;') + '"'
    return f'"{v}"'


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _r(rect: Rect, ox: float, oy: float) -> tuple[float, float, float, float]:
    return T.mm(rect.x) + ox, T.mm(rect.y) + oy, T.mm(rect.w), T.mm(rect.h)


# ──────────────────────────────────────────────────────────────────────
# defs (patterns)
# ──────────────────────────────────────────────────────────────────────
def _emit_defs(s: StringIO) -> None:
    s.write("<defs>\n")
    # Grade A diagonal hatch
    a = T.GRADE["A"]
    s.write(
        '<pattern id="patA" patternUnits="userSpaceOnUse" width="6" height="6">'
        f'<rect width="6" height="6" fill="{a["fill"]}" fill-opacity="{a["transparency_pct"]/100}"/>'
        f'<path d="M -1 7 l 8 -8 M -1 3 l 4 -4 M 3 7 l 4 -4" stroke="#000000" stroke-width="0.6"/>'
        '</pattern>\n'
    )
    # CNC dotted hatch
    c = T.GRADE["CNC"]
    s.write(
        '<pattern id="patCNC" patternUnits="userSpaceOnUse" width="6" height="6">'
        f'<rect width="6" height="6" fill="{c["fill"]}" fill-opacity="{c["transparency_pct"]/100}"/>'
        f'<circle cx="3" cy="3" r="0.7" fill="{c["pattern_color"]}"/>'
        '</pattern>\n'
    )
    # Arrowhead markers — 검정, 길쭉(2.5:1), refX=0 → 선이 머리 시작점에서 멈춤
    # (refX=9였을 때 좁은 tip 부근에서 선이 삼각형보다 두꺼워져 삐져나오던 문제 해결)
    for k in T.FLOW.keys():
        s.write(
            f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="0" refY="5" '
            f'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
            f'<path d="M 0 3 L 10 5 L 0 7 z" fill="{T.FLOW[k]}"/>'
            '</marker>\n'
        )
    s.write("</defs>\n")


def _emit_room_clips(s: StringIO, ox: float, oy: float, layout) -> None:
    """각 Room의 내부 clip path. 장비/라벨이 Room 밖으로 새지 않게."""
    s.write("<defs>\n")
    for pr in layout.rooms.values():
        x, y, w, h = _r(pr.rect, ox, oy)
        s.write(
            f'<clipPath id="clip_{pr.room.id}">'
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"/>'
            f'</clipPath>\n'
        )
    s.write("</defs>\n")


# ──────────────────────────────────────────────────────────────────────
# z0 background, z1/z2 grids
# ──────────────────────────────────────────────────────────────────────
def _emit_z0_background(s: StringIO, w: float, h: float) -> None:
    s.write(
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{T.NEUTRAL["50"]}"/>\n'
    )


def _emit_z1_minor_grid(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    bw, bh = T.mm(layout.building_w_mm), T.mm(layout.building_h_mm)
    gap = T.mm(T.MM_MINOR)
    s.write(f'<g stroke="{T.NEUTRAL["100"]}" stroke-width="{T.STROKE["grid_minor"]}">\n')
    x = ox
    while x <= ox + bw + 0.5:
        s.write(f'<line x1="{x:.2f}" y1="{oy}" x2="{x:.2f}" y2="{oy + bh}"/>')
        x += gap
    y = oy
    while y <= oy + bh + 0.5:
        s.write(f'<line x1="{ox}" y1="{y:.2f}" x2="{ox + bw}" y2="{y:.2f}"/>')
        y += gap
    s.write("\n</g>\n")


def _emit_z2_major_grid(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    bw, bh = T.mm(layout.building_w_mm), T.mm(layout.building_h_mm)
    gap = T.mm(T.MM_MAJOR)
    s.write(f'<g stroke="{T.NEUTRAL["200"]}" stroke-width="{T.STROKE["grid_major"]}">\n')
    x = ox
    while x <= ox + bw + 0.5:
        s.write(f'<line x1="{x:.2f}" y1="{oy}" x2="{x:.2f}" y2="{oy + bh}"/>')
        x += gap
    y = oy
    while y <= oy + bh + 0.5:
        s.write(f'<line x1="{ox}" y1="{y:.2f}" x2="{ox + bw}" y2="{y:.2f}"/>')
        y += gap
    s.write("\n</g>\n")


# ──────────────────────────────────────────────────────────────────────
# z2b architectural grid axes (X1..Xn top, Y1..Yn left)
# ──────────────────────────────────────────────────────────────────────
def _collect_axis_lines(layout: Layout) -> tuple[list[float], list[float]]:
    """Room/AL 경계에서 실측 축선 좌표 추출 (중복 제거, 정렬).
    반환: (X mm 위치 리스트, Y mm 위치 리스트). 양 끝은 건물 외곽선 포함.
    """
    xs_mm: set[float] = {0.0, float(layout.building_w_mm)}
    ys_mm: set[float] = {0.0, float(layout.building_h_mm)}
    TOL = 100  # mm tolerance — 100mm 미만 차이는 합침

    def _add_unique(s: set, v: float):
        for existing in s:
            if abs(existing - v) < TOL:
                return
        s.add(v)

    for pr in layout.rooms.values():
        _add_unique(xs_mm, pr.rect.x)
        _add_unique(xs_mm, pr.rect.x2)
        _add_unique(ys_mm, pr.rect.y)
        _add_unique(ys_mm, pr.rect.y2)

    return sorted(xs_mm), sorted(ys_mm)


def _emit_z2b_axes(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    """건축 표준 축선 — Room 경계에서 실측 추출, 인접 축간 실측 거리 표기."""
    bw = T.mm(layout.building_w_mm)
    bh = T.mm(layout.building_h_mm)
    R = 9
    OFF = 36

    axis_stroke = T.NEUTRAL["600"]
    text_fill = T.NEUTRAL["800"]
    tick_stroke = T.NEUTRAL["400"]

    xs_mm, ys_mm = _collect_axis_lines(layout)

    s.write('<g>\n')

    # ── X axis (top) ──
    axis_y = oy - OFF
    dim_y = oy - 14
    xs_units = [T.mm(v) + ox for v in xs_mm]
    for i, x in enumerate(xs_units):
        n = i + 1
        s.write(
            f'<line x1="{x:.2f}" y1="{axis_y + R}" x2="{x:.2f}" y2="{oy}" '
            f'stroke="{tick_stroke}" stroke-width="0.5" stroke-dasharray="2 2"/>\n'
            f'<circle cx="{x:.2f}" cy="{axis_y}" r="{R}" fill="{T.NEUTRAL["0"]}" '
            f'stroke="{axis_stroke}" stroke-width="0.8"/>\n'
            f'<text x="{x:.2f}" y="{axis_y + 3.5:.2f}" text-anchor="middle" '
            f'font-size="9" font-family={_q(T.FONT_MONO)} fill="{text_fill}">X{n}</text>\n'
        )
    for i in range(len(xs_units) - 1):
        x1, x2 = xs_units[i], xs_units[i + 1]
        mid = (x1 + x2) / 2
        dist_m = (xs_mm[i + 1] - xs_mm[i]) / 1000
        if x2 - x1 < 16:
            continue  # 너무 좁으면 치수 라벨 생략
        s.write(
            f'<line x1="{x1 + 2:.2f}" y1="{dim_y}" x2="{x2 - 2:.2f}" y2="{dim_y}" '
            f'stroke="{tick_stroke}" stroke-width="0.5"/>\n'
            f'<path d="M {x1:.2f} {dim_y} l 4 -2 l 0 4 z" fill="{tick_stroke}"/>\n'
            f'<path d="M {x2:.2f} {dim_y} l -4 -2 l 0 4 z" fill="{tick_stroke}"/>\n'
            f'<text x="{mid:.2f}" y="{dim_y - 3:.2f}" text-anchor="middle" '
            f'font-size="8" font-family={_q(T.FONT_MONO)} fill="{text_fill}">{dist_m:.2f}m</text>\n'
        )

    # ── Y axis (left) ──
    axis_x = ox - OFF
    dim_x = ox - 14
    ys_units = [T.mm(v) + oy for v in ys_mm]
    for i, y in enumerate(ys_units):
        n = i + 1
        s.write(
            f'<line x1="{axis_x + R}" y1="{y:.2f}" x2="{ox}" y2="{y:.2f}" '
            f'stroke="{tick_stroke}" stroke-width="0.5" stroke-dasharray="2 2"/>\n'
            f'<circle cx="{axis_x}" cy="{y:.2f}" r="{R}" fill="{T.NEUTRAL["0"]}" '
            f'stroke="{axis_stroke}" stroke-width="0.8"/>\n'
            f'<text x="{axis_x}" y="{y + 3.5:.2f}" text-anchor="middle" '
            f'font-size="9" font-family={_q(T.FONT_MONO)} fill="{text_fill}">Y{n}</text>\n'
        )
    for i in range(len(ys_units) - 1):
        y1, y2 = ys_units[i], ys_units[i + 1]
        mid = (y1 + y2) / 2
        dist_m = (ys_mm[i + 1] - ys_mm[i]) / 1000
        if y2 - y1 < 16:
            continue
        s.write(
            f'<line x1="{dim_x}" y1="{y1 + 2:.2f}" x2="{dim_x}" y2="{y2 - 2:.2f}" '
            f'stroke="{tick_stroke}" stroke-width="0.5"/>\n'
            f'<path d="M {dim_x} {y1:.2f} l -2 4 l 4 0 z" fill="{tick_stroke}"/>\n'
            f'<path d="M {dim_x} {y2:.2f} l -2 -4 l 4 0 z" fill="{tick_stroke}"/>\n'
            f'<text x="{dim_x - 3:.2f}" y="{mid:.2f}" text-anchor="middle" '
            f'font-size="8" font-family={_q(T.FONT_MONO)} fill="{text_fill}" '
            f'transform="rotate(-90 {dim_x - 3:.2f} {mid:.2f})">{dist_m:.2f}m</text>\n'
        )

    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z3 building outline
# ──────────────────────────────────────────────────────────────────────
def _emit_z3_building_outline(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    bw, bh = T.mm(layout.building_w_mm), T.mm(layout.building_h_mm)
    s.write(
        f'<rect x="{ox}" y="{oy}" width="{bw}" height="{bh}" '
        f'fill="none" stroke="{T.NEUTRAL["900"]}" stroke-width="{T.STROKE["building_outline"]}"/>\n'
    )


# ──────────────────────────────────────────────────────────────────────
# z4 / z5 rooms
# ──────────────────────────────────────────────────────────────────────
def _fill_for(grade: str) -> str:
    if grade == "A":
        return "url(#patA)"
    if grade == "CNC":
        return "url(#patCNC)"
    return T.GRADE[grade]["fill"]


def _emit_z4_room_fills(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    s.write('<g>\n')
    for pr in layout.rooms.values():
        x, y, w, h = _r(pr.rect, ox, oy)
        g = pr.room.clean_grade
        fill = _fill_for(g)
        opacity = T.GRADE[g]["transparency_pct"] / 100 if g not in ("A", "CNC") else 1.0
        s.write(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" fill-opacity="{opacity:.2f}"/>\n'
        )
    s.write('</g>\n')


def _emit_z5_room_borders(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    # [2026-06-02] 방 테두리를 등급색으로 — 라이트에선 등급 컬러 외곽선,
    # blueprint 후처리에선 네온으로 밝아짐 (레퍼런스: 내부 다크 + 외곽선 네온).
    s.write('<g fill="none">\n')
    for pr in layout.rooms.values():
        x, y, w, h = _r(pr.rect, ox, oy)
        border = T.GRADE[pr.room.clean_grade]["border"]
        weight = T.STROKE["inner_wall"]
        s.write(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'stroke="{border}" stroke-width="{weight}"/>\n'
        )
    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z6 doors
# ──────────────────────────────────────────────────────────────────────
def _emit_z6_doors(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    """건축 표준 도어 심볼: 90° 호(arc) + door leaf 선.

    수평벽(rot=0): 호는 위/아래로 펼침, swing_to_xy의 y가 문 위치보다 크면 아래로
    수직벽(rot=90): 호는 좌/우로 펼침, swing_to_xy의 x로 결정
    """
    s.write(f'<g stroke="{T.NEUTRAL["900"]}" fill="none" stroke-linecap="round">\n')
    for d in layout.doors:
        cx = T.mm(d.x) + ox
        cy = T.mm(d.y) + oy
        leaf = T.mm(d.width_mm)  # door leaf length = full door width
        half = leaf / 2

        if d.rotation_deg == 0:
            # ── 가로벽 도어 ──
            # 벽 라인 끊김(opening)
            s.write(
                f'<line x1="{cx - half:.2f}" y1="{cy:.2f}" x2="{cx + half:.2f}" y2="{cy:.2f}" '
                f'stroke="{T.NEUTRAL["0"]}" stroke-width="{T.STROKE["door"] + 2}"/>\n'
            )
            # swing 방향 결정 (아래 swing이면 +1, 위면 -1)
            arc_dir = 1 if (d.swing_to_xy and d.swing_to_xy[1] > d.y) else -1
            # door leaf (heavier solid line) — hinge at 왼쪽
            leaf_end_y = cy + arc_dir * leaf
            s.write(
                f'<line x1="{cx - half:.2f}" y1="{cy:.2f}" x2="{cx - half:.2f}" y2="{leaf_end_y:.2f}" '
                f'stroke-width="{T.STROKE["door"]}"/>\n'
            )
            # swing arc (90° quarter-circle, 실선)
            # [2026-06-02 v3] sweep 반전 — 곡선이 swing 쪽(여닫이 방향)으로 볼록하게.
            # 이전 sweep=1(arc_dir>0)은 호가 hinge 반대편으로 오목 → 도어가 반대로 보임.
            sweep = 0 if arc_dir > 0 else 1
            s.write(
                f'<path d="M {cx - half:.2f} {leaf_end_y:.2f} A {leaf:.2f} {leaf:.2f} 0 0 {sweep} {cx + half:.2f} {cy:.2f}" '
                f'stroke-width="{T.STROKE["door_swing"]}"/>\n'
            )
        else:
            # ── 세로벽 도어 ──
            s.write(
                f'<line x1="{cx:.2f}" y1="{cy - half:.2f}" x2="{cx:.2f}" y2="{cy + half:.2f}" '
                f'stroke="{T.NEUTRAL["0"]}" stroke-width="{T.STROKE["door"] + 2}"/>\n'
            )
            arc_dir = 1 if (d.swing_to_xy and d.swing_to_xy[0] > d.x) else -1
            leaf_end_x = cx + arc_dir * leaf
            s.write(
                f'<line x1="{cx:.2f}" y1="{cy - half:.2f}" x2="{leaf_end_x:.2f}" y2="{cy - half:.2f}" '
                f'stroke-width="{T.STROKE["door"]}"/>\n'
            )
            # [2026-06-02 v3] sweep 반전 (위 가로벽과 동일 이유)
            sweep = 1 if arc_dir > 0 else 0
            s.write(
                f'<path d="M {leaf_end_x:.2f} {cy - half:.2f} A {leaf:.2f} {leaf:.2f} 0 0 {sweep} {cx:.2f} {cy + half:.2f}" '
                f'stroke-width="{T.STROKE["door_swing"]}"/>\n'
            )
    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z7 airlocks
# ──────────────────────────────────────────────────────────────────────
def _emit_z7_airlocks(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    s.write('<g>\n')
    for pa in layout.airlocks.values():
        x, y, w, h = _r(pa.rect, ox, oy)
        grade = pa.airlock.clean_grade
        fill = _fill_for(grade)
        opacity = T.GRADE[grade]["transparency_pct"] / 100 if grade not in ("A", "CNC") else 1.0
        # AL box (solid black border)
        s.write(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" fill-opacity="{opacity:.2f}" '
            f'stroke="{T.NEUTRAL["900"]}" stroke-width="{T.STROKE["inner_wall"]}"/>\n'
        )
        # AL type label — 영역 중앙 (사용자 요청)
        cx, cy = x + w / 2, y + h / 2
        ft = getattr(pa.airlock, "flow_type", None)
        ty = cy - 5 if (ft and h >= 22) else cy        # flow_type 표기 시 위로
        s.write(
            f'<text x="{cx:.2f}" y="{ty:.2f}" text-anchor="middle" '
            f'dominant-baseline="middle" font-size="{T.TEXT["xs"]}" '
            f'fill="{T.NEUTRAL["900"]}" font-family={_q(T.FONT_MONO)} font-weight="700">'
            f'{_esc(pa.airlock.type)}</text>\n'
        )
        # [정렬] flow_type 표기 — 차압 공기흐름 타입(cascade↓차압 / sink↘유입 /
        # bubble↗유출). 기호 + 약어로 작은 글씨.
        if ft and h >= 22:
            sym = {"cascade": ">>", "sink": ">|<", "bubble": "<|>"}.get(ft, "")
            s.write(
                f'<text x="{cx:.2f}" y="{cy + 7:.2f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-size="7" '
                f'fill="{T.NEUTRAL["600"]}" font-family={_q(T.FONT_MONO)}>'
                f'{sym} {_esc(ft)}</text>\n'
            )
    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z8 equipment
# ──────────────────────────────────────────────────────────────────────
EQUIPMENT_STROKE = "#DC2626"  # red-600 — 건축 도면 관례 (사용자 요청 복원)


def _emit_z8_equipment(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    """Equipment as red-bordered boxes. 텍스트는 빨간색 단색 (사용자 요청)."""
    for pr in layout.rooms.values():
        if not pr.equipment:
            continue
        # <g>: 박스만 빨간 테두리. 텍스트는 안에서 fill만 빨강, stroke none.
        s.write(
            f'<g clip-path="url(#clip_{pr.room.id})">\n'
        )
        for pe in pr.equipment:
            x, y, w, h = _r(pe.rect, ox, oy)
            # ─ 빨간 테두리 박스 ─
            s.write(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
                f'fill="{T.NEUTRAL["0"]}" stroke="{EQUIPMENT_STROKE}" '
                f'stroke-width="{(T.STROKE["equipment"] + 0.3) / 2}"/>\n'
            )
            if w < 18 or h < 12:
                continue
            name = pe.equipment.name
            area_m2 = pe.equipment.footprint_m2
            # 박스 20% 축소에 맞춰 글씨도 작게 (9→7.5, 8→6.5)
            name_size = 7.5
            area_size = 6.5
            # 박스 폭 안에 들어가게 truncate (1 char ≈ 4.2 unit at fs=7.5)
            max_chars = max(int(w / 4.2) - 1, 3)
            short_name = name if len(name) <= max_chars else name[:max_chars - 1] + "."

            # 박스 내부 중앙 정렬 (수평 + 수직)
            cx = x + w / 2
            if h >= 16 and area_m2 > 0:
                # 2줄 (이름 + 면적) — 박스 중앙 기준 위/아래로 분리
                s.write(
                    f'<text x="{cx:.2f}" y="{y + h/2 - 1:.2f}" text-anchor="middle" '
                    f'dominant-baseline="middle" font-size="{name_size}" '
                    f'fill="{EQUIPMENT_STROKE}" stroke="none" '
                    f'font-family={_q(T.FONT_MONO)} font-weight="700">'
                    f'{_esc(short_name)}</text>\n'
                )
                s.write(
                    f'<text x="{cx:.2f}" y="{y + h/2 + 7:.2f}" text-anchor="middle" '
                    f'dominant-baseline="middle" font-size="{area_size}" '
                    f'fill="{EQUIPMENT_STROKE}" stroke="none" '
                    f'font-family={_q(T.FONT_MONO)}>'
                    f'{area_m2:.1f} m²</text>\n'
                )
            else:
                # 1줄만 (이름) — 박스 정중앙
                s.write(
                    f'<text x="{cx:.2f}" y="{y + h/2:.2f}" text-anchor="middle" '
                    f'dominant-baseline="middle" font-size="{name_size}" '
                    f'fill="{EQUIPMENT_STROKE}" stroke="none" '
                    f'font-family={_q(T.FONT_MONO)} font-weight="700">'
                    f'{_esc(short_name)}</text>\n'
                )
        s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z10 labels (Room name + grade chip + DP + area)
# ──────────────────────────────────────────────────────────────────────
def _emit_z10_labels(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    """평문 룸 라벨 (GMP 도면 스타일) — grade chip/박스 제거, 텍스트만.

    레이아웃: 큰 방은 영문명 + 한글 부제. 좁은 방은 영문명만.
    DP/Area 같은 메타데이터는 small grey, 우측 하단.
    """
    s.write('<g>\n')
    for pr in layout.rooms.values():
        x, y, w, h = _r(pr.rect, ox, oy)
        room = pr.room
        label_color = T.NEUTRAL["900"]

        if w < 40 or h < 30:
            # 너무 좁으면 ID만
            s.write(
                f'<text x="{x + w/2:.2f}" y="{y + h/2 + 4:.2f}" text-anchor="middle" '
                f'font-size="{T.TEXT["xs"]}" fill="{label_color}" font-weight="600">'
                f'{_esc(room.id.replace("R_", "")[:14])}</text>\n'
            )
            continue

        # 라벨 스택 (모두 중앙 정렬, 흰색 halo) — 사용자 요청: 메타를 방 이름 바로 아래
        #   y+16 : 영문명 (큰 글씨, bold)
        #   y+29 : 한글 부제 (작게)  ← 있을 때만
        #   y+42 : 메타 (Grade · DP · Area, 모노스페이스)  ← 한글 있을 때
        #   y+29 : 메타  ← 한글 없을 때 영문 바로 아래
        ko_visible = h >= 50
        meta_y = (y + 42) if ko_visible else (y + 29)

        # ─ 영문명 ─
        s.write(
            f'<text x="{x + w/2:.2f}" y="{y + 16:.2f}" text-anchor="middle" '
            f'font-size="{T.TEXT["sm"]}" fill="{label_color}" font-weight="700" '
            f'>'
            f'{_esc(room.name_en)}</text>\n'
        )
        # ─ 한글 부제 ─
        if ko_visible:
            s.write(
                f'<text x="{x + w/2:.2f}" y="{y + 29:.2f}" text-anchor="middle" '
                f'font-size="9" fill="{T.NEUTRAL["600"]}" '
                f'>'
                f'{_esc(room.name_ko)}</text>\n'
            )
        # ─ 메타1 (Grade · DP · Area · ACPH) ─ 방 이름 바로 아래
        if h >= 35:
            dp = room.differential_pressure_Pa
            sign = "+" if dp > 0 else ""
            parts = [room.clean_grade, f"{sign}{dp:g}Pa", f"{room.area_m2:.0f}m²"]
            if room.air_changes_per_hour:           # [정렬] ACPH 반영
                parts.append(f"{room.air_changes_per_hour:g}ACH")
            meta_text = " · ".join(parts)
            s.write(
                f'<text x="{x + w/2:.2f}" y="{meta_y:.2f}" text-anchor="middle" '
                f'font-size="8" fill="{T.NEUTRAL["600"]}" font-family={_q(T.FONT_MONO)} '
                f'>'
                f'{_esc(meta_text)}</text>\n'
            )
        # ─ 메타2 (천정고 · 갱의) ─ 큰 방만 (천정고·gowning_type 반영)
        if h >= 64:
            sub = []
            if room.ceiling_height_mm:
                sub.append(f"H{room.ceiling_height_mm:g}")
            if room.gowning_type:
                sub.append(room.gowning_type)
            if sub:
                s.write(
                    f'<text x="{x + w/2:.2f}" y="{meta_y + 11:.2f}" text-anchor="middle" '
                    f'font-size="8" fill="{T.NEUTRAL["400"]}" font-family={_q(T.FONT_MONO)} '
                    f'>'
                    f'{_esc(" · ".join(sub))}</text>\n'
                )
    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z11 boundary flow labels (Visitors, Material entry, Waste exit ...)
# ──────────────────────────────────────────────────────────────────────
def _emit_z11_boundary_flow(s: StringIO, ox: float, oy: float, layout: Layout, spec: RuleEngineOutput) -> None:
    """건물 외곽선에 동선 진입/출입 라벨 표기 — FLOW 색상 코딩.

    Personnel=indigo, Material=teal, Waste=rose, Visitors=neutral.
    """
    bw = T.mm(layout.building_w_mm)
    bh = T.mm(layout.building_h_mm)

    # (side, label, fraction, color_key)
    labels = [
        ("left",   "Personnel ↔",  0.5,  "personnel"),
        ("top",    "Material ↓",   0.5,  "material"),
        ("right",  "Visitors ↔",   0.4,  None),
        ("right",  "Visitors ↔",   0.7,  None),
        ("bottom", "Waste ↑",      0.5,  "waste"),
    ]

    s.write('<g font-weight="700" font-size="11">\n')
    for side, label, frac, color_key in labels:
        color = T.NEUTRAL["900"]  # 모노톤 — 사용자 요청
        if side == "left":
            tx = ox - 50
            ty = oy + bh * frac
            s.write(
                f'<text x="{tx:.2f}" y="{ty:.2f}" text-anchor="middle" '
                f'fill="{color}" transform="rotate(-90 {tx:.2f} {ty:.2f})">{label}</text>\n'
            )
        elif side == "right":
            tx = ox + bw + 56
            ty = oy + bh * frac
            s.write(
                f'<text x="{tx:.2f}" y="{ty:.2f}" text-anchor="middle" '
                f'fill="{color}" transform="rotate(90 {tx:.2f} {ty:.2f})">{label}</text>\n'
            )
        elif side == "top":
            tx = ox + bw * frac
            ty = oy - 50
            s.write(
                f'<text x="{tx:.2f}" y="{ty:.2f}" text-anchor="middle" '
                f'fill="{color}">{label}</text>\n'
            )
        elif side == "bottom":
            tx = ox + bw * frac
            ty = oy + bh + 16
            s.write(
                f'<text x="{tx:.2f}" y="{ty:.2f}" text-anchor="middle" '
                f'fill="{color}">{label}</text>\n'
            )
    s.write('</g>\n')


def _emit_z9_flow_arrows(s: StringIO, ox: float, oy: float, layout: Layout,
                         spec: RuleEngineOutput, flow_mode: str = "full") -> None:
    """GMP 동선 화살표 — 룰엔진 `spec.flow_paths` 4종을 *그대로* 렌더 (D-023).

    [정렬 G1 해소] 기존엔 방 id 패턴("SUPPLY_CORRIDOR")으로 동선을 휴리스틱
    재구성했으나(alignment_audit G1, renderer 가 spec 을 안 받았음), 이제
    `spec.flow_paths`(personnel_entry/exit · material_entry · waste_exit ·
    product_process_order)의 방 시퀀스를 실제 배치 좌표로 연결한다.
    근거: GMP Flow 규정 1~4 (Person/Material/Product/Waste). 색인은 z12 범례.

    - 각 동선 = 연결된 화살표(구간마다 머리), 종류별 색 + 종류별 수직
      오프셋으로 공유 복도에서 평행선이 겹치지 않게.
    - Product 는 공정실 중심을 직선 연결 → 벽 가로지르기(GMP Product §2).
    - 외부 노드(ELEVATOR_*)는 URS 방위 외곽 포트로 매핑.
    - flow_paths 가 placeholder/미해소면 토폴로지 휴리스틱으로 폴백
      (발표용 내부 spec 회귀 방지).
    """
    if flow_mode == "off":
        return
    polylines = _resolve_flow_polylines(layout, ox, oy, spec, flow_mode)
    if not polylines:
        _emit_z9_flow_arrows_topology(s, ox, oy, layout)
        return
    # 종류별 그룹 — `<g class="flow flow-{key}">` 으로 묶어 뷰어/CSS/JS 토글 가능.
    bykey: dict = {}
    for key, pts in polylines:
        bykey.setdefault(key, []).append(pts)
    for key in ("personnel", "material", "waste", "product"):
        if key not in bykey:
            continue
        s.write(f'<g class="flow flow-{key}" id="flow-{key}">\n')
        seen: set[str] = set()
        for pts in bykey[key]:
            sig = _flow_signature(pts)
            if sig in seen:
                continue
            seen.add(sig)
            _draw_flow_polyline(s, pts, key)
        s.write('</g>\n')


# 종류별 전체 translation(px). 선분별 normal offset 이 아니라 path 전체를 옮겨
# L자 꺾임이 끊겨 보이지 않게 한다.
_FLOW_TRANSLATE = {
    "personnel": (0.0, -5.0),
    "material": (0.0, 0.0),
    "product": (0.0, 5.0),
    "waste": (0.0, 10.0),
}


def _flow_edge_port(node: str, layout: Layout, ox: float, oy: float):
    """외부 노드(ELEVATOR_*, 출입구)를 건물 외곽 포트로 매핑.
    URS 방위: 인원 3시(우), 자재 12시(상), 폐기물 9시(좌)."""
    bw, bh = T.mm(layout.building_w_mm), T.mm(layout.building_h_mm)
    n = node.upper()
    if "WASTE" in n:
        return (ox - 6, oy + bh * 0.5)            # 9시(좌) 폐기물 반출
    if "MATERIAL" in n:
        return (ox + bw * 0.5, oy - 6)            # 12시(상) 자재 반입
    if any(k in n for k in ("PERSON", "LOBBY", "ENTRANCE", "ELEVATOR")):
        return (ox + bw + 6, oy + bh * 0.5)       # 3시(우) 인원 출입
    return None


def _flow_point(node: str, layout: Layout, ox: float, oy: float):
    """flow_paths 노드 → svg 좌표. 방/전실 중심 또는 외곽 포트. 미해소 None."""
    pr = layout.rooms.get(node)
    if pr is not None:
        x, y, w, h = _r(pr.rect, ox, oy)
        return (x + w / 2, y + h / 2)
    pa = layout.airlocks.get(node)
    if pa is not None:
        x, y, w, h = _r(pa.rect, ox, oy)
        return (x + w / 2, y + h / 2)
    # 외부(건물 밖) 엘리베이터/반입출구 노드는 선으로 빼지 않음 — 동선이 건물
    # 외벽까지 그어지던 문제. 동선은 in/out 방에서 종료(외부 방향은 z11 외곽 라벨).
    return None


def _is_corridor_room(room) -> bool:
    """복도 방인지 (복도 인지 라우팅용). is_corridor 또는 id 에 CORRIDOR."""
    return bool(getattr(room, "is_corridor", False)) or "CORRIDOR" in getattr(room, "id", "")


def _corridor_axis_points(rect, prev_pt, next_pt, ox: float, oy: float):
    """복도 rect 의 중심선상에서, 이전 점에 가까운 진입점·다음 점에 가까운 진출점.
    수평 복도면 중심선 y=cy 위 x 이동, 수직 복도면 중심선 x=cx 위 y 이동."""
    x, y, w, h = _r(rect, ox, oy)
    if w >= h:                        # 수평 복도
        cy = y + h / 2
        xin = min(max(prev_pt[0], x), x + w)
        xout = min(max(next_pt[0], x), x + w)
        return (xin, cy), (xout, cy)
    else:                             # 수직 복도
        cx = x + w / 2
        yin = min(max(prev_pt[1], y), y + h)
        yout = min(max(next_pt[1], y), y + h)
        return (cx, yin), (cx, yout)


# ──────────────────────────────────────────────────────────────────────
# 장애물 회피 채널 라우팅 (D-029) — 동선이 방·벽을 가로지르지 않도록 복도
# 중심선 + 건물 외곽 ring 채널로만 보내고, 방 관통이 최소인 경로를 선택.
# ──────────────────────────────────────────────────────────────────────
def _flow_channels(layout: Layout, ox: float, oy: float):
    """수평 채널(Y들) / 수직 채널(X들).

    = 복도 중심선 + 외곽 ring inset + **모든 방 경계선(벽 그리드)**.
    경계선 위 직선은 양쪽 방 *내부*를 건드리지 않으므로(관통 판정은 strict
    부등호), 동선이 복도가 없는 구역에서도 벽을 따라 흐를 수 있다.
    """
    hs, vs = set(), set()
    bw, bh = T.mm(layout.building_w_mm), T.mm(layout.building_h_mm)
    x_min, x_max = ox, ox + bw          # 건물 외벽 좌/우
    y_min, y_max = oy, oy + bh          # 건물 외벽 상/하
    tol = 12.0
    for pr in layout.rooms.values():
        x, y, w, h = _r(pr.rect, ox, oy)
        if _is_corridor_room(pr.room):                       # 복도 중심선
            (hs if w >= h else vs).add(round(y + h / 2, 1) if w >= h else round(x + w / 2, 1))
        hs.update({round(y, 1), round(y + h, 1)})            # 방 상/하 경계(내부 벽)
        vs.update({round(x, 1), round(x + w, 1)})            # 방 좌/우 경계(내부 벽)
    # [수정] 건물 외벽과 겹치는 채널 제거 — 외벽은 통로가 아니므로 동선이 외벽을
    # 타던 문제. 외곽 ring 뿐 아니라 맨바깥 방 경계(=외벽)도 함께 제외.
    hs = {v for v in hs if abs(v - y_min) > tol and abs(v - y_max) > tol}
    vs = {v for v in vs if abs(v - x_min) > tol and abs(v - x_max) > tol}
    return sorted(hs), sorted(vs)


def _room_rects_svg(layout: Layout, ox: float, oy: float) -> dict:
    """비복도 방 rect(svg) — 관통 판정 대상."""
    return {rid: _r(pr.rect, ox, oy)
            for rid, pr in layout.rooms.items() if not _is_corridor_room(pr.room)}


def _pt_room(p, room_rects: dict):
    for rid, (x, y, w, h) in room_rects.items():
        if x <= p[0] <= x + w and y <= p[1] <= y + h:
            return rid
    return None


def _hcross(ax, bx, y, room_rects, skip) -> int:
    lo, hi = min(ax, bx), max(ax, bx)
    n = 0
    for rid, (x, yy, w, h) in room_rects.items():
        if rid in skip:
            continue
        if yy < y < yy + h and not (hi <= x or lo >= x + w):
            n += 1
    return n


def _vcross(ay, by, x, room_rects, skip) -> int:
    lo, hi = min(ay, by), max(ay, by)
    n = 0
    for rid, (xx, y, w, h) in room_rects.items():
        if rid in skip:
            continue
        if xx < x < xx + w and not (hi <= y or lo >= y + h):
            n += 1
    return n


def _channel_route(A, B, ch_h, ch_v, room_rects) -> list:
    """A→B 직교 경로를 채널(복도/외곽) 경유로 — 방 관통 최소(동률이면 최단)."""
    skip = {r for r in (_pt_room(A, room_rects), _pt_room(B, room_rects)) if r}
    best, bestcost = [A, B], None
    for hy in ch_h:                       # 수평 채널 경유: A→(A.x,hy)→(B.x,hy)→B
        c = (_vcross(A[1], hy, A[0], room_rects, skip)
             + _hcross(A[0], B[0], hy, room_rects, skip)
             + _vcross(hy, B[1], B[0], room_rects, skip))
        cost = (c, abs(A[1] - hy) + abs(A[0] - B[0]) + abs(hy - B[1]))
        if bestcost is None or cost < bestcost:
            bestcost, best = cost, [A, (A[0], hy), (B[0], hy), B]
    for vx in ch_v:                       # 수직 채널 경유
        c = (_hcross(A[0], vx, A[1], room_rects, skip)
             + _vcross(A[1], B[1], vx, room_rects, skip)
             + _hcross(vx, B[0], B[1], room_rects, skip))
        cost = (c, abs(A[0] - vx) + abs(A[1] - B[1]) + abs(vx - B[0]))
        if bestcost is None or cost < bestcost:
            bestcost, best = cost, [A, (vx, A[1]), (vx, B[1]), B]
    return best


def _route_polyline(pts: list, ch_h, ch_v, room_rects) -> list:
    """waypoint 점들을 채널 라우팅으로 이어 붙임 (방 관통 최소)."""
    routed = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        seg = _channel_route(a, b, ch_h, ch_v, room_rects)
        for q in seg[1:]:
            if routed and abs(routed[-1][0] - q[0]) < 0.5 and abs(routed[-1][1] - q[1]) < 0.5:
                continue
            routed.append(q)
    return routed


def _find_room(layout: Layout, *subs: str, exclude: tuple[str, ...] = ()) -> str | None:
    rooms = layout.rooms
    for rid in rooms:
        up = rid.upper()
        if any(s.upper() in up for s in subs) and not any(e.upper() in up for e in exclude):
            return rid
    return None


def _main_corridors(layout: Layout) -> dict:
    ret_top = _find_room(layout, "RETURN_CORRIDOR", exclude=("_S",))
    ret_bot = next((rid for rid in layout.rooms if rid.endswith("RETURN_CORRIDOR_S")), None)
    d_corr = next((rid for rid in layout.rooms
                   if rid == "R_CORRIDOR" or rid.endswith("_AUX_CORRIDOR")), None)
    nc_corr = _find_room(layout, "CORRIDOR_VISITOR") or _find_room(layout, "NC_AUX_CORRIDOR")
    return {
        "nc": nc_corr,
        "d": d_corr,
        "supply": _find_room(layout, "SUPPLY_CORRIDOR"),
        "return_top": ret_top,
        "return_bottom": ret_bot or ret_top,
    }


def _attached_airlock(layout: Layout, room_id: str, preferred_types: tuple[str, ...]) -> str | None:
    for t in preferred_types:
        for aid, pa in layout.airlocks.items():
            if pa.attached_room_id == room_id and pa.airlock.type == t:
                return aid
    for aid, pa in layout.airlocks.items():
        if pa.attached_room_id == room_id and any(pa.airlock.type.startswith(p[:3]) for p in preferred_types):
            return aid
    return None


def _major_process_rooms(layout: Layout, spec) -> list[str]:
    prod = [rid for rid in list(getattr(spec.flow_paths, "product_process_order", []) or [])
            if rid in layout.rooms]
    for i, rid in enumerate(prod):
        if "INOCULATION" in rid.upper():
            prod = prod[i:]
            break
    if prod:
        return prod
    return [
        rid for rid, pr in layout.rooms.items()
        if pr.room.category == "process" and getattr(pr.room, "one_way_flow", False)
    ]


def _return_corridor_for(layout: Layout, room_id: str, corr: dict) -> str | None:
    pr = layout.rooms.get(room_id)
    if pr is None:
        return corr.get("return_top")
    if pr.rect.cy < layout.building_h_mm / 2:
        return corr.get("return_top")
    return corr.get("return_bottom") or corr.get("return_top")


def _compact(seq: list[str | None]) -> list[str]:
    out = []
    for item in seq:
        if item and (not out or out[-1] != item):
            out.append(item)
    return out


def _derive_full_flows(layout: Layout, spec, flow_mode: str = "full") -> list:
    """GMP 경유지 기반 동선 recipe.

    Material/Personnel 은 낮은 grade corridor 에서 gowning/MAL gate 를 거쳐 높은
    grade 로 진입하고, Waste 는 Waste-out 으로 종료한다. Product 는 Inoculation
    부터 시작해 공정 순서 뒤 DS storage 까지 이어진다.
    """
    corr = _main_corridors(layout)
    supply = corr["supply"]
    d_corr = corr["d"]
    nc_corr = corr["nc"]
    mat_in_nc_d = _find_room(layout, "MATERIAL_IN", exclude=("STORAGE",))
    gown_nc_d = _find_room(layout, "GOWNING_FEMALE") or _find_room(layout, "GOWNING_MALE")
    gown_d_c = _find_room(layout, "R_GOWNING") or _find_room(layout, "GOWNING_PROCESS")
    mal_d_c = _find_room(layout, "SUPPLY_MAL_IN") or _find_room(layout, "MAL_IN", exclude=("PURIFICATION", "HARVEST", "CULTURE", "INOCULATION"))
    waste_out = _find_room(layout, "WASTE_OUT", "WASTE")
    lobby = _find_room(layout, "LOBBY")
    ds_storage = _find_room(layout, "DS_STORAGE", "STORAGE_DS", "STORAGE_BULK")
    major = _major_process_rooms(layout, spec)
    flows: list = []

    if flow_mode != "full":
        target_rooms = major[:1]
        for rid in target_rooms:
            mat_al = _attached_airlock(layout, rid, ("MAL_in", "CAL_in"))
            flows.append(("material", _compact([
                nc_corr, mat_in_nc_d, d_corr, mal_d_c, supply, mat_al, rid,
            ])))

            pal_in = _attached_airlock(layout, rid, ("PAL_in", "CAL_in"))
            pal_out = _attached_airlock(layout, rid, ("PAL_out", "CAL_out", "MAL_out"))
            ret = _return_corridor_for(layout, rid, corr)
            flows.append(("personnel", _compact([
                lobby, nc_corr, gown_nc_d, d_corr, gown_d_c, supply,
                pal_in, rid, pal_out, ret, d_corr, gown_nc_d, nc_corr, lobby,
            ])))

            waste_al = _attached_airlock(layout, rid, ("MAL_out", "CAL_out", "PAL_out"))
            flows.append(("waste", _compact([
                rid, waste_al, ret, d_corr, waste_out,
            ])))
    else:
        # Review-readable full mode: draw shared trunk once, then per-room branches.
        # The old version repeated the entire NC→D→C trunk for every process room,
        # which made dense same-color stripes over Gowning/D corridor.
        flows.append(("material", _compact([
            nc_corr, mat_in_nc_d, d_corr, mal_d_c, supply,
        ])))
        flows.append(("personnel", _compact([
            lobby, nc_corr, gown_nc_d, d_corr, gown_d_c, supply,
        ])))

        return_corridors: set[str] = set()
        for rid in major:
            ret = _return_corridor_for(layout, rid, corr)
            if ret:
                return_corridors.add(ret)

            mat_al = _attached_airlock(layout, rid, ("MAL_in", "CAL_in"))
            flows.append(("material", _compact([supply, mat_al, rid])))

            pal_in = _attached_airlock(layout, rid, ("PAL_in", "CAL_in"))
            pal_out = _attached_airlock(layout, rid, ("PAL_out", "CAL_out", "MAL_out"))
            flows.append(("personnel", _compact([supply, pal_in, rid, pal_out, ret])))

            waste_al = _attached_airlock(layout, rid, ("MAL_out", "CAL_out", "PAL_out"))
            flows.append(("waste", _compact([rid, waste_al, ret])))

        for ret in sorted(return_corridors):
            flows.append(("personnel", _compact([ret, d_corr, gown_nc_d, nc_corr, lobby])))
            flows.append(("waste", _compact([ret, d_corr, waste_out])))

    product = list(major)
    if product:
        flows.append(("product", _compact(product + [supply, mal_d_c, d_corr, ds_storage])))
    return flows


def _resolve_flow_polylines(layout: Layout, ox: float, oy: float, spec,
                            flow_mode: str = "full") -> list:
    """spec.flow_paths 5필드 → [(flow_key, [점,...]), ...].

    flow_mode="full" 이면 공통 corridor trunk 는 1회만 그리고 공정실별 branch 를
    추가한다. "main" 은 대표 1경로만 그린다.
    해소 점 2개 미만 path 제외. 내부 노드 4개 미만이면(placeholder) 빈 리스트.
    """
    fp = getattr(spec, "flow_paths", None)
    if fp is None:
        return []
    seqs = _derive_full_flows(layout, spec, flow_mode=flow_mode)
    if not seqs:
        seqs = [
            ("personnel", list(fp.personnel_entry or [])),
            ("personnel", list(fp.personnel_exit or [])),
            ("material", list(fp.material_entry or [])),
            ("waste", list(fp.waste_exit or [])),
            ("product", list(fp.product_process_order or [])),
        ]
    ch_h, ch_v = _flow_channels(layout, ox, oy)
    room_rects = _room_rects_svg(layout, ox, oy)
    out = []
    interior_resolved = 0
    for key, seq in seqs:
        # 1) 노드 해소 → (점, 복도여부, rect)
        nodes: list = []
        for node in seq:
            p = _flow_point(node, layout, ox, oy)
            if p is None:
                continue
            if node in layout.rooms or node in layout.airlocks:
                interior_resolved += 1
            pr = layout.rooms.get(node)
            is_corr = pr is not None and _is_corridor_room(pr.room)
            rect = pr.rect if pr is not None else None
            nodes.append((p, is_corr, rect))
        # 2) [복도 인지] 내부 복도 웨이포인트는 중심점 대신 [진입, 진출](중심선상)로
        #    펼쳐 동선이 복도를 *타고* 흐르게 — 벽/타 방 가로지르기 최소화.
        pts: list = []
        for i, (p, is_corr, rect) in enumerate(nodes):
            if is_corr and rect is not None and 0 < i < len(nodes) - 1:
                e_in, e_out = _corridor_axis_points(rect, nodes[i - 1][0], nodes[i + 1][0], ox, oy)
                cand = [e_in, e_out]
            else:
                cand = [p]
            for q in cand:
                if pts and abs(pts[-1][0] - q[0]) < 0.5 and abs(pts[-1][1] - q[1]) < 0.5:
                    continue   # 연속 중복 제거
                pts.append(q)
        # 3) [장애물 회피] Product 외 동선은 채널(복도/외곽) 경유로 라우팅 →
        #    방·벽 관통 최소. Product 는 공정실 간 벽 가로지르기(규정 3-2) 유지.
        if key != "product" and len(pts) >= 2:
            pts = _route_polyline(pts, ch_h, ch_v, room_rects)
        if len(pts) >= 2:
            out.append((key, pts))
    if interior_resolved < 4:
        return []
    return out


def _flow_signature(pts: list) -> str:
    return "|".join(f"{round(x, 1):.1f},{round(y, 1):.1f}" for x, y in pts)


def _draw_flow_polyline(s: StringIO, pts: list, key: str) -> None:
    """연결된 동선 — **직교(Manhattan) L자** 라우팅 (D-025).

    대각선 center-to-center 대신 각 구간을 수평→수직(또는 그 반대) L 로 꺾어
    복도/벽을 따라 흐르는 GMP 도면 관습에 맞춤. 하나의 SVG path 로 그려
    segment별 offset 때문에 모서리가 끊기는 현상을 막는다.
    """
    dx, dy = _FLOW_TRANSLATE.get(key, (0.0, 0.0))
    routed = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        horiz_first = abs(x2 - x1) >= abs(y2 - y1)
        ex, ey = (x2, y1) if horiz_first else (x1, y2)    # 엘보
        cand = [(x1 + dx, y1 + dy)]
        if not (
            (math.isclose(ex, x1, abs_tol=0.5) and math.isclose(ey, y1, abs_tol=0.5))
            or (math.isclose(ex, x2, abs_tol=0.5) and math.isclose(ey, y2, abs_tol=0.5))
        ):
            cand.append((ex + dx, ey + dy))
        cand.append((x2 + dx, y2 + dy))
        for q in cand:
            if routed and abs(routed[-1][0] - q[0]) < 0.5 and abs(routed[-1][1] - q[1]) < 0.5:
                continue
            routed.append(q)
    if len(routed) < 2:
        return
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in routed)
    s.write(
        f'<path d="{d}" stroke="{T.FLOW[key]}" stroke-width="1.8" '
        f'stroke-opacity="0.82" fill="none" stroke-linecap="round" '
        f'stroke-linejoin="round" stroke-dasharray="7 5" '
        f'marker-end="url(#arrow-{key})"/>\n'
    )


def _emit_z9_flow_arrows_topology(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    """[폴백] 청정도 구배 토폴로지 one-way flow 화살표 (flow_paths 미해소 시).

    로직:
      - Supply 복도(중앙): 가운 입구(좌) → 우 분배.        personnel 색
      - Return 복도(상·하): 우 → 좌, D복도 배출 방향.       waste 색
      - Grade D 세로 복도: 하→상 인원/자재 진입.            personnel 색
      - AL drop(공정행 수직 통과): supply → room → return.
            공정행이 supply 위면 ↑(return상으로), 아래면 ↓(return하로).
            PAL=personnel, MAL=material, CAL=product 색.
    """
    s.write('<g>\n')

    def _harrow(rect, l2r: bool, key: str):
        x0, y0, w, h = _r(rect, ox, oy)
        ym = y0 + h / 2
        x1, x2 = (x0 + 18, x0 + w - 18) if l2r else (x0 + w - 18, x0 + 18)
        if abs(x2 - x1) < 6:
            return
        s.write(
            f'<line x1="{x1:.2f}" y1="{ym:.2f}" x2="{x2:.2f}" y2="{ym:.2f}" '
            f'stroke="{T.FLOW[key]}" stroke-width="2.2" fill="none" '
            f'stroke-dasharray="7 4" marker-end="url(#arrow-{key})"/>\n'
        )

    # ── 1. 복도 메인 흐름 ──
    supply_cy_mm = layout.building_h_mm / 2
    for rid, pr in layout.rooms.items():
        if "SUPPLY_CORRIDOR" in rid:
            supply_cy_mm = pr.rect.cy
            _harrow(pr.rect, True, "personnel")     # 좌(가운)→우
        elif "RETURN_CORRIDOR" in rid:
            _harrow(pr.rect, False, "waste")        # 우→좌(D복도 배출)

    # ── 2. Grade D 세로 복도: 하→상 진입 ──
    for rid, pr in layout.rooms.items():
        if rid == "R_CORRIDOR" or rid.endswith("_AUX_CORRIDOR"):
            x0, y0, w, h = _r(pr.rect, ox, oy)
            xm = x0 + w / 2
            s.write(
                f'<line x1="{xm:.2f}" y1="{y0 + h - 18:.2f}" x2="{xm:.2f}" y2="{y0 + 18:.2f}" '
                f'stroke="{T.FLOW["personnel"]}" stroke-width="2.2" fill="none" '
                f'stroke-dasharray="7 4" marker-end="url(#arrow-personnel)"/>\n'
            )

    # ── 3. AL drop: 공정행 수직 통과 (supply→room→return 방향) ──
    ext = 16
    for pa in layout.airlocks.values():
        x, y, w, h = _r(pa.rect, ox, oy)
        cx = x + w / 2
        al_type = pa.airlock.type or ""
        key = (
            "personnel" if al_type.startswith("PAL")
            else "material" if al_type.startswith("MAL")
            else "product"
        )
        if pa.side not in ("north", "south"):
            continue
        up = pa.rect.cy < supply_cy_mm   # 공정행이 supply 위 → ↑(return 상으로)
        if up:
            y1, y2 = y + h + ext, y - ext
        else:
            y1, y2 = y - ext, y + h + ext
        s.write(
            f'<line x1="{cx:.2f}" y1="{y1:.2f}" x2="{cx:.2f}" y2="{y2:.2f}" '
            f'stroke="{T.FLOW[key]}" stroke-width="2.5" fill="none" '
            f'stroke-dasharray="7 4" marker-end="url(#arrow-{key})"/>\n'
        )

    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z12 legend
# ──────────────────────────────────────────────────────────────────────
def _emit_z12_legend(s: StringIO, x: float, y: float, spec: RuleEngineOutput, layout: Layout) -> None:
    w, h = 350, 430
    s.write(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{T.NEUTRAL["0"]}" '
        f'stroke="{T.NEUTRAL["200"]}" stroke-width="1"/>\n'
    )
    # Title
    s.write(
        f'<text x="{x + 12}" y="{y + 22}" font-size="{T.TEXT["base"]}" font-weight="700" '
        f'fill="{T.NEUTRAL["900"]}">LEGEND</text>\n'
    )
    # Grade swatches
    yy = y + 44
    grade_desc = {
        "A": "Sterile barrier",
        "B": "Barrier surround",
        "C": "Main process",
        "D": "Support / closed process",
        "CNC": "Controlled non-classified",
        "NC": "Non-classified",
    }
    for g in ["A", "B", "C", "D", "CNC", "NC"]:
        meta = T.GRADE[g]
        fill = _fill_for(g)
        opacity = meta["transparency_pct"] / 100 if g not in ("A", "CNC") else 1.0
        s.write(
            f'<rect x="{x + 12}" y="{yy - 11}" width="20" height="14" '
            f'fill="{fill}" fill-opacity="{opacity:.2f}" '
            f'stroke="#000000" stroke-width="1"/>\n'
        )
        s.write(
            f'<text x="{x + 40}" y="{yy:.0f}" font-size="{T.TEXT["xs"]}" '
            f'fill="{T.NEUTRAL["800"]}" font-family={_q(T.FONT_MONO)}>'
            f'Grade {g}</text>\n'
        )
        s.write(
            f'<text x="{x + 116}" y="{yy:.0f}" font-size="9" fill="{T.NEUTRAL["600"]}">'
            f'{_esc(grade_desc[g])}</text>\n'
        )
        yy += 18
    # Flow arrows
    yy += 8
    s.write(
        f'<text x="{x + 12}" y="{yy:.0f}" font-size="{T.TEXT["xs"]}" font-weight="700" '
        f'fill="{T.NEUTRAL["900"]}">FLOW</text>\n'
    )
    yy += 14
    for k, label in [("personnel", "Personnel"), ("material", "Material"), ("waste", "Waste"), ("product", "Product")]:
        s.write(
            f'<line x1="{x + 14}" y1="{yy - 4}" x2="{x + 40}" y2="{yy - 4}" '
            f'stroke="{T.FLOW[k]}" stroke-width="1.8" stroke-dasharray="7 5" '
            f'marker-end="url(#arrow-{k})"/>\n'
        )
        s.write(
            f'<text x="{x + 50}" y="{yy:.0f}" font-size="{T.TEXT["xs"]}" '
            f'fill="{T.NEUTRAL["800"]}">{label}</text>\n'
        )
        yy += 16

    yy += 14
    s.write(
        f'<text x="{x + 12}" y="{yy:.0f}" font-size="{T.TEXT["xs"]}" font-weight="700" '
        f'fill="{T.NEUTRAL["900"]}">DRAWING INFO</text>\n'
    )
    yy += 18
    area_m2 = layout.building_w_mm * layout.building_h_mm / 1_000_000
    actual_rooms = [pr for pr in layout.rooms.values() if not _is_corridor_room(pr.room)]
    info_rows = [
        ("Canvas W x H", f"{layout.building_w_mm/1000:.1f}m x {layout.building_h_mm/1000:.1f}m"),
        ("Canvas Area", f"{area_m2:.0f} m2"),
        ("Placed Rooms", str(len(actual_rooms))),
        ("Corridors", str(len(layout.rooms) - len(actual_rooms))),
        ("Airlocks", str(len(layout.airlocks))),
        ("Doors", str(len(layout.doors))),
        ("Modality", spec.modality.upper()),
    ]
    for label, value in info_rows:
        s.write(
            f'<text x="{x + 12}" y="{yy:.0f}" font-size="9" fill="{T.NEUTRAL["600"]}" '
            f'font-family={_q(T.FONT_MONO)}>{_esc(label)}</text>\n'
        )
        s.write(
            f'<text x="{x + 138}" y="{yy:.0f}" font-size="10" fill="{T.NEUTRAL["900"]}" '
            f'font-weight="600">{_esc(value)}</text>\n'
        )
        yy += 16


# ──────────────────────────────────────────────────────────────────────
# z12 titleblock (bottom)
# ──────────────────────────────────────────────────────────────────────
def _emit_z12_titleblock(s: StringIO, x: float, y: float, w: float, h: float, spec: RuleEngineOutput) -> None:
    s.write(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{T.NEUTRAL["0"]}" '
        f'stroke="{T.NEUTRAL["200"]}" stroke-width="1"/>\n'
    )
    cols = [
        ("PROJECT", spec.project_name),
        ("MODALITY", spec.modality.upper()),
        ("ROOMS", str(len(spec.rooms))),
        ("AIRLOCKS", str(len(spec.airlocks))),
        ("PREPARED BY", "Rule Engine v0.1"),
    ]
    col_w = w / len(cols)
    for i, (k, v) in enumerate(cols):
        cx = x + i * col_w + 12
        s.write(
            f'<text x="{cx}" y="{y + 18}" font-size="9" fill="{T.NEUTRAL["400"]}" '
            f'font-family={_q(T.FONT_MONO)}>{k}</text>\n'
        )
        s.write(
            f'<text x="{cx}" y="{y + 38}" font-size="{T.TEXT["sm"]}" '
            f'fill="{T.NEUTRAL["900"]}" font-weight="600">{_esc(v)}</text>\n'
        )
