"""Rule 12 — NC 구역 배치.

근거: GMP Layout Logic_0510 §12
- 화장실/사무실/모니터링/로비/관람복도/휴게실 등
- 공정구역·보조구역 형태에 방해되지 않는 별도 영역
- 별도 층/건물에 배치 계획 있으면 생략 가능

이 룰은 URS.organization의 include_*_onsite 플래그로 NC Room 포함/제외를 검증.
누락된 필수 NC가 있으면 경고 로그.
"""
from __future__ import annotations

from ..working_state import WorkingState

NC_ROOMS = [
    ("R_LOBBY",            "include_lobby_onsite",            "로비"),
    ("R_OFFICE",           "include_office_onsite",           "사무실"),
    ("R_MONITORING",       "include_monitoring_room_onsite",  "모니터링실"),
    ("R_TOILET_FEMALE",    "include_toilet_onsite",           "화장실(여)"),
    ("R_TOILET_MALE",      "include_toilet_onsite",           "화장실(남)"),
    ("R_LOUNGE",           "include_lounge_onsite",           "휴게실"),
]


def apply(state: WorkingState) -> None:
    org = state.urs.organization
    summary = []
    for room_id, flag_name, display in NC_ROOMS:
        flag = getattr(org, flag_name)
        present = state.has_room(room_id)
        if flag and not present:
            state.log(
                rule_id="rule_12_nc",
                target=room_id,
                decision="WARNING: 누락",
                reason=f"organization.{flag_name}=True 인데 {display} 미존재. select_required_rooms 점검.",
            )
        elif not flag and present:
            state.log(
                rule_id="rule_12_nc",
                target=room_id,
                decision="WARNING: 불필요한 포함",
                reason=f"organization.{flag_name}=False 인데 {display} 존재.",
            )
        if flag:
            summary.append(display)

    # NC Room들은 별도 zone (이미 rule_5에서 분리됨). 여기선 확정 로그만.
    state.log(
        rule_id="rule_12_nc",
        target="nc_zone",
        decision=f"NC 구역 {len(state.zones.nc_zone)}개: {', '.join(state.zones.nc_zone) or '(없음)'}",
        reason=(
            "별도 영역으로 분리. 공정·보조구역 형태에 방해되지 않도록 외곽 또는 별도 층 권장. "
            f"활성화된 NC 기능: {', '.join(summary) or '없음'}"
        ),
        source="GMP Layout Logic_0510 §12 NC 구역",
    )
