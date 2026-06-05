"""CLI entrypoint.

사용:
  python -m src.cli rule-engine examples/teammate_urs_0516.xlsx output/spec.json
  python -m src.cli draw output/spec.json output/floorplan.svg
  python -m src.cli validate output/spec.json

[2026-06-01 통합] rule-engine 은 이제 소연 엔진(src/rule_engine, dataclass)을
URS xlsx 로 돌린 뒤, tier1 어댑터로 우리 내부 계약(src/contract/schemas.py,
pydantic)으로 변환해 spec.json 을 쓴다. draw/validate 는 그 pydantic spec 을
그대로 읽으므로 변경 없음 (anti-corruption layer, CLAUDE.md D-003).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.contract.schemas import RuleEngineOutput


def cmd_rule_engine(args: argparse.Namespace) -> int:
    """URS xlsx → 소연 엔진 → (to_json) → tier1 어댑터 → 우리 pydantic spec.json."""
    from src.rule_engine import run_rule_engine
    from src.rule_engine.urs_parser import load_urs_as_input
    from src.drawing_agent.data.tier1_ruleengine import adapt_external_dict

    urs_path = Path(args.urs)
    out_path = Path(args.output)

    # 1) URS xlsx → 소연 RuleEngineInput → 소연 엔진 실행 (her dataclass output)
    inp = load_urs_as_input(path=urs_path)
    her_out = run_rule_engine(inp)

    # 2) 소연 출력(dataclass→JSON) → anti-corruption 어댑터 → 우리 pydantic 계약
    her_dict = json.loads(her_out.to_json())
    out = RuleEngineOutput.model_validate(adapt_external_dict(her_dict))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out.model_dump_json(indent=2))

    print(f"[OK]  {urs_path} → {out_path}")
    print(f"      rooms={len(out.rooms)}, airlocks={len(out.airlocks)}, "
          f"adjacency={len(out.adjacency)}, rationale={len(out.rationale)}")
    print(f"      zones: process={len(out.zones.process_zone)}, "
          f"aux={len(out.zones.auxiliary_zone)}, NC={len(out.zones.nc_zone)}")
    return 0


def cmd_draw(args: argparse.Namespace) -> int:
    from src.drawing_agent.floorplan import generate_floorplan

    spec = RuleEngineOutput.model_validate_json(Path(args.spec).read_text())
    # [D-023] 기본 = gradient 토폴로지(임의 방집합 배치, 방 누락 0). 레거시
    # strip-band(공정순서 하드코딩)는 일부 방을 떨어뜨리므로 --strip 일 때만.
    svg, layout = generate_floorplan(
        spec, building_w_mm=args.width, building_h_mm=args.height,
        dynamic_rooms=not args.strip, flow_mode=args.flows,
    )
    out = Path(args.svg)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    # 정렬 점검: 룰엔진이 준 실제 방 중 도면에서 누락된 것 보고
    from src.drawing_agent.layout_solver import _is_al_fake_room
    dropped = [r.id for r in spec.rooms
               if r.id not in layout.rooms and not _is_al_fake_room(r)]
    print(f"[OK]  {args.spec} → {out}")
    print(f"      rooms placed: {len(layout.rooms)}, airlocks: {len(layout.airlocks)}, doors: {len(layout.doors)}")
    if dropped:
        print(f"      [WARN] 배치 누락된 실제 방 {len(dropped)}: {dropped}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """저장된 spec.json을 다시 로드해서 (deserialization sanity)."""
    p = Path(args.spec)
    out = RuleEngineOutput.model_validate_json(p.read_text())
    print(f"[OK]  {p} loads cleanly")
    print(f"      project={out.project_name}, modality={out.modality}")
    print(f"      rooms={len(out.rooms)}, airlocks={len(out.airlocks)}, "
          f"adjacency={len(out.adjacency)}, rationale={len(out.rationale)}")

    # Hard constraint 위반(rationale에 WARNING)이 있는지 보고
    warnings = [r for r in out.rationale if "WARNING" in r.decision]
    if warnings:
        print(f"      WARNINGs in rationale: {len(warnings)}")
        for w in warnings[:5]:
            print(f"        [{w.rule_id}] {w.target}: {w.decision}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="layout-generator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rule = sub.add_parser("rule-engine", help="URS xlsx → 7-block spec.json (소연 엔진)")
    p_rule.add_argument("urs", help="URS input xlsx path (e.g. examples/teammate_urs_0516.xlsx)")
    p_rule.add_argument("output", help="output spec.json path")
    p_rule.set_defaults(func=cmd_rule_engine)

    p_val = sub.add_parser("validate", help="spec.json 재로드 & 요약")
    p_val.add_argument("spec", help="output spec.json")
    p_val.set_defaults(func=cmd_validate)

    p_draw = sub.add_parser("draw", help="spec.json → SVG floorplan")
    p_draw.add_argument("spec", help="input spec.json")
    p_draw.add_argument("svg", help="output svg path")
    p_draw.add_argument("--width", type=int, default=78500, help="building width (mm)")
    p_draw.add_argument("--height", type=int, default=42500, help="building depth (mm)")
    p_draw.add_argument("--strip", action="store_true",
                        help="레거시 strip-band 토폴로지 강제 (기본=gradient, 방 누락 0)")
    p_draw.add_argument("--flows", choices=["full", "main", "off"], default="full",
                        help="동선 표현: full=공정실별 comb(기본), main=대표1경로, off=없음")
    p_draw.set_defaults(func=cmd_draw)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
