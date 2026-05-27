"""SVG renderer — DESIGN.md §5 Z-order로 layering.

의존성 없이 raw SVG 텍스트를 생성. 외부 라이브러리 X.
"""
from __future__ import annotations

import datetime as _dt
import html
from io import StringIO

from src.drawing_agent import design_tokens as T
from src.drawing_agent.layout_solver import (
    Layout,
    PlacedAirlock,
    PlacedDoor,
    PlacedRoom,
    Rect,
)
from src.rule_engine.schemas import RuleEngineOutput


def render(spec: RuleEngineOutput, layout: Layout) -> str:
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
        z9  Flow 화살표 (Phase 2 — v1에서는 범례만)
        z10 텍스트 라벨
        z11 치수선 (v1 simplified)
        z12 범례 & 타이틀 블록
    """
    # 캔버스 크기 (mm → unit + padding)
    w_unit = T.mm(layout.building_w_mm) + 2 * T.CANVAS_PAD + 260  # 우측 legend 영역
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

    _emit_z10_labels(s, ox, oy, layout)

    # 우측 범례
    legend_x = ox + T.mm(layout.building_w_mm) + 24
    _emit_z12_legend(s, legend_x, oy, spec)

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
        f'<path d="M -1 7 l 8 -8 M -1 3 l 4 -4 M 3 7 l 4 -4" stroke="{a["pattern_color"]}" stroke-width="0.6"/>'
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
    # Arrowhead markers (4 flow colors)
    for k, hexc in T.FLOW.items():
        s.write(
            f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{hexc}"/>'
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
def _emit_z2b_axes(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    """Architectural grid axes outside building bbox (top X, left Y)
    with dimension chains showing inter-axis distances in meters.
    """
    bw = T.mm(layout.building_w_mm)
    bh = T.mm(layout.building_h_mm)
    step = T.mm(T.MM_MAJOR)
    step_m = T.MM_MAJOR / 1000  # meters between adjacent axes
    R = 9   # circle radius for axis bubble
    OFF = 36  # distance from building edge to axis bubble center

    axis_stroke = T.NEUTRAL["600"]
    text_fill = T.NEUTRAL["800"]
    tick_stroke = T.NEUTRAL["400"]

    s.write('<g>\n')

    # ── X axis (top) ──
    axis_y = oy - OFF
    dim_y = oy - 14  # dimension chain just above building outline
    xs = []
    x = ox
    n = 1
    while x <= ox + bw + 0.5:
        xs.append(x)
        # tick line: bubble bottom → dim chain → building top edge
        s.write(
            f'<line x1="{x:.2f}" y1="{axis_y + R}" x2="{x:.2f}" y2="{oy}" '
            f'stroke="{tick_stroke}" stroke-width="0.5" stroke-dasharray="2 2"/>\n'
        )
        # bubble
        s.write(
            f'<circle cx="{x:.2f}" cy="{axis_y}" r="{R}" fill="{T.NEUTRAL["0"]}" '
            f'stroke="{axis_stroke}" stroke-width="0.8"/>\n'
        )
        s.write(
            f'<text x="{x:.2f}" y="{axis_y + 3.5:.2f}" text-anchor="middle" '
            f'font-size="9" font-family={_q(T.FONT_MONO)} fill="{text_fill}">X{n}</text>\n'
        )
        n += 1
        x += step

    # dimension chain between adjacent X axes
    for i in range(len(xs) - 1):
        x1, x2 = xs[i], xs[i + 1]
        mid = (x1 + x2) / 2
        s.write(
            f'<line x1="{x1 + 2:.2f}" y1="{dim_y}" x2="{x2 - 2:.2f}" y2="{dim_y}" '
            f'stroke="{tick_stroke}" stroke-width="0.5"/>\n'
        )
        # arrowheads (small triangles at both ends)
        s.write(
            f'<path d="M {x1:.2f} {dim_y} l 4 -2 l 0 4 z" fill="{tick_stroke}"/>\n'
            f'<path d="M {x2:.2f} {dim_y} l -4 -2 l 0 4 z" fill="{tick_stroke}"/>\n'
        )
        s.write(
            f'<text x="{mid:.2f}" y="{dim_y - 3:.2f}" text-anchor="middle" '
            f'font-size="8" font-family={_q(T.FONT_MONO)} fill="{text_fill}">{step_m:.2f}m</text>\n'
        )

    # ── Y axis (left) ──
    axis_x = ox - OFF
    dim_x = ox - 14
    ys = []
    y = oy
    n = 1
    while y <= oy + bh + 0.5:
        ys.append(y)
        s.write(
            f'<line x1="{axis_x + R}" y1="{y:.2f}" x2="{ox}" y2="{y:.2f}" '
            f'stroke="{tick_stroke}" stroke-width="0.5" stroke-dasharray="2 2"/>\n'
        )
        s.write(
            f'<circle cx="{axis_x}" cy="{y:.2f}" r="{R}" fill="{T.NEUTRAL["0"]}" '
            f'stroke="{axis_stroke}" stroke-width="0.8"/>\n'
        )
        s.write(
            f'<text x="{axis_x}" y="{y + 3.5:.2f}" text-anchor="middle" '
            f'font-size="9" font-family={_q(T.FONT_MONO)} fill="{text_fill}">Y{n}</text>\n'
        )
        n += 1
        y += step

    for i in range(len(ys) - 1):
        y1, y2 = ys[i], ys[i + 1]
        mid = (y1 + y2) / 2
        s.write(
            f'<line x1="{dim_x}" y1="{y1 + 2:.2f}" x2="{dim_x}" y2="{y2 - 2:.2f}" '
            f'stroke="{tick_stroke}" stroke-width="0.5"/>\n'
        )
        s.write(
            f'<path d="M {dim_x} {y1:.2f} l -2 4 l 4 0 z" fill="{tick_stroke}"/>\n'
            f'<path d="M {dim_x} {y2:.2f} l -2 -4 l 4 0 z" fill="{tick_stroke}"/>\n'
        )
        # rotated text so it reads vertically
        s.write(
            f'<text x="{dim_x - 3:.2f}" y="{mid:.2f}" text-anchor="middle" '
            f'font-size="8" font-family={_q(T.FONT_MONO)} fill="{text_fill}" '
            f'transform="rotate(-90 {dim_x - 3:.2f} {mid:.2f})">{step_m:.2f}m</text>\n'
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
    s.write('<g fill="none">\n')
    for pr in layout.rooms.values():
        x, y, w, h = _r(pr.rect, ox, oy)
        border = T.GRADE[pr.room.clean_grade]["border"]
        weight = T.STROKE["inner_wall"]
        if pr.room.is_corridor:
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
            sweep = 1 if arc_dir > 0 else 0
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
            sweep = 0 if arc_dir > 0 else 1
            s.write(
                f'<path d="M {leaf_end_x:.2f} {cy - half:.2f} A {leaf:.2f} {leaf:.2f} 0 0 {sweep} {cx:.2f} {cy + half:.2f}" '
                f'stroke-width="{T.STROKE["door_swing"]}"/>\n'
            )
    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z7 airlocks
# ──────────────────────────────────────────────────────────────────────
def _airlock_triangle_path(x: float, y: float, w: float, h: float, side: str) -> str:
    """Solid swing-direction triangle pointing INTO the connected room."""
    size = min(w, h) * 0.55
    if side == "north":
        # AL above room → tip points down (south)
        cx = x + w / 2
        return f"M {cx - size:.2f} {y + h - size * 1.4:.2f} L {cx + size:.2f} {y + h - size * 1.4:.2f} L {cx:.2f} {y + h - 1:.2f} Z"
    if side == "south":
        # AL below room → tip points up (north)
        cx = x + w / 2
        return f"M {cx - size:.2f} {y + size * 1.4:.2f} L {cx + size:.2f} {y + size * 1.4:.2f} L {cx:.2f} {y + 1:.2f} Z"
    if side == "east":
        # AL right of room → tip points left (west)
        cy = y + h / 2
        return f"M {x + size * 1.4:.2f} {cy - size:.2f} L {x + size * 1.4:.2f} {cy + size:.2f} L {x + 1:.2f} {cy:.2f} Z"
    if side == "west":
        # AL left of room → tip points right (east)
        cy = y + h / 2
        return f"M {x + w - size * 1.4:.2f} {cy - size:.2f} L {x + w - size * 1.4:.2f} {cy + size:.2f} L {x + w - 1:.2f} {cy:.2f} Z"
    # inline (CAL/PAL/MAL in supply corridor) — diagonal east-pointing
    cx, cy = x + w / 2, y + h / 2
    return f"M {cx - size:.2f} {cy - size:.2f} L {cx - size:.2f} {cy + size:.2f} L {cx + size:.2f} {cy:.2f} Z"


def _emit_z7_airlocks(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    s.write('<g>\n')
    for pa in layout.airlocks.values():
        x, y, w, h = _r(pa.rect, ox, oy)
        grade = pa.airlock.clean_grade
        fill = _fill_for(grade)
        opacity = T.GRADE[grade]["transparency_pct"] / 100 if grade not in ("A", "CNC") else 1.0
        border = T.GRADE[grade]["border"]
        # AL box (solid border, no dashes — architectural style)
        s.write(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" fill-opacity="{opacity:.2f}" '
            f'stroke="{T.NEUTRAL["900"]}" stroke-width="{T.STROKE["inner_wall"]}"/>\n'
        )
        # Solid black swing triangle pointing into connected room
        tri_path = _airlock_triangle_path(x, y, w, h, pa.side)
        s.write(
            f'<path d="{tri_path}" fill="{T.NEUTRAL["900"]}" '
            f'stroke="{T.NEUTRAL["900"]}" stroke-width="0.5" stroke-linejoin="miter"/>\n'
        )
        # AL type label (top-left, small)
        s.write(
            f'<text x="{x + 2:.2f}" y="{y + 9:.2f}" font-size="{T.TEXT["xs"]}" '
            f'fill="{T.NEUTRAL["900"]}" font-family={_q(T.FONT_MONO)} font-weight="600">'
            f'{_esc(pa.airlock.type)}</text>\n'
        )
        # flow_type indicator (sink ▼ / bubble ▲) for non-cascade
        if pa.airlock.flow_type == "sink":
            s.write(
                f'<text x="{x + w - 2:.2f}" y="{y + 9:.2f}" text-anchor="end" font-size="8" '
                f'fill="{T.SEMANTIC["info"]}">▼</text>\n'
            )
        elif pa.airlock.flow_type == "bubble":
            s.write(
                f'<text x="{x + w - 2:.2f}" y="{y + 9:.2f}" text-anchor="end" font-size="8" '
                f'fill="{T.SEMANTIC["info"]}">▲</text>\n'
            )
    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z8 equipment
# ──────────────────────────────────────────────────────────────────────
EQUIPMENT_STROKE = "#DC2626"  # red-600 — architectural-drawing convention


def _emit_z8_equipment(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    """Equipment as red-bordered boxes with name + area label (matches GMP
    floorplan convention). Clipped to each Room so they never leak out."""
    for pr in layout.rooms.values():
        if not pr.equipment:
            continue
        s.write(
            f'<g clip-path="url(#clip_{pr.room.id})" '
            f'fill="{T.NEUTRAL["0"]}" stroke="{EQUIPMENT_STROKE}" '
            f'stroke-width="{T.STROKE["equipment"] + 0.3}">\n'
        )
        for pe in pr.equipment:
            x, y, w, h = _r(pe.rect, ox, oy)
            s.write(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"/>\n'
            )
            if w < 22 or h < 14:
                # Too small for label — show only the box
                continue
            name = pe.equipment.name
            area_m2 = pe.equipment.footprint_m2
            # Name (top line)
            s.write(
                f'<text x="{x + 3:.2f}" y="{y + 9:.2f}" font-size="{T.TEXT["xs"]}" '
                f'fill="{T.NEUTRAL["900"]}" font-family={_q(T.FONT_MONO)} font-weight="600">'
                f'{_esc(name)}</text>\n'
            )
            # Area (bottom line) — only if box tall enough
            if h >= 22 and area_m2 > 0:
                s.write(
                    f'<text x="{x + 3:.2f}" y="{y + h - 4:.2f}" font-size="9" '
                    f'fill="{EQUIPMENT_STROKE}" font-family={_q(T.FONT_MONO)}>'
                    f'{area_m2:.1f} m²</text>\n'
                )
        s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z10 labels (Room name + grade chip + DP + area)
# ──────────────────────────────────────────────────────────────────────
def _emit_z10_labels(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    s.write('<g>\n')
    for pr in layout.rooms.values():
        x, y, w, h = _r(pr.rect, ox, oy)
        room = pr.room
        if w < 40 or h < 30:
            # 너무 좁으면 ID만
            s.write(
                f'<text x="{x + w/2:.2f}" y="{y + h/2 + 4:.2f}" text-anchor="middle" '
                f'font-size="{T.TEXT["xs"]}" fill="{T.GRADE[room.clean_grade]["label"]}" font-family={_q(T.FONT_MONO)}>'
                f'{_esc(room.id.replace("R_", ""))}</text>\n'
            )
            continue
        # Room name (Korean + English on next line for big rooms)
        s.write(
            f'<text x="{x + 8:.2f}" y="{y + 16:.2f}" font-size="{T.TEXT["sm"]}" '
            f'fill="{T.GRADE[room.clean_grade]["label"]}" font-weight="600">'
            f'{_esc(room.name_en)}</text>\n'
        )
        s.write(
            f'<text x="{x + 8:.2f}" y="{y + 30:.2f}" font-size="{T.TEXT["xs"]}" '
            f'fill="{T.NEUTRAL["600"]}">'
            f'{_esc(room.name_ko)}</text>\n'
        )
        # Grade chip (top-right corner)
        chip_x, chip_y, chip_w, chip_h = x + w - 30, y + 6, 22, 16
        s.write(
            f'<rect x="{chip_x:.2f}" y="{chip_y:.2f}" width="{chip_w}" height="{chip_h}" rx="3" '
            f'fill="{T.GRADE[room.clean_grade]["border"]}"/>\n'
        )
        s.write(
            f'<text x="{chip_x + chip_w/2:.2f}" y="{chip_y + chip_h - 4:.2f}" text-anchor="middle" '
            f'font-size="{T.TEXT["xs"]}" fill="white" font-weight="700" font-family={_q(T.FONT_MONO)}>'
            f'{room.clean_grade}</text>\n'
        )
        # DP badge (bottom-right)
        dp = room.differential_pressure_Pa
        sign = "+" if dp > 0 else ""
        dp_label = f"{sign}{dp:g} Pa"
        s.write(
            f'<text x="{x + w - 6:.2f}" y="{y + h - 8:.2f}" text-anchor="end" '
            f'font-size="{T.TEXT["xs"]}" fill="{T.NEUTRAL["600"]}" font-family={_q(T.FONT_MONO)}>'
            f'{dp_label}</text>\n'
        )
        # Area
        s.write(
            f'<text x="{x + 8:.2f}" y="{y + h - 8:.2f}" '
            f'font-size="{T.TEXT["xs"]}" fill="{T.NEUTRAL["600"]}" font-family={_q(T.FONT_MONO)}>'
            f'{room.area_m2:.0f} m²</text>\n'
        )
    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z12 legend
# ──────────────────────────────────────────────────────────────────────
def _emit_z12_legend(s: StringIO, x: float, y: float, spec: RuleEngineOutput) -> None:
    w, h = 220, 320
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
    for g in ["A", "B", "C", "D", "CNC", "NC"]:
        meta = T.GRADE[g]
        fill = _fill_for(g)
        opacity = meta["transparency_pct"] / 100 if g not in ("A", "CNC") else 1.0
        s.write(
            f'<rect x="{x + 12}" y="{yy - 11}" width="20" height="14" '
            f'fill="{fill}" fill-opacity="{opacity:.2f}" '
            f'stroke="{meta["border"]}" stroke-width="1"/>\n'
        )
        s.write(
            f'<text x="{x + 40}" y="{yy:.0f}" font-size="{T.TEXT["xs"]}" '
            f'fill="{T.NEUTRAL["800"]}" font-family={_q(T.FONT_MONO)}>'
            f'Grade {g}</text>\n'
        )
        s.write(
            f'<text x="{x + 90}" y="{yy:.0f}" font-size="9" fill="{T.NEUTRAL["400"]}">'
            f'{_esc(meta["description"])}</text>\n'
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
            f'stroke="{T.FLOW[k]}" stroke-width="1.5" marker-end="url(#arrow-{k})"/>\n'
        )
        s.write(
            f'<text x="{x + 50}" y="{yy:.0f}" font-size="{T.TEXT["xs"]}" '
            f'fill="{T.NEUTRAL["800"]}">{label}</text>\n'
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
        ("DATE", _dt.date.today().isoformat()),
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
