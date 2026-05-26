"""CLI entrypoint.

사용:
  python -m src.cli rule-engine examples/urs_mab_8000L.json output/spec.json
  python -m src.cli rule-engine examples/urs_mab_8000L.json output/spec.json --no-strict
  python -m src.cli validate output/spec.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.rule_engine.engine import run_rule_engine
from src.rule_engine.schemas import RuleEngineOutput, URSInput


def cmd_rule_engine(args: argparse.Namespace) -> int:
    urs_path = Path(args.urs)
    out_path = Path(args.output)

    urs = URSInput.model_validate_json(urs_path.read_text())
    try:
        out = run_rule_engine(urs, strict=args.strict)
    except ValueError as e:
        print(f"[FAIL] Hard constraint violations:\n{e}", file=sys.stderr)
        return 1

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
    svg, layout = generate_floorplan(spec, building_w_mm=args.width, building_h_mm=args.height)
    out = Path(args.svg)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    print(f"[OK]  {args.spec} → {out}")
    print(f"      rooms placed: {len(layout.rooms)}, airlocks: {len(layout.airlocks)}, doors: {len(layout.doors)}")
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

    p_rule = sub.add_parser("rule-engine", help="URS → 7-block spec.json")
    p_rule.add_argument("urs", help="URS input JSON path")
    p_rule.add_argument("output", help="output spec.json path")
    p_rule.add_argument(
        "--no-strict",
        dest="strict",
        action="store_false",
        help="hard constraint 위반 시 raise하지 않고 rationale만 기록",
    )
    p_rule.set_defaults(strict=True, func=cmd_rule_engine)

    p_val = sub.add_parser("validate", help="spec.json 재로드 & 요약")
    p_val.add_argument("spec", help="output spec.json")
    p_val.set_defaults(func=cmd_validate)

    p_draw = sub.add_parser("draw", help="spec.json → SVG floorplan")
    p_draw.add_argument("spec", help="input spec.json")
    p_draw.add_argument("svg", help="output svg path")
    p_draw.add_argument("--width", type=int, default=78500, help="building width (mm)")
    p_draw.add_argument("--height", type=int, default=42500, help="building depth (mm)")
    p_draw.set_defaults(func=cmd_draw)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
