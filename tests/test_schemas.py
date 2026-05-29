"""Smoke tests for Pydantic schemas (URSInput + RuleEngineOutput)."""
from src.rule_engine.schemas import (
    URSInput,
    RuleEngineOutput,
    Room,
    Airlock,
    Adjacency,
    FlowPaths,
    Zones,
    Constraints,
    RangeMM,
    Rationale,
)


def test_urs_defaults():
    urs = URSInput()
    assert urs.product.modality == "mAb"
    assert urs.building.total_floor_area_m2 == 3300
    assert urs.flow_policy.one_way_flow_required_until == "virus_filtration"
    assert urs.organization.gender_separated_gowning is True


def test_urs_overrides():
    urs = URSInput(
        overrides={
            "force_include_rooms": ["R_DS_STORAGE"],
            "area_overrides_m2": {"R_PURIFICATION_1": 350},
        }
    )
    assert "R_DS_STORAGE" in urs.overrides.force_include_rooms
    assert urs.overrides.area_overrides_m2["R_PURIFICATION_1"] == 350


def test_output_roundtrip_json():
    out = RuleEngineOutput(
        project_name="t",
        modality="mAb",
        rooms=[
            Room(
                id="R_MEDIA_PREP",
                name_ko="배지조제실",
                name_en="Media preparation",
                category="process",
                clean_grade="C",
                area_m2=100,
                volume_m3=300,
            )
        ],
        airlocks=[],
        adjacency=[],
        flow_paths=FlowPaths(),
        zones=Zones(process_zone=["R_MEDIA_PREP"]),
        constraints=Constraints(
            corridor_width_mm=RangeMM(min=1500, preferred_min=2000, preferred_max=3000, max=3000)
        ),
        rationale=[
            Rationale(
                rule_id="rule_4_clean_grade",
                target="R_MEDIA_PREP",
                decision="Grade C",
                reason="주공정 + non-closed system",
            )
        ],
    )
    js = out.model_dump_json()
    back = RuleEngineOutput.model_validate_json(js)
    assert back.rooms[0].id == "R_MEDIA_PREP"
    assert back.rationale[0].rule_id == "rule_4_clean_grade"


def test_room_extra_field_ignored():
    """Extra fields should be silently ignored (extra='ignore' per D-003).

    이전엔 extra='forbid' 였으나 anti-corruption layer (tier1_ruleengine)
    채택 후 ignore 로 완화. 팀원 출력 (rule_engine) 이 우리가 모르는 필드
    (meta, instance_id, severity 등) 를 가져도 깨지지 않도록.
    """
    room = Room(
        id="R_TEST",
        name_ko="t",
        name_en="t",
        category="process",
        clean_grade="C",
        area_m2=10,
        UNKNOWN_FIELD=42,  # type: ignore
    )
    # 모르는 필드는 silently drop 되고, 알려진 필드는 정상 보존
    assert room.id == "R_TEST"
    assert not hasattr(room, "UNKNOWN_FIELD")
