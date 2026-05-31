"""L1 unit test — rag_validator.

핸드오프 (2026-05-28): RAG 검색 결과 분기 — high/medium/low/empty similarity
4 가지 케이스를 모의 search 함수로 재현하여 verdict 매핑을 검증.

minirunner 호환을 위해 autouse / indirect parametrize 같은 고급 기능은 쓰지 않음.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.rag_interface.models import Chunk, SearchQuery, SearchResult
from src.rule_engine.validation_interface import ValidationVerdict
from src.rule_engine.validators import (
    RagValidatorConfig,
    make_rag_validator,
)


# ---------------------------------------------------------------------------
# 헬퍼 — 결정론적 SearchResult 빌더
# ---------------------------------------------------------------------------

def _chunk(similarity: float, chunk_id: str = "EU_GMP_Annex_1_2022_chunk_17") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text="Grade A zones shall be designed to ...",
        source="EU_GMP_Annex_1_2022",
        section="4.29",
        page=17,
        similarity=similarity,
        metadata={"year": 2022, "doc_type": "regulatory"},
        collection="regulatory_docs",
    )


def _result(query: SearchQuery, sims: list[float]) -> SearchResult:
    chunks = [_chunk(s, f"chunk_{i}") for i, s in enumerate(sims)]
    return SearchResult(
        query=query,
        chunks=chunks,
        total_hits=len(chunks),
        avg_similarity=(sum(sims) / len(sims)) if sims else 0.0,
        status="ok" if sims else "insufficient_evidence",
        warning=None,
        search_duration_ms=1.0,
        timestamp=datetime(2026, 5, 28),
    )


def _make_search(sim_for_rule: dict[str, list[float]]) -> Callable[[SearchQuery], SearchResult]:
    """rule_id 키로 유사도 배열을 반환하는 모의 search 함수.

    매칭되는 키가 없으면 빈 결과 (insufficient_evidence).
    """
    def _search(q: SearchQuery) -> SearchResult:
        # context_tags[0] 가 rule_id.
        rid = q.context_tags[0] if q.context_tags else ""
        sims = sim_for_rule.get(rid, [])
        return _result(q, sims)
    return _search


def _write_output(tmp: Path, rationale: list[dict]) -> Path:
    """최소한의 RuleEngineOutput JSON 파일을 작성."""
    data = {
        "meta": {"input_hash": "h_abc", "stats": {"flag_counts": {}}},
        "rationale": rationale,
    }
    p = tmp / "output.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 검증 시나리오들
# ---------------------------------------------------------------------------

def test_high_similarity_marks_confirmed_violation():
    """top similarity >= 0.5 면 confirmed_violation 으로 분기되어 needs_revision."""
    search = _make_search({"rule_03_room_size": [0.83, 0.71]})
    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_03_room_size",
                "target_id": "R_INOC",
                "decision": "ceiling too low",
                "input_facts": {},
                "applied_logic": "...",
                "source_reference": "EU GMP",
                "flags": [
                    {"rule_id": "rule_03_room_size",
                     "severity": "suspected_violation",
                     "note": "ceiling height 2400mm < required 2700mm"},
                ],
            },
        ])
        v = validator(p)
    assert isinstance(v, ValidationVerdict)
    assert v.status == "needs_revision"
    assert len(v.acknowledged_flags) == 1
    ack = v.acknowledged_flags[0]
    assert ack.verdict == "confirmed_violation"
    assert ack.rule_id == "rule_03_room_size"
    assert tuple(ack.rule_engine_flag_index) == (0, 0)
    assert ack.rag_citations  # 비어있지 않아야


def test_medium_similarity_marks_needs_user_review():
    """0.2 <= sim < 0.5 면 needs_user_review (보수적으로 needs_revision)."""
    search = _make_search({"rule_07_al_flow_type": [0.31]})
    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_07_al_flow_type",
                "target_id": "AL_001",
                "decision": "...",
                "input_facts": {},
                "applied_logic": "...",
                "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_07_al_flow_type",
                     "severity": "warning",
                     "note": "cascade type mismatch"},
                ],
            },
        ])
        v = validator(p)
    assert v.acknowledged_flags[0].verdict == "needs_user_review"
    assert v.status == "needs_revision"


def test_low_similarity_marks_false_alarm():
    """sim < 0.2 면 false_alarm — 다른 flag 없으면 status=pass."""
    search = _make_search({"rule_05_zones": [0.05]})
    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_05_zones",
                "target_id": "R_X",
                "decision": "...",
                "input_facts": {},
                "applied_logic": "...",
                "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_05_zones",
                     "severity": "suspected_violation",
                     "note": "category mismatch"},
                ],
            },
        ])
        v = validator(p)
    assert v.acknowledged_flags[0].verdict == "false_alarm"
    assert v.status == "pass"


def test_empty_rag_marks_false_alarm():
    """RAG 결과가 0 chunk 면 false_alarm."""
    search = _make_search({})  # 모든 query 에 대해 empty
    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_99_unknown",
                "target_id": "X",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_99_unknown",
                     "severity": "suspected_violation",
                     "note": "??"},
                ],
            },
        ])
        v = validator(p)
    assert v.acknowledged_flags[0].verdict == "false_alarm"
    assert v.acknowledged_flags[0].rag_citations == []


def test_info_severity_skipped_without_rag_call():
    """severity=info 는 RAG 호출 없이 자동 false_alarm 처리."""
    calls: list[SearchQuery] = []

    def search(q):
        calls.append(q)
        return _result(q, [0.9])  # 호출되면 high

    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_01_layout_axis",
                "target_id": "global",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_01_layout_axis",
                     "severity": "info",
                     "note": "just an info"},
                ],
            },
        ])
        v = validator(p)
    assert calls == []  # info 는 RAG 호출 X
    assert v.acknowledged_flags[0].verdict == "false_alarm"
    assert v.status == "pass"


def test_no_flags_means_pass():
    """rationale 에 flag 가 전혀 없으면 status=pass, ack 도 비어있음."""
    search = _make_search({})
    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_01_layout_axis",
                "target_id": "global",
                "decision": "ok", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [],
            },
        ])
        v = validator(p)
    assert v.acknowledged_flags == []
    assert v.status == "pass"


def test_multiple_flags_indexed_correctly():
    """한 rationale 안에 여러 flag 가 있을 때 (rationale_idx, flag_idx) 가 올바르게 부여됨."""
    search = _make_search({
        "rule_03_room_size": [0.9],   # 첫 번째 → confirmed
        "rule_13_pressure": [0.05],   # 두 번째 → false
    })
    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_03_room_size",
                "target_id": "R_A",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_03_room_size",
                     "severity": "suspected_violation", "note": "ceiling"},
                    {"rule_id": "rule_03_room_size",
                     "severity": "warning", "note": "area"},
                ],
            },
            {
                "rule_id": "rule_13_pressure",
                "target_id": "R_B",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_13_pressure",
                     "severity": "suspected_violation", "note": "DP"},
                ],
            },
        ])
        v = validator(p)
    # 3 개 flag — 인덱스 0,0 / 0,1 / 1,0
    assert len(v.acknowledged_flags) == 3
    idxs = [tuple(a.rule_engine_flag_index) for a in v.acknowledged_flags]
    assert idxs == [(0, 0), (0, 1), (1, 0)]
    # rule_03 두 flag 는 같은 SearchQuery (rule_id 동일) → 같은 high sim → confirmed
    assert v.acknowledged_flags[0].verdict == "confirmed_violation"
    assert v.acknowledged_flags[1].verdict == "confirmed_violation"
    assert v.acknowledged_flags[2].verdict == "false_alarm"
    # confirmed 가 1개라도 있으면 status=needs_revision
    assert v.status == "needs_revision"


def test_verdict_preserves_input_hash():
    """ValidationVerdict.rule_engine_input_hash 는 output JSON 의 meta.input_hash 사용."""
    search = _make_search({})
    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [])
        v = validator(p)
    assert v.rule_engine_input_hash == "h_abc"


def test_config_thresholds_respected():
    """RagValidatorConfig 의 임계값을 바꾸면 verdict 분기 점이 이동."""
    # 기본값에서 0.4 는 medium → review.
    # 하지만 confirmed 임계값을 0.3 으로 낮추면 0.4 는 confirmed 가 되어야 함.
    search = _make_search({"rule_X": [0.4]})
    cfg = RagValidatorConfig(min_similarity_confirmed=0.3)
    validator = make_rag_validator(rag_search=search, config=cfg)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_X", "target_id": "T",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_X",
                     "severity": "suspected_violation", "note": "..."},
                ],
            },
        ])
        v = validator(p)
    assert v.acknowledged_flags[0].verdict == "confirmed_violation"


def test_regulatory_only_routes_collection():
    """regulatory_only=True (기본) 면 SearchQuery.collection 이 regulatory_docs."""
    captured: list[SearchQuery] = []

    def search(q):
        captured.append(q)
        return _result(q, [0.05])  # 결과 자체는 false_alarm

    validator = make_rag_validator(rag_search=search)  # 기본 regulatory_only=True
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_13_pressure", "target_id": "R_C",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_13_pressure",
                     "severity": "suspected_violation", "note": "DP gap"},
                ],
            },
        ])
        validator(p)
    assert len(captured) == 1
    assert captured[0].collection == "regulatory_docs"
    assert captured[0].calling_agent == "ValidationAgent"
    # context_tags 에 rule_id / target_id 가 들어가야 라우팅 가능
    assert "rule_13_pressure" in (captured[0].context_tags or [])


# ---------------------------------------------------------------------------
# Canonical 영문 쿼리 매핑 (2026-05-28 추가)
# ---------------------------------------------------------------------------

def test_canonical_query_replaces_query_text_for_known_rule():
    """use_canonical_queries=True (default) 면 알려진 rule_id 에 canonical
    영문 쿼리가 prepended 된다."""
    captured: list[SearchQuery] = []

    def search(q):
        captured.append(q)
        return _result(q, [0.1])

    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_13_pressure",
                "target_id": "R_FILL",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_13_pressure",
                     "severity": "suspected_violation",
                     "note": "차압 부족"},  # 한국어 note
                ],
            },
        ])
        validator(p)
    assert len(captured) == 1
    text = captured[0].text
    # canonical 영문 키워드들이 포함되어야
    assert "differential pressure" in text
    assert "Pa" in text
    # note 는 컨텍스트로 함께 들어가야
    assert "차압 부족" in text
    # 식별자 prefix 형식("rule_13_pressure | R_FILL |")은 사라지고 canonical 이 앞에
    assert not text.startswith("rule_13_pressure")


def test_canonical_query_disabled_falls_back_to_identifier_format():
    """use_canonical_queries=False 면 이전 동작 (식별자 + note)."""
    captured: list[SearchQuery] = []

    def search(q):
        captured.append(q)
        return _result(q, [0.1])

    cfg = RagValidatorConfig(use_canonical_queries=False)
    validator = make_rag_validator(rag_search=search, config=cfg)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_13_pressure",
                "target_id": "R_FILL",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_13_pressure",
                     "severity": "suspected_violation",
                     "note": "차압 부족"},
                ],
            },
        ])
        validator(p)
    text = captured[0].text
    assert text.startswith("rule_13_pressure |")
    assert "R_FILL" in text
    assert "차압 부족" in text
    # canonical 영문 키워드는 들어있지 않아야
    assert "differential pressure" not in text


def test_canonical_query_unknown_rule_id_falls_back():
    """canonical dict 에 없는 rule_id 는 use_canonical=True 여도 fallback."""
    captured: list[SearchQuery] = []

    def search(q):
        captured.append(q)
        return _result(q, [0.1])

    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_99_brand_new_rule",  # canonical 미정의
                "target_id": "T",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_99_brand_new_rule",
                     "severity": "suspected_violation", "note": "..."},
                ],
            },
        ])
        validator(p)
    text = captured[0].text
    # fallback 포맷 — 식별자 prefix
    assert text.startswith("rule_99_brand_new_rule |")


def test_canonical_queries_cover_all_15_rules():
    """모든 15개 룰이 canonical dict 에 등록되어 있어야 한다 (회귀 잠금)."""
    from rule_engine.validators.rag_validator import _CANONICAL_QUERIES

    expected = {
        "rule_01_layout_axis", "rule_02_room_shape", "rule_03_room_size",
        "rule_04_clean_grade", "rule_05_zones", "rule_06_airlocks",
        "rule_07_al_flow_type", "rule_08_corridors", "rule_09_doors",
        "rule_10_equipment", "rule_11_wash_prep", "rule_12_nc_rooms",
        "rule_13_pressure", "rule_14_acph", "rule_15_gowning",
    }
    actual = set(_CANONICAL_QUERIES.keys())
    missing = expected - actual
    assert not missing, f"canonical dict 에서 누락된 rule: {missing}"
    # 추가된 키도 알려준다 (정보용, 실패는 아님)
    extra = actual - expected
    if extra:
        # 새 룰이 추가됐을 가능성 — 이 테스트도 갱신해야 함.
        # 그러나 본 테스트에서는 통과 처리하고 다음 PR 에서 expected 갱신.
        pass


def test_canonical_query_format_minimum_length():
    """canonical query 가 너무 짧으면 TF-IDF 매칭이 약해진다. 키워드 최소 3개."""
    from rule_engine.validators.rag_validator import _CANONICAL_QUERIES

    for rid, q in _CANONICAL_QUERIES.items():
        words = q.split()
        assert len(words) >= 3, (
            f"{rid}: canonical query 가 너무 짧음 ({len(words)} words). "
            f"최소 3개 키워드 권장. query={q!r}"
        )


# ---------------------------------------------------------------------------
# Source metadata filter (2026-05-28 추가 — TF-IDF noise 감소 단계)
# ---------------------------------------------------------------------------

def test_source_filter_populates_metadata_filter_for_known_rule():
    """use_source_filter=True (default) 면 알려진 rule_id 에 source 리스트가
    SearchQuery.metadata_filter 로 채워진다."""
    captured: list[SearchQuery] = []

    def search(q):
        captured.append(q)
        return _result(q, [0.1])

    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_13_pressure",
                "target_id": "R_FILL",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_13_pressure",
                     "severity": "suspected_violation", "note": "DP gap"},
                ],
            },
        ])
        validator(p)
    assert len(captured) == 1
    mf = captured[0].metadata_filter
    assert mf is not None
    assert "source" in mf
    sources = mf["source"]
    assert isinstance(sources, list)
    assert "EU_GMP_Annex1_2022" in sources
    assert "WHO_TRS_Annex2_2022" in sources
    assert "ISO_14644_4" in sources


def test_source_filter_disabled_leaves_metadata_filter_none():
    """use_source_filter=False 면 metadata_filter 는 None."""
    captured: list[SearchQuery] = []

    def search(q):
        captured.append(q)
        return _result(q, [0.1])

    cfg = RagValidatorConfig(use_source_filter=False)
    validator = make_rag_validator(rag_search=search, config=cfg)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_13_pressure", "target_id": "R_FILL",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_13_pressure",
                     "severity": "suspected_violation", "note": "x"},
                ],
            },
        ])
        validator(p)
    assert captured[0].metadata_filter is None


def test_source_filter_unknown_rule_id_falls_back_to_no_filter():
    """매핑에 없는 rule_id 는 use_source_filter=True 여도 filter 없음."""
    captured: list[SearchQuery] = []

    def search(q):
        captured.append(q)
        return _result(q, [0.1])

    validator = make_rag_validator(rag_search=search)
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_99_unknown", "target_id": "X",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_99_unknown",
                     "severity": "suspected_violation", "note": "y"},
                ],
            },
        ])
        validator(p)
    assert captured[0].metadata_filter is None


def test_rule_to_sources_covers_all_15_rules():
    """15개 룰 모두 _RULE_TO_SOURCES 에 등록되어 있어야 (회귀 잠금)."""
    from rule_engine.validators.rag_validator import _RULE_TO_SOURCES
    expected = {
        "rule_01_layout_axis", "rule_02_room_shape", "rule_03_room_size",
        "rule_04_clean_grade", "rule_05_zones", "rule_06_airlocks",
        "rule_07_al_flow_type", "rule_08_corridors", "rule_09_doors",
        "rule_10_equipment", "rule_11_wash_prep", "rule_12_nc_rooms",
        "rule_13_pressure", "rule_14_acph", "rule_15_gowning",
    }
    actual = set(_RULE_TO_SOURCES.keys())
    missing = expected - actual
    assert not missing, f"_RULE_TO_SOURCES 누락: {missing}"
    # 모든 매핑은 최소 1개의 source 를 가져야
    for rid, srcs in _RULE_TO_SOURCES.items():
        assert isinstance(srcs, list) and len(srcs) >= 1, (
            f"{rid}: source 리스트가 비어있음"
        )


# ---------------------------------------------------------------------------
# Percentile-based threshold calibration
# ---------------------------------------------------------------------------

def test_calibrate_thresholds_returns_monotonic_pair():
    """calibrate_thresholds: high >= medium 항상 성립."""
    from rule_engine.validators.rag_validator import calibrate_thresholds

    # 분포가 단조 증가하도록 sample sim 을 미리 설계
    sims_pool = [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.22, 0.30, 0.45, 0.60]

    def search(q):
        return _result(q, sims_pool)

    high, medium = calibrate_thresholds(
        search,
        sample_queries=["q1", "q2"],
        high_percentile=95.0,
        medium_percentile=80.0,
    )
    assert high >= medium >= 0.0
    # 95th percentile 는 위쪽에 가까운 값이어야
    assert high >= 0.30


def test_calibrate_thresholds_empty_returns_zero():
    """검색 결과가 모두 비어있으면 (0.0, 0.0) 반환."""
    from rule_engine.validators.rag_validator import calibrate_thresholds

    def search(q):
        return _result(q, [])

    high, medium = calibrate_thresholds(
        search, sample_queries=["x", "y"],
    )
    assert (high, medium) == (0.0, 0.0)


def test_calibrate_thresholds_uses_canonical_when_no_sample_given():
    """sample_queries=None 이면 _CANONICAL_QUERIES 의 모든 value 가 사용."""
    from rule_engine.validators.rag_validator import (
        calibrate_thresholds, _CANONICAL_QUERIES,
    )
    seen_texts: list[str] = []

    def search(q):
        seen_texts.append(q.text)
        return _result(q, [0.1])

    calibrate_thresholds(search)  # sample_queries=None
    assert len(seen_texts) == len(_CANONICAL_QUERIES)
    # canonical query 본문이 들어왔는지 한 개만 확인
    assert any("differential pressure" in t for t in seen_texts)


def test_calibrate_thresholds_percentile_boundaries():
    """high_percentile=100 → max sim, medium_percentile=0 → min sim."""
    from rule_engine.validators.rag_validator import calibrate_thresholds

    sims = [0.10, 0.20, 0.30, 0.40, 0.50]

    def search(q):
        return _result(q, sims)

    high, medium = calibrate_thresholds(
        search, sample_queries=["q"], high_percentile=100.0,
        medium_percentile=0.0,
    )
    assert high == 0.50
    assert medium == 0.10


def test_make_calibrated_rag_validator_applies_thresholds():
    """make_calibrated_rag_validator 가 산정된 임계값을 config 에 적용한다."""
    from rule_engine.validators.rag_validator import make_calibrated_rag_validator

    # sample 결과로 sim 분포를 강제: 모두 0.15 → high=medium=0.15
    def search(q):
        return _result(q, [0.15])

    validator = make_calibrated_rag_validator(rag_search=search)
    # validator 에 verdict 한 번 돌려보고 threshold 가 적용됐는지 간접 확인.
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_output(Path(tmp), [
            {
                "rule_id": "rule_13_pressure", "target_id": "R_X",
                "decision": "...", "input_facts": {},
                "applied_logic": "...", "source_reference": "...",
                "flags": [
                    {"rule_id": "rule_13_pressure",
                     "severity": "suspected_violation", "note": "z"},
                ],
            },
        ])
        v = validator(p)
    # 모든 sample sim 이 0.15 라 high=medium=0.15. 실제 검색도 0.15 →
    # similarity == threshold 이면 confirmed_violation (>=) 분기.
    assert v.acknowledged_flags[0].verdict == "confirmed_violation"
