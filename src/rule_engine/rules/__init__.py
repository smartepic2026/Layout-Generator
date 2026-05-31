"""rules — 14개 룰 모듈 (Excel "Layout 설계 원리" 12개 + 환기횟수 + 출입복장).

각 모듈은 apply 함수 1개씩 제공한다. engine.py 가 정의된 순서로 호출한다.
모듈 분리 원칙: 한 룰 = 한 파일. 룰 본문이 50줄을 넘기지 않는 한 분리하지 않는다.

룰 ↔ Excel 매핑 (보고서 v0.2 §3.2 함수 매핑 표 참조):
    01 layout_axis    — 룰 1 (전체 배열 컨셉)
    02 room_shape     — 룰 2 (Room 구성)
    03 room_size      — 룰 3 (Room 크기)
    04 clean_grade    — 룰 4 (청정등급)         [passthrough+flag]
    05 zones          — 룰 5 (Room 배열)
    06 airlocks       — 룰 6 (전실 배열)
    07 al_flow_type   — 룰 7 (전실 흐름 타입)
    08 corridors      — 룰 8 (복도 배열)
    09 doors          — 룰 9 (도어 위치)
    10 equipment      — 룰 10 (제조 장비 배치)
    11 wash_prep      — 룰 11 (세척실·준비실)
    12 nc_rooms       — 룰 12 (NC 구역)
    13 pressure       — 룰 13 (차압 cascade)
    14 acph           — 환기횟수 시트            [passthrough+flag]
    15 gowning        — 출입복장 시트            [passthrough+flag]
"""
from __future__ import annotations

from . import (
    rule_01_layout_axis,
    rule_02_room_shape,
    rule_03_room_size,
    rule_04_clean_grade,
    rule_05_zones,
    rule_06_airlocks,
    rule_07_al_flow_type,
    rule_08_corridors,
    rule_09_doors,
    rule_10_equipment,
    rule_11_wash_prep,
    rule_12_nc_rooms,
    rule_13_pressure,
    rule_14_acph,
    rule_15_gowning,
)

__all__ = [
    "rule_01_layout_axis",
    "rule_02_room_shape",
    "rule_03_room_size",
    "rule_04_clean_grade",
    "rule_05_zones",
    "rule_06_airlocks",
    "rule_07_al_flow_type",
    "rule_08_corridors",
    "rule_09_doors",
    "rule_10_equipment",
    "rule_11_wash_prep",
    "rule_12_nc_rooms",
    "rule_13_pressure",
    "rule_14_acph",
    "rule_15_gowning",
]
