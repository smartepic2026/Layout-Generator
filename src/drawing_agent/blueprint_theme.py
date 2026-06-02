"""블루프린트(다크 CAD) 테마 — 라이트 SVG 를 다크 네이비 배경으로 후처리.

발견: 등급/동선 색(Emerald/Amber/Blue + indigo/teal/rose/violet)은 다크 배경에서
그대로 네온 액센트로 작동한다. 따라서 NEUTRAL 팔레트(배경·그리드·벽·텍스트)만
다크 등가로 치환하면 첨부 레퍼런스풍 블루프린트가 된다. (렌더러 무수정, 비파괴 후처리)
"""
from __future__ import annotations

# NEUTRAL 토큰 → 다크 등가. 등급(GRADE)·동선(FLOW)·장비 빨강은 유지(네온 액센트).
_MAP = {
    "#FAFAF9": "#0A0F1E",   # NEUTRAL 50  배경
    "#FFFFFF": "#0C1426",   # NEUTRAL 0   흰 패널/도어 마스크
    "#F5F5F4": "#141E36",   # NEUTRAL 100 minor grid
    "#E7E5E4": "#1C2742",   # NEUTRAL 200 major grid + NC fill
    "#A8A29E": "#5E7099",   # NEUTRAL 400 NC 보더/틱
    "#57534E": "#9DB2D8",   # NEUTRAL 600 텍스트
    "#292524": "#C7D6F0",   # NEUTRAL 800 텍스트
    "#1C1917": "#E8EEFB",   # NEUTRAL 900 벽 + 주 텍스트
}


def to_blueprint(svg: str) -> str:
    """라이트 SVG → 다크 블루프린트 SVG (NEUTRAL 색만 치환)."""
    out = svg
    # 대소문자 양쪽 치환 (렌더러가 대문자 hex 사용하지만 안전하게)
    for light, dark in _MAP.items():
        out = out.replace(light, dark).replace(light.lower(), dark)
    return out
