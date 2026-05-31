"""DESIGN.md → 코드 토큰. 모든 SVG 출력은 이 모듈만 참조.

마법 숫자/색 금지. 변경은 여기서만.
"""
from __future__ import annotations

from src.contract.kb_loader import grade_colors_kb

# ──────────────────────────────────────────────────────────────────────
# Colors (DESIGN.md §2)
# ──────────────────────────────────────────────────────────────────────
_kb = grade_colors_kb()

NEUTRAL = _kb["neutral_scale"]  # {"0": "#FFFFFF", ..., "900": "#1C1917"}
SEMANTIC = _kb["semantic"]      # ok / warning / violation / info

GRADE = _kb["grades"]
"""각 등급은 {fill, border, label, pattern, pattern_color, transparency_pct}.
   fill은 50% opacity 권장."""

FLOW = {k: v["hex"] for k, v in _kb["flow_colors"].items()}
"""personnel / material / waste / product → hex"""

PRESSURE_SCALE = _kb["pressure_scale"]  # 5단계 sequential blues

# ──────────────────────────────────────────────────────────────────────
# Typography (DESIGN.md §3)
# ──────────────────────────────────────────────────────────────────────
FONT_DISPLAY = '"Inter","Pretendard",-apple-system,"Helvetica Neue",sans-serif'
FONT_BODY = FONT_DISPLAY
FONT_MONO = '"JetBrains Mono","SF Mono",Menlo,monospace'

TEXT = {
    "xs": 10,
    "sm": 12,
    "base": 14,
    "md": 16,
    "lg": 20,
    "xl": 28,
    "2xl": 40,
}

# ──────────────────────────────────────────────────────────────────────
# Spacing (DESIGN.md §4) — 8pt grid
# ──────────────────────────────────────────────────────────────────────
GRID = 8
SP = {n: n * GRID // 8 for n in (4, 8, 12, 16, 24, 32, 48, 64, 96, 128)}
# 그대로: SP[4]=4, SP[8]=8, ...

# 도면 캔버스 그리드 (실측 mm 기준)
MM_MINOR = 1000  # 1000mm = 1m
MM_MAJOR = 5000  # 5000mm = 5m

# 캔버스 padding (SVG outside building)
CANVAS_PAD = 64

# ──────────────────────────────────────────────────────────────────────
# Stroke weights (DESIGN.md §5) — 단위 px (SVG user units)
# ──────────────────────────────────────────────────────────────────────
STROKE = {
    "building_outline": 5.0,   # ↑ from 3.0 — heavy black outline
    "outer_wall": 4.0,         # ↑ from 2.5
    "inner_wall": 3.5,         # ↑ from 1.5 — match GMP convention thick walls
    "door": 1.5,
    "door_swing": 0.75,
    "equipment": 1.0,
    "dimension": 0.5,
    "grid_major": 1.0,
    "grid_minor": 0.5,
}

# ──────────────────────────────────────────────────────────────────────
# Render scale (mm → SVG user unit)
# ──────────────────────────────────────────────────────────────────────
# SVG는 dimensionless. 화면용 적정 스케일: 1mm = 0.012 user unit (≈ 1:84)
# 78500mm × 42500mm 건물 → 942 × 510 unit (브라우저 친화적 크기)
SCALE_MM_TO_UNIT = 0.016


def mm(value_mm: float) -> float:
    """mm → SVG unit. layout solver는 mm로 작업, 렌더만 변환."""
    return value_mm * SCALE_MM_TO_UNIT
