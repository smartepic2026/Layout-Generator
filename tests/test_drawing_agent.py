"""Drawing Agent v1 smoke tests.

[D-023] 렌더링 경로 = gradient(`dynamic_rooms=True`) — 임의 방집합을 배치하며
실제 방을 누락하지 않는다. 기본값(strip-band)은 baseline 측정용 subset 경로라
일부 방을 떨어뜨리므로(alignment_audit, cli draw 는 --strip 일 때만), 렌더 검증
테스트는 명시적으로 gradient 를 쓴다.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from src.drawing_agent.floorplan import generate_floorplan
from src.drawing_agent.layout_solver import _is_al_fake_room
from tests._legacy_spec import run_rule_engine
from src.contract.schemas import URSInput


def _real_room_ids(spec):
    """전실 중복(rooms[] 에 placeholder 로 존재하는 에어록) 제외한 실제 방 id."""
    return [r.id for r in spec.rooms if not _is_al_fake_room(r)]


def test_floorplan_generation_smoke():
    spec = run_rule_engine(URSInput(), strict=True)
    svg, layout = generate_floorplan(spec, dynamic_rooms=True)

    # SVG가 정상 형식인지
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")

    # AL도 배치 + 도어 생성
    assert len(layout.airlocks) == len(spec.airlocks)
    assert len(layout.doors) > 30


def test_no_real_room_omitted():
    """[정렬 핵심] 룰엔진이 준 실제 방(전실 중복 제외)이 도면에서 누락되지 않음.

    사용자 #2(누락·왜곡 없는 정렬)의 회귀 가드. strip-band 경로가 새 엔진 ID로
    MEDIA/BUFFER 등을 떨어뜨리던 문제(alignment_audit)를 gradient 가 해소.
    """
    spec = run_rule_engine(URSInput(), strict=True)
    _, layout = generate_floorplan(spec, dynamic_rooms=True)
    dropped = [rid for rid in _real_room_ids(spec) if rid not in layout.rooms]
    assert not dropped, f"누락된 실제 방: {dropped}"


def test_svg_contains_grade_colors():
    spec = run_rule_engine(URSInput(), strict=True)
    svg, _ = generate_floorplan(spec, dynamic_rooms=True)
    # DESIGN.md 팔레트의 핵심 색이 SVG에 등장
    assert "#FCD34D" in svg  # Grade C amber-300
    assert "#93C5FD" in svg  # Grade D blue-300


def test_svg_contains_room_labels():
    spec = run_rule_engine(URSInput(), strict=True)
    svg, _ = generate_floorplan(spec, dynamic_rooms=True)
    # 주요 Room 영문명이 모두 등장 (누락 없이)
    for n in ["Media preparation", "Cell Culture", "Purification 1", "Purification 2", "Supply corridor"]:
        assert n in svg, f"missing label: {n}"


def test_flow_arrows_follow_flow_paths():
    """[G1 해소] 동선 화살표가 spec.flow_paths 4종을 렌더 (방 id 패턴 휴리스틱 아님).

    product_process_order 는 공정실들을 연결한다. renderer 는 끊김 방지를 위해
    구간별 line 이 아니라 연결된 path 로 그리므로, marker 개수 대신 flow group 과
    product path 존재 여부를 확인한다.
    """
    spec = run_rule_engine(URSInput(), strict=True)
    svg, _ = generate_floorplan(spec, dynamic_rooms=True)
    for k in ("personnel", "material", "waste", "product"):
        assert f"arrow-{k}" in svg, f"missing flow marker: {k}"
    assert 'class="flow flow-product"' in svg
    assert 'stroke="#F97316"' in svg
    assert 'marker-end="url(#arrow-product)"' in svg


def test_svg_contains_legend_and_titleblock():
    spec = run_rule_engine(URSInput(), strict=True)
    svg, _ = generate_floorplan(spec, dynamic_rooms=True)
    assert "LEGEND" in svg
    assert "PROJECT" in svg
    assert "MODALITY" in svg


def test_svg_is_valid_xml_with_sink_airlocks():
    """Airlock sink labels include '<'; renderer must XML-escape text."""
    spec = run_rule_engine(URSInput(), strict=True)
    for airlock in spec.airlocks:
        airlock.flow_type = "sink"
    svg, _ = generate_floorplan(spec, dynamic_rooms=True)
    ET.fromstring(svg)
    assert "&gt;|&lt; sink" in svg


def test_no_room_overflow_after_clip():
    """clipPath가 배치된 방마다 정의되어 있는지 확인."""
    spec = run_rule_engine(URSInput(), strict=True)
    svg, layout = generate_floorplan(spec, dynamic_rooms=True)
    clips = re.findall(r'clipPath id="clip_(R_[A-Z_0-9]+)"', svg)
    assert len(clips) == len(layout.rooms)
