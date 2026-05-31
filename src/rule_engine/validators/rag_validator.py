"""rag_validator — RAG 의미검색 기반 실제 Validation Agent.

핸드오프 (2026-05-28): `make_stub_validator` 를 모델로 삼아 동일한 시그니처를
유지하면서 실제 RAG DB 의미검색으로 flag 의 진위를 판정한다.

설계 원칙:
    - Rule Engine 은 Validation Agent 의 내부 구현 (LLM/RAG) 을 모른다.
    - 본 모듈은 `rag_interface.models` 의 데이터 클래스만 의존하고, 검색 백엔드는
      외부에서 callable 로 주입받는다 (`rag_search` 파라미터). `rag_interface`
      의 `search.search` 구현이 완료되면 그 함수를 그대로 주입하면 된다.
    - 보고서 v0.2 §2.1 echo chamber 방지: Design Agent 와 같은 KB 를 사용하되
      build-time 동기화만 인정. runtime 직접 통합은 하지 않는다 (본 모듈은
      검색 결과만 받아 후처리할 뿐 KB 자체를 다루지 않음).

판정 로직 (flag 단위):
    1. rule_id + flag.note + target_id 로 SearchQuery 작성.
    2. rag_search 호출.
    3. 결과 top hit 의 confidence_level 에 따라 분기:
        - high   (similarity >= 0.5): confirmed_violation
        - medium (0.2 <= sim < 0.5): needs_user_review
        - low / 0 chunks            : false_alarm
    4. AcknowledgedFlag (rule_engine_flag_index, verdict, rag_citations, note)
       구성.

전체 status 결정 (회의 안건 #3 의 3-값 enum):
    - any confirmed_violation 존재 → "needs_revision"
    - confirmed 없고 needs_user_review 존재 → "needs_revision" (보수적)
    - 모두 false_alarm 이거나 flag 자체가 없음 → "pass"

Public API:
    RagValidatorConfig       — 임계값/동작 설정 데이터클래스.
    make_rag_validator       — Callable[[Path], ValidationVerdict] factory.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.rag_interface.models import Chunk, SearchQuery, SearchResult

from ..validation_interface import (
    AcknowledgedFlag,
    NewViolation,
    ValidationVerdict,
    VerdictStatus,
)


# ---------------------------------------------------------------------------
# 설정 — 임계값과 동작 토글을 한 곳에 모은다.
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RagValidatorConfig:
    """RAG validator 의 동작 파라미터.

    Attributes:
        top_k: 한 flag 당 RAG 에서 가져올 chunk 수. 기본 5.
        min_similarity_confirmed: 이 값 이상이면 confirmed_violation.
            기본 0.5 (rag_interface.models 의 _HIGH_THRESHOLD 일치).
        min_similarity_review: 이 값 이상이면 needs_user_review.
            기본 0.2 (rag_interface.models 의 _MEDIUM_THRESHOLD 일치).
        regulatory_only: True 면 regulatory_docs 컬렉션만 조회.
            보고서 v0.2 D2 결정: ValidationAgent 는 cross-collection 금지.
        calling_agent: SearchQuery.calling_agent 에 들어갈 식별자 (audit 용).
        detect_new_violations: True 면 rationale 외에 새 위반 탐지 시도.
            현 버전에선 hook 만 노출하고 실제 발견 로직은 단순. 기본 False.
        use_canonical_queries: True 면 rule_id 별 canonical 영문 쿼리 사용
            (cross-lingual / paraphrasing 한계 우회). flag.note 는 컨텍스트로
            덧붙임. False 면 이전 동작 (식별자 + flag.note 그대로).
            기본 True — TF-IDF 백엔드에서 한국어 flag note 의 매칭 실패를
            우회하기 위해 도입 (2026-05-28 의사결정 §2).
        use_source_filter: True 면 _RULE_TO_SOURCES 매핑에 따라
            SearchQuery.metadata_filter 에 룰별 관련 source 리스트를 채워
            검색 범위를 좁힘. False 면 컬렉션 전체 검색 (이전 동작).
            기본 True — TF-IDF noise 감소 목적 (2026-05-28 추가 단계).
            list value 는 OR/IN 시맨틱으로 rag_search 구현체가 해석한다.
    """
    top_k: int = 5
    min_similarity_confirmed: float = 0.5
    min_similarity_review: float = 0.2
    regulatory_only: bool = True
    calling_agent: str = "ValidationAgent"
    detect_new_violations: bool = False
    use_canonical_queries: bool = True
    use_source_filter: bool = True


# ---------------------------------------------------------------------------
# Canonical 영문 쿼리 매핑 — TF-IDF 환경에서 cross-lingual / paraphrasing
# 한계를 우회하기 위한 룰별 사전 정의 쿼리.
#
# 설계 의도:
#     - Rule Engine 의 flag.note 는 한국어/영문 혼재이고 표현이 자유로움.
#     - RAG DB 는 영문 regulatory 문서로만 구성됨 (FDA / EMA / WHO / ISO 등).
#     - TF-IDF 는 단어 중첩 기반이라 한국어 note → 영문 chunk 매칭이 어려움.
#     - 룰별로 "해당 룰이 다루는 도메인 개념"을 영문 표준 용어로 미리 1줄
#       정의해두면, flag.note 가 어떻게 표현되든 일관되게 retrieval 가능.
#
# 갱신 규칙:
#     - 룰을 새로 추가하면 본 dict 에도 영문 쿼리 한 줄 추가.
#     - 누락된 rule_id 는 fallback (rule_id 자체를 쿼리로 사용).
#     - 영문 키워드 5~10개 권장, 너무 길면 TF-IDF 토큰 가중치가 분산됨.
# ---------------------------------------------------------------------------

_CANONICAL_QUERIES: dict[str, str] = {
    "rule_01_layout_axis": (
        "cleanroom facility layout axis horizontal vertical "
        "process flow arrangement direction"
    ),
    "rule_02_room_shape": (
        "cleanroom room shape geometry aspect ratio rectangular "
        "footprint design"
    ),
    "rule_03_room_size": (
        "cleanroom area floor size ceiling height minimum "
        "requirement Grade volume"
    ),
    "rule_04_clean_grade": (
        "EU GMP cleanroom Grade A B C D classification "
        "adjacent area transition requirement"
    ),
    "rule_05_zones": (
        "cleanroom process auxiliary zone non-classified area "
        "classification grouping"
    ),
    "rule_06_airlocks": (
        "airlock cleanroom personnel material entry exit "
        "requirement segregation"
    ),
    "rule_07_al_flow_type": (
        "airlock cascade sink bubble pressure flow type "
        "differential cleanroom"
    ),
    "rule_08_corridors": (
        "cleanroom corridor width supply return separation "
        "personnel material flow"
    ),
    "rule_09_doors": (
        "cleanroom door interlock pressure swing direction "
        "size requirement"
    ),
    "rule_10_equipment": (
        "manufacturing equipment cleanroom clearance footprint "
        "installation requirement"
    ),
    "rule_11_wash_prep": (
        "wash preparation room equipment cleaning sanitization "
        "GMP requirement"
    ),
    "rule_12_nc_rooms": (
        "non-classified office monitoring lobby toilet area "
        "support room"
    ),
    "rule_13_pressure": (
        "cleanroom differential pressure Pa Grade B C D "
        "requirement positive negative"
    ),
    "rule_14_acph": (
        "air changes per hour ACPH cleanroom Grade ventilation "
        "supply airflow"
    ),
    "rule_15_gowning": (
        "gowning room transition Grade airlock garment "
        "aseptic dressing"
    ),
}


# ---------------------------------------------------------------------------
# Rule_id → 관련 regulatory source 매핑 — metadata_filter 에 사용.
#
# 설계 의도:
#     - 각 룰이 다루는 도메인이 regulatory 문서 중 어디에 집중적으로 다뤄지는지
#       사전 정의해두면, 검색 범위가 좁아져 같은 threshold 에서 정밀도 상승.
#     - source 이름은 RAG_DB_build/data/manifest.json 의 metadata.source 와 일치.
#     - cross-lingual / paraphrasing 한계 우회 이후 남은 noise (관련 없는 chunk
#       가 어쩌다 키워드 겹쳐 매칭) 를 줄이는 두 번째 단계.
#
# 갱신 규칙:
#     - RAG_DB 에 source 가 추가되면 본 dict 도 갱신 검토.
#     - 누락된 rule_id 는 filter 미적용 (전체 컬렉션 검색).
#     - regulatory_only=True 가정으로 regulatory_docs 의 source 만 등록.
# ---------------------------------------------------------------------------

_RULE_TO_SOURCES: dict[str, list[str]] = {
    "rule_01_layout_axis": ["EU_GMP_Annex1_2022"],
    "rule_02_room_shape": ["ISO_14644_4", "EU_GMP_Annex1_2022"],
    "rule_03_room_size": ["ISO_14644_4", "ISO_14644_1"],
    "rule_04_clean_grade": [
        "EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022", "ISO_14644_1",
    ],
    "rule_05_zones": ["EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022"],
    "rule_06_airlocks": ["EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022"],
    "rule_07_al_flow_type": ["EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022"],
    "rule_08_corridors": ["EU_GMP_Annex1_2022", "ISO_14644_4"],
    "rule_09_doors": ["EU_GMP_Annex1_2022", "ISO_14644_4"],
    "rule_10_equipment": [
        "EU_GMP_Annex1_2022", "FDA_Sterile_Drug_Products_2004",
    ],
    "rule_11_wash_prep": [
        "FDA_Sterile_Drug_Products_2004", "EU_GMP_Annex1_2022",
    ],
    "rule_12_nc_rooms": ["EU_GMP_Annex1_2022"],
    "rule_13_pressure": [
        "EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022", "ISO_14644_4",
    ],
    "rule_14_acph": [
        "ISO_14644_4", "ISO_14644_1", "EU_GMP_Annex1_2022",
    ],
    "rule_15_gowning": [
        "EU_GMP_Annex1_2022", "WHO_TRS_Annex2_2022",
    ],
}


def _build_metadata_filter(
    rule_id: str, *, use_source_filter: bool
) -> dict | None:
    """rule_id 에 대한 metadata_filter dict 를 만든다.

    Returns:
        use_source_filter=True 이고 rule_id 가 _RULE_TO_SOURCES 에 있으면
        `{"source": [list-of-sources]}` 형태의 dict. 그 외엔 None.
        list value 는 OR/IN 시맨틱으로 rag_search 구현체가 해석.
    """
    if not use_source_filter:
        return None
    sources = _RULE_TO_SOURCES.get(rule_id)
    if not sources:
        return None
    return {"source": list(sources)}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _build_query_text(
    rule_id: str,
    target_id: str,
    note: str,
    *,
    use_canonical: bool = True,
) -> str:
    """flag 한 점을 RAG 에 전달할 자연어 쿼리로 변환.

    Args:
        rule_id: Rule Engine 룰 식별자.
        target_id: 위반이 발생한 대상 (Room / AirLock / global 등).
        note: Rule Engine 이 작성한 위반 설명 (한국어/영문 혼재).
        use_canonical: True 면 _CANONICAL_QUERIES 에서 영문 쿼리를 가져와
            앞에 붙이고 note 를 컨텍스트로 추가. False 면 이전 동작
            (식별자 + note 만 사용). rule_id 가 _CANONICAL_QUERIES 에
            없으면 use_canonical 값과 무관하게 이전 동작으로 fallback.

    Returns:
        RAG 백엔드로 보낼 쿼리 문자열.
    """
    if use_canonical and rule_id in _CANONICAL_QUERIES:
        canonical = _CANONICAL_QUERIES[rule_id]
        # canonical 을 앞에 둬서 TF-IDF 가중치가 도메인 용어에 실리도록.
        # note 는 추가 컨텍스트로만 부가.
        return f"{canonical} | {note}"
    return f"{rule_id} | {target_id} | {note}"


def _decide_verdict_for_flag(
    result: SearchResult,
    cfg: RagValidatorConfig,
) -> tuple[str, list[str], str]:
    """SearchResult → (verdict, citations, note).

    verdict 는 AcknowledgedFlag.verdict 의 3-값 enum.
    citations 는 인용 문자열 (중복 제거, 등장 순서 유지).
    note 는 사람이 읽을 한 줄 설명.
    """
    if not result.chunks:
        return (
            "false_alarm",
            [],
            f"RAG 결과 없음 (status={result.status}) — 해당 위반의 근거를 KB 에서 찾지 못함.",
        )

    top = result.chunks[0]
    citations = result.to_citation_list()
    if top.similarity >= cfg.min_similarity_confirmed:
        verdict = "confirmed_violation"
        note = (
            f"top similarity={top.similarity:.3f} (≥{cfg.min_similarity_confirmed:.2f}) — "
            f"근거 {len(result.chunks)} chunk, 최우선 출처: {top.citation_string}."
        )
    elif top.similarity >= cfg.min_similarity_review:
        verdict = "needs_user_review"
        note = (
            f"top similarity={top.similarity:.3f} (medium) — KB 근거가 약함, "
            f"사용자 확인 권장. 최우선 출처: {top.citation_string}."
        )
    else:
        verdict = "false_alarm"
        note = (
            f"top similarity={top.similarity:.3f} (<{cfg.min_similarity_review:.2f}) — "
            f"근거 부족, false alarm 가능."
        )
    return verdict, citations, note


def _aggregate_status(
    acks: list[AcknowledgedFlag],
    new_violations: list[NewViolation],
) -> VerdictStatus:
    """flag 별 verdict 들과 NewViolation 으로 전체 status 결정.

    보수적 정책: confirmed 또는 user_review 가 하나라도 있으면 needs_revision.
    NewViolation 도 마찬가지 (Validation 이 새 위반을 찾았다는 건 revision 필요).
    """
    if new_violations:
        return "needs_revision"
    for a in acks:
        if a.verdict in ("confirmed_violation", "needs_user_review"):
            return "needs_revision"
    return "pass"


def _detect_new_violations_stub(
    output: dict,
    rag_search: Callable[[SearchQuery], SearchResult],
    cfg: RagValidatorConfig,
) -> list[NewViolation]:
    """Rule Engine 이 놓친 위반 탐지 — 우선순위 낮음.

    현 버전은 명시적 카탈로그 query 가 아직 정해지지 않았으므로 빈 리스트만 반환.
    추후 정해진 reference query set 으로 확장 (hook 지점은 보존).
    """
    if not cfg.detect_new_violations:
        return []
    # 향후 확장 지점. 지금은 No-op.
    return []


# ---------------------------------------------------------------------------
# Factory — 실제 validator 함수를 생성
# ---------------------------------------------------------------------------

def make_rag_validator(
    *,
    rag_search: Callable[[SearchQuery], SearchResult],
    config: RagValidatorConfig | None = None,
) -> Callable[[Path], ValidationVerdict]:
    """RAG 의미검색 기반 validator 를 만든다.

    Args:
        rag_search: SearchQuery 를 받아 SearchResult 를 돌려주는 검색 함수.
            `rag_interface.search.search` 가 구현되면 그 함수를 그대로 주입.
            테스트/데모에선 mock 함수를 주입.
        config: 동작 파라미터. None 이면 기본값.

    Returns:
        `Callable[[Path], ValidationVerdict]` — `run_with_validation_loop` 에
        그대로 넘길 수 있는 validator 함수.

    Example:
        >>> from rule_engine.validators import make_rag_validator, RagValidatorConfig
        >>> def my_search(q):  # 실제로는 rag_interface.search.search
        ...     ...
        >>> validator = make_rag_validator(rag_search=my_search)
        >>> # validator(Path("output.json")) -> ValidationVerdict
    """
    cfg = config or RagValidatorConfig()

    def _validate(json_path: Path) -> ValidationVerdict:
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        rationale = data.get("rationale", []) or []

        acks: list[AcknowledgedFlag] = []
        # rationale[idx].flags[fidx] 를 (rationale_idx, flag_idx) 로 추적.
        for r_idx, r in enumerate(rationale):
            flags = r.get("flags") or []
            rule_id = r.get("rule_id", "unknown")
            target_id = r.get("target_id", "unknown")
            for f_idx, f in enumerate(flags):
                note_text = f.get("note", "") or ""
                # info 레벨 flag 는 검증 대상에서 제외 (severity == "info" 는
                # 위반 아님, 단순 정보). 위반 후보만 RAG 에 질의.
                if f.get("severity") == "info":
                    acks.append(
                        AcknowledgedFlag(
                            rule_engine_flag_index=(r_idx, f_idx),
                            rule_id=rule_id,
                            verdict="false_alarm",
                            rag_citations=[],
                            note="severity=info — 위반 아님으로 자동 처리.",
                        )
                    )
                    continue

                query = SearchQuery(
                    text=_build_query_text(
                        rule_id, target_id, note_text,
                        use_canonical=cfg.use_canonical_queries,
                    ),
                    collection=(
                        "regulatory_docs" if cfg.regulatory_only else "both"
                    ),
                    top_k=cfg.top_k,
                    metadata_filter=_build_metadata_filter(
                        rule_id, use_source_filter=cfg.use_source_filter,
                    ),
                    calling_agent=cfg.calling_agent,
                    context_tags=[rule_id, target_id],
                )
                result = rag_search(query)
                verdict, citations, ack_note = _decide_verdict_for_flag(
                    result, cfg
                )
                acks.append(
                    AcknowledgedFlag(
                        rule_engine_flag_index=(r_idx, f_idx),
                        rule_id=rule_id,
                        verdict=verdict,
                        rag_citations=citations,
                        note=ack_note,
                    )
                )

        new_violations = _detect_new_violations_stub(data, rag_search, cfg)
        status = _aggregate_status(acks, new_violations)

        # 요약
        n_confirmed = sum(1 for a in acks if a.verdict == "confirmed_violation")
        n_review = sum(1 for a in acks if a.verdict == "needs_user_review")
        n_false = sum(1 for a in acks if a.verdict == "false_alarm")
        summary = (
            f"RAG validator: flags={len(acks)} "
            f"(confirmed={n_confirmed}, review={n_review}, false={n_false}), "
            f"new_violations={len(new_violations)}, status={status}"
        )

        return ValidationVerdict(
            status=status,
            rule_engine_input_hash=data.get("meta", {}).get("input_hash", "unknown"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            retry_count=0,
            acknowledged_flags=acks,
            new_violations=new_violations,
            summary=summary,
        )

    return _validate


# ---------------------------------------------------------------------------
# Percentile-based threshold calibration (2026-05-28 추가 단계)
#
# 동기:
#     - 고정 임계값 (0.5/0.2 또는 0.12/0.08) 은 백엔드 분포에 종속적.
#     - 컬렉션의 실제 retrieval 품질 분포를 측정해 percentile 로 임계값을 잡으면
#       TF-IDF/MiniLM 같은 백엔드 교체에도 자동 적응.
#     - 보고서 v0.2 §7 D1 "도메인 전문가 정성 확인 1라운드" 와 보완 관계 —
#       D1 은 절대값, 본 함수는 상대값.
#
# 사용법:
#     >>> high, medium = calibrate_thresholds(rag_search)
#     >>> cfg = dataclasses.replace(RagValidatorConfig(),
#     ...     min_similarity_confirmed=high, min_similarity_review=medium)
#     >>> validator = make_rag_validator(rag_search=rag_search, config=cfg)
# ---------------------------------------------------------------------------


def calibrate_thresholds(
    rag_search: Callable[[SearchQuery], SearchResult],
    *,
    sample_queries: list[str] | None = None,
    high_percentile: float = 95.0,
    medium_percentile: float = 80.0,
    top_k: int = 5,
    collection: str = "regulatory_docs",
    calling_agent: str = "ValidationAgent",
) -> tuple[float, float]:
    """canonical 쿼리들의 검색 결과 similarity 분포에서 percentile 기반 임계값 산정.

    Args:
        rag_search: 검색 callable.
        sample_queries: 분포 측정에 사용할 쿼리 리스트.
            None 이면 _CANONICAL_QUERIES 의 모든 값 사용 (15개).
        high_percentile: confirmed_violation 임계값의 percentile (기본 95).
        medium_percentile: needs_user_review 임계값의 percentile (기본 80).
        top_k: 쿼리당 가져올 chunk 수.
        collection: 검색할 컬렉션 이름.
        calling_agent: SearchQuery.calling_agent 식별자.

    Returns:
        (min_similarity_confirmed, min_similarity_review) 튜플.
        sample 이 비어있으면 (0.0, 0.0) 반환.
    """
    if sample_queries is None:
        sample_queries = list(_CANONICAL_QUERIES.values())

    similarities: list[float] = []
    for q_text in sample_queries:
        q = SearchQuery(
            text=q_text,
            collection=collection,
            top_k=top_k,
            calling_agent=calling_agent,
            context_tags=["__calibration__"],
        )
        result = rag_search(q)
        for chunk in result.chunks:
            similarities.append(float(chunk.similarity))

    if not similarities:
        return (0.0, 0.0)

    similarities.sort()
    n = len(similarities)

    def _percentile(p: float) -> float:
        if p <= 0:
            return similarities[0]
        if p >= 100:
            return similarities[-1]
        rank = (p / 100.0) * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        frac = rank - lo
        return similarities[lo] * (1 - frac) + similarities[hi] * frac

    high_value = _percentile(high_percentile)
    medium_value = _percentile(medium_percentile)
    if medium_value > high_value:
        medium_value = high_value
    return (high_value, medium_value)


def make_calibrated_rag_validator(
    *,
    rag_search: Callable[[SearchQuery], SearchResult],
    base_config: RagValidatorConfig | None = None,
    high_percentile: float = 95.0,
    medium_percentile: float = 80.0,
    sample_queries: list[str] | None = None,
) -> Callable[[Path], ValidationVerdict]:
    """percentile calibration 으로 임계값을 산정한 validator 를 만든다.

    한 줄 helper — calibrate_thresholds + dataclasses.replace + make_rag_validator.
    """
    import dataclasses as _dc

    base = base_config or RagValidatorConfig()
    high, medium = calibrate_thresholds(
        rag_search,
        sample_queries=sample_queries,
        high_percentile=high_percentile,
        medium_percentile=medium_percentile,
        top_k=base.top_k,
        collection=("regulatory_docs" if base.regulatory_only else "both"),
        calling_agent=base.calling_agent,
    )
    cfg = _dc.replace(
        base,
        min_similarity_confirmed=high,
        min_similarity_review=medium,
    )
    return make_rag_validator(rag_search=rag_search, config=cfg)
