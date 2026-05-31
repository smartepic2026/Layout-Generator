"""End-to-end 데모 — 실제 URS xlsx로 run_rule_engine 한 번 돌려보고 결과 가시화.

2026-05-28 후속 작업: 내장 파서를 `urs_parser.py` 모듈로 승격. 본 파일은
이제 시각화만 담당하고 URS 파싱은 `rule_engine.urs_parser` 에 위임한다.
이전 코드 호환을 위해 `URS_PATH`, `_parse_urs`, `_make_input` 은 본 모듈에
얇은 별칭으로 남겨둔다 (deprecated).

실행:
    python3 -m rule_engine._demo_run
"""
from __future__ import annotations

import sys
from collections import Counter

from src.rule_engine import run_rule_engine
from src.rule_engine.urs_parser import (
    URS_PATH,
    build_rule_engine_input,
    parse_urs_xlsx,
)


# ---------------------------------------------------------------------------
# Backward-compatible aliases (deprecated — 새 코드는 urs_parser 직접 사용).
# ---------------------------------------------------------------------------

_parse_urs = parse_urs_xlsx
_make_input = build_rule_engine_input


def _print_report(output, input_spec):
    """결과를 사람이 읽기 좋게 콘솔 출력."""
    print("=" * 78)
    print("Rule Engine v0.1 — End-to-end Demo Result")
    print("=" * 78)

    meta = output.meta
    print(f"\n[Meta]")
    print(f"  engine_version    : {meta['engine_version']}")
    print(f"  kb_version        : {meta['knowledge_base_version']}")
    print(f"  input_hash        : {meta['input_hash']}")
    print(f"  generated_at      : {meta['generated_at']}")

    stats = meta["stats"]
    print(f"\n[Stats — 7 블록 산출]")
    print(f"  rooms             : {stats['rooms']:>3d}")
    print(f"  airlocks          : {stats['airlocks']:>3d}")
    print(f"  adjacency_edges   : {stats['adjacency_edges']:>3d}")
    print(f"  rationale_entries : {stats['rationale_entries']:>3d}")
    print(f"  flag_counts       : {dict(stats['flag_counts']) or '(none)'}")

    z = output.zones
    print(f"\n[Zones]")
    print(f"  process_zone   ({len(z.process_zone):>2d}): {z.process_zone[:5]}{' …' if len(z.process_zone) > 5 else ''}")
    print(f"  auxiliary_zone ({len(z.auxiliary_zone):>2d}): {z.auxiliary_zone[:5]}{' …' if len(z.auxiliary_zone) > 5 else ''}")
    print(f"  nc_zone        ({len(z.nc_zone):>2d}): {z.nc_zone[:5]}{' …' if len(z.nc_zone) > 5 else ''}")

    print(f"\n[Rooms — derive 결과 샘플 (상위 6개)]")
    print(f"  {'Room':<22} {'Grade':<5} {'area':>6} {'DP':>5} {'ACPH':>5} {'color':<22}")
    for r in output.rooms[:6]:
        area = f"{r.area_m2:.0f}" if r.area_m2 else "-"
        dp = f"{r.differential_pressure_Pa:.0f}" if r.differential_pressure_Pa is not None else "-"
        acph = f"{r.air_changes_per_hour:.0f}" if r.air_changes_per_hour else "-"
        print(f"  {r.name_en:<22} {r.clean_grade:<5} {area:>6} {dp:>5} {acph:>5} {r.background_color or '-':<22}")

    print(f"\n[Airlocks — 상위 5개]")
    print(f"  {'AL ID':<28} {'kind':<10} {'grade':<5} {'flow':<10} {'DP':>5}")
    for al in output.airlocks[:5]:
        dp = f"{al.differential_pressure_Pa:.0f}" if al.differential_pressure_Pa is not None else "-"
        print(f"  {al.al_id:<28} {al.kind:<10} {al.clean_grade:<5} {al.flow_type:<10} {dp:>5}")

    fp = output.flow_paths
    print(f"\n[Flow paths]")
    print(f"  personnel_entry ({len(fp.personnel_entry)}): {' → '.join(fp.personnel_entry[:6])}{' →…' if len(fp.personnel_entry) > 6 else ''}")
    print(f"  material_entry  ({len(fp.material_entry)}): {' → '.join(fp.material_entry[:6])}{' →…' if len(fp.material_entry) > 6 else ''}")
    print(f"  waste_exit      ({len(fp.waste_exit)}): {' → '.join(fp.waste_exit[:6])}{' →…' if len(fp.waste_exit) > 6 else ''}")
    print(f"  product_order   ({len(fp.product_process_order)}): {' → '.join(fp.product_process_order)}")

    rule_counts: Counter = Counter(r.rule_id for r in output.rationale)
    print(f"\n[Rationale — 룰별 적용 횟수]")
    for rid, cnt in sorted(rule_counts.items()):
        flags_in_rule = sum(1 for r in output.rationale if r.rule_id == rid and r.flags)
        marker = f"  ⚠ {flags_in_rule} flag" if flags_in_rule else ""
        print(f"  {rid:<28} {cnt:>3d}{marker}")

    all_flags = [(r.rule_id, f) for r in output.rationale for f in r.flags]
    if all_flags:
        print(f"\n[Flags — 상위 5개]")
        for rid, f in all_flags[:5]:
            print(f"  [{f.severity:<19}] {rid}: {f.note[:80]}")

    rel_counts: Counter = Counter(e.relationship for e in output.adjacency)
    elev_count = sum(1 for e in output.adjacency if e.is_elevator_constraint)
    print(f"\n[Adjacency — {len(output.adjacency)} edges]")
    for rel, cnt in sorted(rel_counts.items()):
        print(f"  {rel:<22} {cnt:>3d}")
    print(f"  (incl. elevator edges  {elev_count:>3d})")


def main() -> int:
    if not URS_PATH.exists():
        print(f"ERROR: URS 파일 없음 — {URS_PATH}", file=sys.stderr)
        return 1
    urs_rooms, urs_equipment, building_info = parse_urs_xlsx(URS_PATH)
    print(f"URS 파싱: rooms={len(urs_rooms)}, equipment={len(urs_equipment)}")

    input_spec = build_rule_engine_input(
        urs_rooms, urs_equipment, building_info
    )
    output = run_rule_engine(input_spec)
    _print_report(output, input_spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
