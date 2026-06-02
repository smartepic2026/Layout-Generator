"""블루프린트(다크 CAD) 테마 — 라이트 SVG 를 다크 네이비 배경으로 후처리.

레퍼런스 분석: 방 *내부*는 배경에 가깝게 매우 어둡고(near-transparent), *외곽선*은
밝은 네온(emerald/amber/blue) 이다. 따라서:
  1) NEUTRAL(배경·그리드·벽·텍스트) → 다크 등가 치환
  2) 방 fill 불투명도 대폭 ↓ (내부 어둡게)
  3) 등급 border(어두운 색) → 밝은 네온 등급색 (외곽선 강조)
등급 fill 의 hue 는 유지(저불투명도라 다크 틴트로 남음). 렌더러 무수정, 비파괴 후처리.
"""
from __future__ import annotations

# NEUTRAL 토큰 → 다크 등가.
_NEUTRAL = {
    "#FAFAF9": "#0A0F1E",   # 50  배경
    "#FFFFFF": "#0C1426",   # 0   흰 패널/도어 마스크
    "#F5F5F4": "#141E36",   # 100 minor grid
    "#E7E5E4": "#1C2742",   # 200 major grid + NC fill
    "#A8A29E": "#5E7099",   # 400 NC 보더/틱
    "#57534E": "#9DB2D8",   # 600 텍스트
    "#292524": "#C7D6F0",   # 800 텍스트
    "#1C1917": "#E8EEFB",   # 900 벽 + 주 텍스트
}

# 등급 border(어두움) → 밝은 네온 등급색 (외곽선 강조)
_BORDER_BRIGHT = {
    "#047857": "#34D399",   # A border  → emerald bright
    "#059669": "#34D399",   # B border  → emerald bright
    "#D97706": "#FBBF24",   # C border  → amber bright
    "#2563EB": "#60A5FA",   # D border  → blue bright
    "#78716C": "#A8A29E",   # CNC border→ stone
}


def to_blueprint(svg: str) -> str:
    """라이트 SVG → 다크 블루프린트 SVG."""
    out = svg
    for light, dark in {**_NEUTRAL, **_BORDER_BRIGHT}.items():
        out = out.replace(light, dark).replace(light.lower(), dark)
    # 방/에어록 내부 어둡게 — fill-opacity 0.50 → 0.13 (배경에 가깝게)
    out = out.replace('fill-opacity="0.50"', 'fill-opacity="0.13"')
    return out
