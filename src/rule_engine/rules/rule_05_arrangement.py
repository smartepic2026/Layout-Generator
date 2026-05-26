"""Rule 5 — Room 배열 (Arrangement / Zoning).

근거: GMP Layout Logic_0510 §5
- 공정 구역 = 직접 제조 + 세척/준비 + 동선용 Room (복도 포함)
- 보조 구역 = 보관/갱의/IPC/CIP 등
- NC 구역 = 화장실/사무실/모니터링/로비
- 공정 Room 배치는 process flow 우선
- 도어는 출입실 동선이 짧은 위치

이 룰은:
- KB.process_order 를 product_process_order로 등록
- 카테고리별로 zones[].process_zone / auxiliary_zone / nc_zone 분리
- 동선(personnel/material/waste) 1차 시퀀스 채움

좌표 결정은 Drawing Agent의 책임이지만, "boundary anchor" 힌트는 axis에서 옴.
"""
from __future__ import annotations

from ..kb_loader import rooms_kb
from ..working_state import WorkingState


def apply(state: WorkingState) -> None:
    modality = state.urs.product.modality
    kb = rooms_kb(modality)

    # ---- Zones ----
    state.zones.process_zone = [rid for rid, r in state.rooms.items() if r.category == "process"]
    state.zones.auxiliary_zone = [rid for rid, r in state.rooms.items() if r.category == "auxiliary"]
    state.zones.nc_zone = [rid for rid, r in state.rooms.items() if r.category == "NC"]

    state.log(
        rule_id="rule_5_arrangement",
        target="zones",
        decision=(
            f"process={len(state.zones.process_zone)}, "
            f"auxiliary={len(state.zones.auxiliary_zone)}, "
            f"NC={len(state.zones.nc_zone)}"
        ),
        reason="카테고리별 zoning. 보조구역은 입구 가까운 쪽, NC는 별도 영역.",
        source="GMP Layout Logic_0510 §5 Room 배열",
    )

    # ---- Process order (제품 동선) ----
    order = [rid for rid in kb["process_order"] if state.has_room(rid)]
    state.process_order_ids = order
    state.flow_paths.product_process_order = order

    state.log(
        rule_id="rule_5_arrangement",
        target="product_process_order",
        decision=" → ".join(order),
        reason="mAb 공정 순서 (KB.process_order). Drawing Agent가 supply corridor 따라 정렬.",
    )

    # ---- 동선 1차 시퀀스 (Phase 2에서 airlock/corridor 추가 후 정제됨) ----
    # personnel_entry: 로비 → 갱의실 → AUX_PAL → 공급복도 → PAL_IN → Room
    # personnel_exit:  Room → PAL_OUT → 리턴복도 → 갱의실 → 로비
    # material_entry: EXT → 자재반입실 → 자재보관실 → MAL_IN → Room
    # waste_exit: Room → MAL_OUT → 리턴복도 → 폐기물반출실 → EXT

    def opt(rid: str) -> list[str]:
        return [rid] if state.has_room(rid) else []

    state.flow_paths.personnel_entry = (
        opt("R_LOBBY")
        + opt("R_GOWNING_FEMALE")
        + opt("R_GOWNING_MALE")
        + opt("R_GOWNING_PROCESS")
        + opt("R_SUPPLY_CORRIDOR")
        + ["<process_room>"]
    )
    state.flow_paths.personnel_exit = (
        ["<process_room>"]
        + opt("R_RETURN_CORRIDOR")
        + opt("R_GOWNING_PROCESS")
        + opt("R_GOWNING_FEMALE")
        + opt("R_LOBBY")
    )
    state.flow_paths.material_entry = (
        ["<EXT>"]
        + opt("R_MATERIAL_INLET")
        + opt("R_MATERIAL_STORAGE")
        + opt("R_SUPPLY_CORRIDOR")
        + ["<process_room>"]
    )
    state.flow_paths.waste_exit = (
        ["<process_room>"]
        + opt("R_RETURN_CORRIDOR")
        + opt("R_WASTE_OUTLET")
        + ["<EXT>"]
    )

    state.log(
        rule_id="rule_5_arrangement",
        target="flow_paths",
        decision="4종 동선 1차 시퀀스 채움 (Phase 6에서 airlock 삽입 후 정제)",
        reason="공정 Room 진입 전 보조구역·갱의·복도 거치는 원칙 (§1 전체 배열 컨셉).",
    )
