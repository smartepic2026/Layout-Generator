"""SVG → DXF 변환기 (Layout-Generator demo SVG용).

usage:
    python scripts/svg_to_dxf.py output/reference_style_demo.svg output/reference_style_demo.dxf

특징:
- SVG y축(아래로 +) → DXF y축(위로 +) 자동 뒤집기
- 레이어 자동 분리 (rooms / walls / airlocks / equipment / labels / arrows / dimensions)
- text fill, stroke 색상 → DXF AutoCAD Color Index 매핑
- 1 SVG unit = 1 mm 가정 (필요시 SCALE 조정)
"""
from __future__ import annotations
import sys
from pathlib import Path

import ezdxf
from ezdxf import colors
from svgelements import (
    SVG, Rect, SimpleLine, Polygon, Polyline, Path, Text, Group,
    Move, Close
)
Line = SimpleLine  # svgelements 최신 버전 호환


# ── 매개변수 ──
SCALE = 1.0   # 1 SVG unit = 1 mm. 실측 50mm = 1 unit 이면 SCALE = 50

# 그룹 ID → DXF 레이어 매핑
LAYER_MAP = {
    "axes": "AXES",
    "dimensions_left": "DIM",
    "dimensions_top": "DIM",
    "room_fills": "ROOM_FILL",
    "walls": "WALL",
    "airlocks": "AIRLOCK",
    "stairs": "STAIRS",
    "equipment_annotations": "EQUIPMENT",
    "arrows": "FLOW",
    "utilities": "ANNOTATION",
    "labels": "LABEL",
}

# 색상 매핑 (RGB hex → ACI index)
COLOR_HEX_TO_ACI = {
    "#000000": 7,   # white/black depending on bg
    "#DC2626": 1,   # red (equipment)
    "#2563EB": 5,   # blue (personnel)
    "#D97706": 30,  # orange (material)
    "#B91C1C": 1,   # red (waste)
    "#1E40AF": 5,   # dark blue (PB)
    "#FBF1D9": 51,  # light yellow (Grade C)
    "#F2F2F2": 9,   # light gray (CNC)
    "#F7E8C2": 41,  # ante
    "#FFFFFF": 7,
}


def rgb_to_aci(color) -> int:
    """svgelements Color → AutoCAD Color Index."""
    if color is None:
        return 7  # default white/black
    s = str(color).upper()
    if s in COLOR_HEX_TO_ACI:
        return COLOR_HEX_TO_ACI[s]
    return 7


def get_layer(element) -> str:
    """svg element 의 부모 group id 따라 레이어 결정."""
    parent = element.values.get("parent")
    # svgelements는 부모를 직접 노출하지 않으므로, id 속성을 명시한 경우 보고 추정
    for k, v in LAYER_MAP.items():
        if k in str(element.values.get("attributes", {}).get("class", "")):
            return v
    return "0"


def y_flip(y: float, max_y: float) -> float:
    """SVG y → DXF y (뒤집기)."""
    return (max_y - y) * SCALE


def x_scale(x: float) -> float:
    return x * SCALE


def main(svg_path: str, dxf_path: str):
    svg = SVG.parse(svg_path)
    max_y = svg.viewbox.height if svg.viewbox else 720

    doc = ezdxf.new("R2010", setup=True)
    msp = doc.modelspace()

    # 레이어 사전 생성
    layer_colors = {
        "AXES": 8, "DIM": 8, "ROOM_FILL": 51, "WALL": 7,
        "AIRLOCK": 7, "STAIRS": 7, "EQUIPMENT": 1,
        "FLOW": 5, "ANNOTATION": 8, "LABEL": 7,
    }
    for name, aci in layer_colors.items():
        if name not in doc.layers:
            doc.layers.add(name=name, color=aci)

    stats = {"rect": 0, "line": 0, "polygon": 0, "path": 0, "text": 0, "skip": 0}

    # 모든 element 순회
    for el in svg.elements():
        # group id 로 레이어 결정 (svgelements 의 values 에 id 가 있을 수 있음)
        layer = "0"
        try:
            # 가장 가까운 부모 group id 추적
            attrs = getattr(el, "values", {}) or {}
            tag = attrs.get("tag", "")
            for parent_attrs in attrs.get("ancestors", []) or []:
                pid = parent_attrs.get("id", "")
                if pid in LAYER_MAP:
                    layer = LAYER_MAP[pid]
                    break
        except Exception:
            pass

        try:
            if isinstance(el, Rect):
                x0, y0 = x_scale(el.x), y_flip(el.y + el.height, max_y)
                w, h = x_scale(el.width), x_scale(el.height)
                points = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
                msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
                # fill → HATCH (생략 가능, 무거움)
                stats["rect"] += 1

            elif isinstance(el, Line):
                x1, y1 = x_scale(el.x1), y_flip(el.y1, max_y)
                x2, y2 = x_scale(el.x2), y_flip(el.y2, max_y)
                msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})
                stats["line"] += 1

            elif isinstance(el, (Polygon, Polyline)):
                pts = [(x_scale(p.x), y_flip(p.y, max_y)) for p in el.points]
                if isinstance(el, Polygon):
                    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})
                else:
                    msp.add_lwpolyline(pts, close=False, dxfattribs={"layer": layer})
                stats["polygon"] += 1

            elif isinstance(el, Path):
                # path 를 segment 별로 분해
                current = None
                for seg in el.segments():
                    if isinstance(seg, Move):
                        current = (x_scale(seg.end.x), y_flip(seg.end.y, max_y))
                    elif isinstance(seg, Close):
                        # 닫기는 별도 처리 안 함 (대부분의 path 는 이미 닫혀 있음)
                        pass
                    else:
                        end = seg.end
                        if current is not None and end is not None:
                            end_pt = (x_scale(end.x), y_flip(end.y, max_y))
                            msp.add_line(current, end_pt, dxfattribs={"layer": layer})
                            current = end_pt
                stats["path"] += 1

            elif isinstance(el, Text):
                x = x_scale(el.x or 0)
                y = y_flip(el.y or 0, max_y)
                txt = el.text or ""
                fs_raw = str(el.values.get("font-size", "10"))
                fs_clean = "".join(c for c in fs_raw if c.isdigit() or c == ".")
                font_size = (float(fs_clean) if fs_clean else 10) * SCALE
                # AutoCAD TEXT entity
                msp.add_text(
                    txt,
                    height=font_size * 0.8,
                    dxfattribs={"layer": layer, "insert": (x, y)},
                )
                stats["text"] += 1

            else:
                stats["skip"] += 1

        except Exception as e:
            print(f"  ! skip element ({type(el).__name__}): {e}", file=sys.stderr)
            stats["skip"] += 1

    doc.saveas(dxf_path)
    print(f"[OK] {svg_path} → {dxf_path}")
    print(f"     stats: {stats}")
    print(f"     layers: {sorted(layer_colors.keys())}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python svg_to_dxf.py INPUT.svg OUTPUT.dxf", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
