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
    s.write(f'<g stroke="{T.NEUTRAL["900"]}" fill="none">\n')
    for d in layout.doors:
        cx = T.mm(d.x) + ox
        cy = T.mm(d.y) + oy
        half = T.mm(d.width_mm) / 2
        if d.rotation_deg == 0:
            # 가로문
            s.write(
                f'<line x1="{cx - half:.2f}" y1="{cy:.2f}" x2="{cx + half:.2f}" y2="{cy:.2f}" '
                f'stroke-width="{T.STROKE["door"]}"/>\n'
            )
            # swing arc (간단히 위/아래로)
            arc_dir = 1 if (d.swing_to_xy and d.swing_to_xy[1] > d.y) else -1
            ax2 = cx + half
            ay2 = cy + arc_dir * (half * 0.8)
            s.write(
                f'<path d="M {cx - half:.2f} {cy:.2f} A {2*half:.2f} {2*half:.2f} 0 0 {1 if arc_dir>0 else 0} {ax2:.2f} {ay2:.2f}" '
                f'stroke-dasharray="2 3" stroke-width="{T.STROKE["door_swing"]}"/>\n'
            )
        else:
            # 세로문
            s.write(
                f'<line x1="{cx:.2f}" y1="{cy - half:.2f}" x2="{cx:.2f}" y2="{cy + half:.2f}" '
                f'stroke-width="{T.STROKE["door"]}"/>\n'
            )
            arc_dir = 1 if (d.swing_to_xy and d.swing_to_xy[0] > d.x) else -1
            ax2 = cx + arc_dir * (half * 0.8)
            ay2 = cy + half
            s.write(
                f'<path d="M {cx:.2f} {cy - half:.2f} A {2*half:.2f} {2*half:.2f} 0 0 {1 if arc_dir>0 else 0} {ax2:.2f} {ay2:.2f}" '
                f'stroke-dasharray="2 3" stroke-width="{T.STROKE["door_swing"]}"/>\n'
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
        border = T.GRADE[grade]["border"]
        # AL은 더 진한 border + 점선
        s.write(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" fill-opacity="{opacity:.2f}" '
            f'stroke="{border}" stroke-width="{T.STROKE["inner_wall"] + 0.5}" stroke-dasharray="3 2"/>\n'
        )
        # AL 타입 라벨 (작게)
        s.write(
            f'<text x="{x + w/2:.2f}" y="{y + h/2 + 3:.2f}" '
            f'text-anchor="middle" font-size="{T.TEXT["xs"]}" '
            f'fill="{T.GRADE[grade]["label"]}" font-family={_q(T.FONT_MONO)}>'
            f'{_esc(pa.airlock.type)}</text>\n'
        )
        # flow_type 표시 (sink/bubble만 별도 marker)
        if pa.airlock.flow_type == "sink":
            s.write(f'<text x="{x + w - 2:.2f}" y="{y + 9:.2f}" text-anchor="end" font-size="8" fill="{T.SEMANTIC["info"]}">▼</text>\n')
        elif pa.airlock.flow_type == "bubble":
            s.write(f'<text x="{x + w - 2:.2f}" y="{y + 9:.2f}" text-anchor="end" font-size="8" fill="{T.SEMANTIC["info"]}">▲</text>\n')
    s.write('</g>\n')


# ──────────────────────────────────────────────────────────────────────
# z8 equipment
# ──────────────────────────────────────────────────────────────────────
def _emit_z8_equipment(s: StringIO, ox: float, oy: float, layout: Layout) -> None:
    """장비는 각 Room의 clipPath 안에서만 그려서 밖으로 새지 않게."""
    for pr in layout.rooms.values():
        if not pr.equipment:
            continue
        s.write(
            f'<g clip-path="url(#clip_{pr.room.id})" '
            f'fill="{T.NEUTRAL["0"]}" stroke="{T.NEUTRAL["600"]}" '
            f'stroke-width="{T.STROKE["equipment"]}">\n'
        )
        for pe in pr.equipment:
            x, y, w, h = _r(pe.rect, ox, oy)
            s.write(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"/>\n'
            )
            label = pe.equipment.name
            if w > 30:
                s.write(
                    f'<text x="{x + 3:.2f}" y="{y + 9:.2f}" font-size="{T.TEXT["xs"]}" '
                    f'fill="{T.NEUTRAL["800"]}" font-family={_q(T.FONT_MONO)}>'
                    f'{_esc(label)}</text>\n'
                )
            if pe.equipment.process_step and w > 30:
                s.write(
                    f'<text x="{x + w - 3:.2f}" y="{y + 9:.2f}" text-anchor="end" font-size="8" '
                    f'fill="{T.NEUTRAL["400"]}" font-family={_q(T.FONT_MONO)}>'
                    f'{_esc(pe.equipment.process_step)}</text>\n'
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
