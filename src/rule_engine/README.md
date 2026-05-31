# `rule_engine` — GMP Layout Rule Engine (v0.1)

> Status: **v0.1 COMPLETE** (2026-05-26)
> 본문 100% 구현, 122/122 unit tests PASS, end-to-end 데모 동작 확인.
>
> **2026-05-26 회의 결정**: 안건 #2 (Excel만) · #3 (JSON + retry 3회) · #4 (7 블록 직렬화 + JSON schema 명세) · #5 (URS에 면적 비율% 컬럼) 확정. 자세한 내용은 §3·§10.

---

## 1. 이 패키지가 하는 일

URS 입력을 받아 Documentation Agent에 전달할 **7 블록**의 도면 사양을 산출한다. 보고서 `Layout_RuleEngine_Report_v0.2.docx` 의 I/O 스펙(§3)을 그대로 구현한다.

핵심 산출:

1. `rooms[]` — Room 객체 (URS 통과 + area/DP/color/ACPH/gowning derive)
2. `airlocks[]` — AL 객체 (kind/flow_type/DP)
3. `adjacency[]` — Room↔Room 인접 그래프 ← **Rule Engine의 가장 큰 가치**
4. `flow_paths` — 4종 동선 (엘리베이터 시작·종료점 포함)
5. `zones` — process/auxiliary/NC 그룹핑
6. `constraints` — 정량 룰 번들
7. `rationale[]` — 룰 적용 추적 + Flag (suspected_violation / warning / info)

---

## 2. v0.1 완성 현황

| 항목 | 상태 |
|---|---|
| 룰 모듈 본문 | **15 / 15 DONE** |
| derive 모듈 본문 | **3 / 3 DONE** |
| Stub 잔여 | **0** |
| Unit tests | **122 / 122 PASS** (18 파일) |
| End-to-end demo | **PASS** — 실제 URS (48 Room / 65 Equipment) 로 7 블록 정상 산출 |
| 총 Python 줄 수 | ~5,300 |

---

## 3. v1 스코프 (보고서 v0.2 §5.5 + 2026-05-26 회의 결정)

| 항목 | v1 값 | 근거 |
|---|---|---|
| Modality | mAb only | 보고서 §5.5 |
| 공정 범위 | DS 제조라인까지 | 보고서 §5.5 |
| 시설 범위 | 건물 내부 layout만 | 보고서 §5.5 |
| 라인 수 | 단일 라인 | 보고서 §5.5 |
| 층수 | 단일층 (다층 건물의 한 층) | 보고서 §5.5 |
| 엘리베이터 | 외부 위치 정보로만 반영 | 보고서 §5.4 |
| 호출 순서 | A안 (Rule Engine → Validation → Documentation, 위반 시 feedback) | 보고서 §2.2 + 회의 잠정 채택 |
| **URS 입력** | **Excel만 사용** | 회의 안건 #2 |
| **Validation 인터페이스** | **JSON 파일 + retry 3회 cutoff** | 회의 안건 #3 |
| **Documentation 인터페이스** | **7 블록 output에 `to_dict()` / `to_json()` 직렬화 + JSON schema 명세 + 예시 파일** | 회의 안건 #4 |
| **면적 입력 방식** | **URS에 "면적 비율 (%)" 컬럼 — 모든 Room의 % 합 = 100** | 회의 안건 #5 |

---

## 4. 폴더 구조

```
rule_engine/
├── README.md
├── __init__.py
├── engine.py                      # run_rule_engine + _bundle_constraints + _build_meta
├── models.py                      # Input 5 그룹 + Output 7 블록 데이터 클래스
├── _demo_run.py                   # ★ end-to-end 데모 (URS xlsx → 7 블록 산출)
├── _demo_result.txt               # 데모 실행 결과 텍스트
├── _prototype_purification1.py    # 정제실1 23 장비 면적 계산 prototype
├── rules/                         # 15 룰 본문
│   ├── rule_01_layout_axis.py     ~ rule_15_gowning.py
├── derive/                        # 3 derive 모듈
│   ├── rooms_selector.py          # URS dict → Room 객체
│   ├── adjacency.py               # ★ Room↔Room 그래프 빌드 (Rule Engine 핵심)
│   └── flow_paths.py              # 4종 동선
└── tests/
    ├── conftest.py                # 공유 fixture 7개
    ├── _minirunner.py             # pytest 없을 때 fallback runner
    └── unit/                      # 18 test 파일, 122 케이스
```

---

## 5. 사용법

### 5.1 데모 실행

```bash
cd <workspace>
python3 -m rule_engine._demo_run
```

실제 `URS_ConceptualDesign for layout_0516.xlsx` 를 파싱해서 `run_rule_engine`을 호출하고, 7 블록 산출 결과를 콘솔에 출력한다. 출력 예시는 `_demo_result.txt` 참조.

### 5.2 unit test 실행

```bash
# pytest 환경에서:
pytest rule_engine/tests/

# pytest 없는 환경 (sandbox 등):
python3 -m rule_engine.tests._minirunner
```

### 5.3 Programmatic

```python
from rule_engine import RuleEngineInput, ProductSpec, BuildingSpec, ..., run_rule_engine

input_spec = RuleEngineInput(
    product=ProductSpec(modality="mAb", culture_scale_L=8000, ...),
    building=BuildingSpec(..., elevator_for_material_in="12", elevator_for_waste_out="9"),
    flow_policy=...,
    organization=...,
    overrides=Overrides(),
    urs_rooms=[...],       # URS Parser 출력
    urs_equipment=[...],
)
output = run_rule_engine(input_spec)
# output.rooms, output.airlocks, output.adjacency, ..., output.meta
```

---

## 6. End-to-end 데모 결과 (실제 URS)

URS 파싱: **48 rooms / 65 equipment** → run_rule_engine 실행 후:

| 산출 블록 | 수치 |
|---|---|
| rooms | **48** (URS 그대로 통과 + area/DP/color/ACPH/gowning derive) |
| airlocks | **18** (CAL/PAL/MAL in·out 자동 변환) |
| adjacency edges | **23** (process flow 6 + AL 14 + elevator 2 + passthrough 1) |
| rationale entries | **399** (룰별 추적 로그) |
| flags | **28** (suspected_violation 20, warning 4, info 4) |

특히 다음이 자동 산출됨:
- **product_process_order**: `Media prep → Buffer prep → Inoculation → Cell Culture → Harvest → Purification 1 → Purification 2` (P1→P7)
- **material_entry**: `ELEVATOR_MATERIAL_IN → Mateial-in → Supply corridor → Media prep`
- **waste_exit**: `Purification 2 → Return corridor → Waste-out → ELEVATOR_WASTE_OUT`

전체 출력은 `_demo_result.txt` 참조.

---

## 7. 14 + 3 함수 매핑

| Excel 룰 / 시트 | 모듈 | 핵심 동작 |
|---|---|---|
| 룰 1 (전체 배열) | `rules/rule_01_layout_axis` | axis 벡터 (12/3/6/9시 → dx/dy) |
| 룰 2 (Room 구성) | `rules/rule_02_room_shape` | area → 직사각형 W·D (aspect 1.0~2.0) |
| 룰 3 (Room 크기) | `rules/rule_03_room_size` | KB 룩업 우선 + Algorithm B fallback |
| 룰 4 (청정등급) | `rules/rule_04_clean_grade` | URS passthrough + 색상 + flag |
| 룰 5 (Room 배열) | `rules/rule_05_zones` | process/auxiliary/NC 분류 |
| 룰 6 (전실 배열) | `rules/rule_06_airlocks` | URS AL Room → AirLock (kind 추론) |
| 룰 7 (전실 흐름) | `rules/rule_07_al_flow_type` | cascade/sink/bubble |
| 룰 8 (복도) | `rules/rule_08_corridors` | Supply ↔ Return 직결 차단 |
| 룰 9 (도어) | `rules/rule_09_doors` | 1000mm / MAL 1500mm, swing target |
| 룰 10 (장비) | `rules/rule_10_equipment` | process_no 기준 정렬 |
| 룰 11 (세척·준비) | `rules/rule_11_wash_prep` | passthrough_only 엣지 |
| 룰 12 (NC) | `rules/rule_12_nc_rooms` | organization 플래그 기반 필터 |
| 룰 13 (차압) | `rules/rule_13_pressure` | B(45) > C(30) > D(15) > CNC(5) > NC(0) Pa |
| 환기횟수 시트 | `rules/rule_14_acph` | URS passthrough + 권장 범위 비교 |
| 출입복장 시트 | `rules/rule_15_gowning` | Grade → method derive |
| (URS Room 통과) | `derive/rooms_selector` | URS dict → Room 객체 |
| (인접 그래프) | `derive/adjacency` | ★ process flow + AL + elevator |
| (4종 동선) | `derive/flow_paths` | personnel/material/waste/product |

---

## 8. URS 우선 정책 (passthrough + flag)

다음 3개 룰은 사용자 URS 값을 **수정하지 않는다**. 룰 위반 의심 시 `Rationale.flags`에 `Flag(severity="suspected_violation", ...)` 만 마킹하고, 최종 판정은 Validation Agent의 RAG cross-check에 위임 (보고서 §4.1):

- `rule_04_clean_grade` — Room.clean_grade 통과
- `rule_14_acph` — Room.air_changes_per_hour 통과
- `rule_15_gowning` — Room.gowning_type 통과 (method만 derive)

---

## 9. 엘리베이터 처리 (v0.2 결정, 보고서 §5.4)

v1은 단일 라인·단일층이지만, 다층 건물의 한 층을 차지하는 시나리오를 반영한다.

- **Input** `BuildingSpec.elevator_for_material_in`, `elevator_for_waste_out` (ClockDirection or None)
- **Adjacency** 그래프에 가상 노드 `ELEVATOR_MATERIAL_IN`, `ELEVATOR_WASTE_OUT` 도입. `is_elevator_constraint=True` 표시.
- **flow_paths.material_entry** 가 elevator(material)에서 시작, **waste_exit** 가 elevator(waste)에서 종료.

엘리베이터 자체는 룰 엔진의 배치 대상이 아닌 외부 위치 정보. Documentation Agent에 시각화 힌트로 전달.

---

## 10. 다음 작업 (회의 결정 반영, 2026-05-26)

| 우선순위 | 작업 | 의존 결정 | 잠정 기간 |
|---|---|---|---|
| **1** ⭐ | **URS 양식 갱신 + Parser** — 시트2에 "면적 비율 (%)" 컬럼 신설, `_demo_run.py` 미니 파서를 `urs_parser.py`로 정식화 | 안건 #2·#5 | 3~5일 |
| **2** ⭐ | **`rule_03_room_size` 갱신** — 비율 기반 lookup 단계 신설 (`area_m2 = total × pct/100`) + 합 100 검증 룰 | 안건 #5 | 1일 |
| **3** | **`models.Room`에 `area_ratio_pct` 필드 추가** + `to_dict()` / `to_json()` 직렬화 메서드 | 안건 #4·#5 | 1일 |
| **4** | **JSON schema 명세 문서 작성** + `output_example.json` 제공 | 안건 #4 | 2일 |
| **5** | **Validation Agent 연동 인터페이스 헬퍼** — JSON 직렬화 + retry 3회 cutoff + verdict 객체 | 안건 #3 | 1주 |
| 6 | L2 Integration test | — | 3일 |
| 7 | L3 Golden file E2E test (pytest-regressions) | — | 3일 |
| 8 | constraints KB 파서 (RAG → Rule Engine KB build, v0.2 안건 5.b) | 안건 5.b | 1~2주 |
| 9 | L4 Property-based test (Hypothesis) | — | 1주 |

---

## 11. 합의된 작업 스타일

- Python 3.10+ (`X | None` 문법)
- 모든 dataclass `frozen=True, slots=True`
- Google-style docstring + 한국어 본문
- 모듈 docstring은 "한 줄 요약 / 왜 필요한가 / 무엇을 안 하는가" 3단 구조
- 파일 300줄 미만 (rule_03만 171줄, 나머지 평균 80~100줄)
- OneDrive sync 이슈 회피: 대용량 파일은 bash heredoc + `sleep 1`

---

## 12. 관련 문서

- `Layout_RuleEngine_Report_v0.2.docx` — 본 패키지의 설계 보고서 (아키텍처 + I/O 스펙 + Decision Log)
- `GMP Layout Logic_0510.xlsx` — 룰베이스 KB
- `URS_ConceptualDesign for layout_0516.xlsx` — URS 템플릿 (demo input)
- `GMP_Layout_RuleEngine_IO_Spec.md` — I/O 스펙 v0.1 (v0.2 업데이트 예정)
- `_prototype_purification1.py` — 정제실1 면적 계산 prototype
- `_demo_result.txt` — end-to-end 데모 실행 결과 콘솔 출력
