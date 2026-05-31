"""L1 unit test — rule_07_al_flow_type."""
from __future__ import annotations

import dataclasses

from src.rule_engine.models import AirLock, Rationale
from src.rule_engine.rules import rule_07_al_flow_type


def _make_al(al_id: str, grade: str, kind: str = "PAL_in") -> AirLock:
    return AirLock(
        al_id=al_id, kind=kind, clean_grade=grade,
        area_m2=12.0, flow_type="cascade",
        connects_higher_room=None, connects_lower_room=None,
        purpose="personnel", differential_pressure_Pa=None,
    )


def test_default_cascade_no_isolation(empty_input):
    """biological_safety_isolation=False면 default(cascade) 사용."""
    als = [_make_al("AL_1", "C"), _make_al("AL_2", "B")]
    rationale: list[Rationale] = []

    out = rule_07_al_flow_type.apply(als, [], empty_input, rationale)

    assert all(al.flow_type == "cascade" for al in out)


def test_isolation_grade_b_is_bubble(empty_input):
    """biological_safety_isolation=True + Grade B AL → bubble."""
    fp = dataclasses.replace(
        empty_input.flow_policy, biological_safety_isolation=True
    )
    inp = dataclasses.replace(empty_input, flow_policy=fp)
    als = [_make_al("AL_B", "B")]
    rationale: list[Rationale] = []

    out = rule_07_al_flow_type.apply(als, [], inp, rationale)

    assert out[0].flow_type == "bubble"


def test_isolation_other_grades_are_sink(empty_input):
    """biological_safety_isolation=True + Grade C/D AL → sink."""
    fp = dataclasses.replace(
        empty_input.flow_policy, biological_safety_isolation=True
    )
    inp = dataclasses.replace(empty_input, flow_policy=fp)
    als = [_make_al("AL_C", "C"), _make_al("AL_D", "D")]
    rationale: list[Rationale] = []

    out = rule_07_al_flow_type.apply(als, [], inp, rationale)

    assert out[0].flow_type == "sink"
    assert out[1].flow_type == "sink"


def test_custom_default_type(empty_input):
    """flow_policy.airlock_default_type=sink로 두면 isolation 없어도 sink."""
    fp = dataclasses.replace(
        empty_input.flow_policy, airlock_default_type="sink"
    )
    inp = dataclasses.replace(empty_input, flow_policy=fp)
    als = [_make_al("AL_1", "C")]
    rationale: list[Rationale] = []

    out = rule_07_al_flow_type.apply(als, [], inp, rationale)

    assert out[0].flow_type == "sink"


def test_rationale_per_al(empty_input):
    """각 AL마다 rationale 1줄."""
    als = [_make_al(f"AL_{i}", "C") for i in range(3)]
    rationale: list[Rationale] = []

    rule_07_al_flow_type.apply(als, [], empty_input, rationale)

    assert len(rationale) == 3
    assert all(r.rule_id == "rule_07_al_flow_type" for r in rationale)
