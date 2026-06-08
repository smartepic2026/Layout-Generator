from __future__ import annotations

from pathlib import Path

import pytest

from src.contract.schemas import RuleEngineOutput
from src.drawing_agent.data.tier1_ruleengine import adapt_external_dict
from src.drawing_agent.floorplan import generate_floorplan
from src.drawing_agent.validators import validate_layout


def _teamlead_specs() -> list[Path]:
    paths = sorted(Path("output/audit_0608").glob("urs_0607-*_spec.json"))
    if not paths:
        pytest.skip("teamlead audit specs missing")
    return paths


def test_area_ratio_pct_survives_ruleengine_adapter():
    raw = {
        "rooms": [{
            "room_id": "R_A",
            "name_ko": "A",
            "name_en": "A",
            "cat": "process",
            "grade": "C",
            "area_m2": 300.0,
            "area_ratio_pct": 10.0,
        }],
        "airlocks": [],
        "adjacency": [],
        "flow_paths": {},
        "zones": {},
        "constraints": {"corridor_width_mm": {"min": 1500}},
        "rationale": [],
    }
    spec = RuleEngineOutput.model_validate(adapt_external_dict(raw))
    assert spec.rooms[0].area_ratio_pct == 10.0


def test_teamlead_layouts_have_no_hard_spatial_errors():
    for path in _teamlead_specs():
        spec = RuleEngineOutput.model_validate_json(path.read_text())
        _, layout = generate_floorplan(
            spec,
            dynamic_rooms=True,
            flow_mode="main",
            variant_seed=42,
            variant_index=0,
        )
        errors = [v for v in validate_layout(spec, layout) if v.severity == "error"]
        assert not errors, f"{path.name}: {errors[:5]}"


def test_layout_variants_change_room_arrangement():
    spec = RuleEngineOutput.model_validate_json(_teamlead_specs()[1].read_text())
    signatures = []
    for idx in range(3):
        _, layout = generate_floorplan(
            spec,
            dynamic_rooms=True,
            flow_mode="main",
            variant_seed=42,
            variant_index=idx,
        )
        sig = tuple(
            (rid, round(pr.rect.x), round(pr.rect.y), round(pr.rect.w), round(pr.rect.h))
            for rid, pr in sorted(layout.rooms.items())
            if "CORRIDOR" not in rid
        )
        signatures.append(sig)
    assert len(set(signatures)) == 3
