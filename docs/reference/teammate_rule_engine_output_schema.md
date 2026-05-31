# Rule Engine Output Schema — Documentation Agent Input Spec

> **Version**: v0.1 (2026-05-27)
> **For**: Documentation Agent 개발자
> **Source**: 회의 결정 #4 (2026-05-26) — "Documentation Agent 개발자가 그대로 input으로 활용할 수 있도록 Rule Engine output 명확화"
> **예시 파일**: `output_example.json` (실제 URS 1건 산출 결과, 243 KB)

---

## 1. Top-Level Structure

Rule Engine은 단일 JSON 객체를 산출. 최상위 8개 키.

```json
{
  "rooms":       [ ... ],
  "airlocks":    [ ... ],
  "adjacency":   [ ... ],
  "flow_paths":  { ... },
  "zones":       { ... },
  "constraints": { ... },
  "rationale":   [ ... ],
  "meta":        { ... }
}
```

| 키 | 타입 | 설명 |
|---|---|---|
| `rooms` | array | Room 객체 N개 (URS의 모든 방) |
| `airlocks` | array | AirLock 객체 (PAL/MAL/CAL in·out) |
| `adjacency` | array | Room↔Room 인접 그래프 엣지 |
| `flow_paths` | object | 4종 동선 (personnel/material/waste/product) |
| `zones` | object | process/auxiliary/NC 구역 그룹 |
| `constraints` | object | 정량 룰 (복도 폭·AL 크기·장비 간격 등) |
| `rationale` | array | 룰 적용 추적 로그 + flag |
| `meta` | object | 엔진·KB 버전, 입력 해시, 실행 통계 |

---

## 2. `rooms[]` — Room 명세

각 방의 모든 설계 정보. 회의 안건 #5 결정에 따라 `area_ratio_pct` 필드 포함.

```jsonc
{
  "room_id": "R_MEDIA_PREPARATION",          // string, 고유 식별자 (R_ prefix)
  "name_ko": "배지조제실",                    // string, 한글명
  "name_en": "Media preparation",            // string, 영문명
  "category": "process",                     // "process" | "auxiliary" | "NC"
  "clean_grade": "C",                        // "A" | "B" | "C" | "D" | "CNC" | "NC"
  "room_flow": "Both-way",                   // "One-way" | "Both-way"
  "gowning_type": "무진복",                   // "무균복" | "무진복" | "스크럽" | "일상복"
  "gowning_method": "over gowning",          // "over gowning" | "degowning and gowning" | "regular" | null
  "equipment": [                             // array, Equipment 객체 (아래 §2.1)
    { "instance_id": "Weigh booth", "name": "Weigh booth",
      "width_mm": 3500, "depth_mm": 3000, "height_mm": 3000,
      "weight_kg": 500, "max_operating_weight_kg": 600,
      "process_no": ["P1-1. 배지 원료 칭량"] }
  ],
  "process_no": ["P1-1. 배지 원료 칭량"],     // array of string, 세부 공정 No.
  "area_m2": 100.0,                          // float | null, 면적 (m²)
  "width_mm": 12247,                         // int | null, 가로 (mm)
  "depth_mm": 8165,                          // int | null, 세로 (mm)
  "ceiling_height_mm": 2700,                 // int | null, 천정고 (mm)
  "volume_m3": 270.0,                        // float | null, 체적 (m³)
  "differential_pressure_Pa": 30.0,          // float | null, 차압 (Pa)
  "air_changes_per_hour": 30.0,              // float | null, 환기횟수 (회/h)
  "recovery_time_min": 15.0,                 // float | null, 회복시간 (분)
  "background_color": "yellow",              // string | null, 도면 색상
  "transparency_pct": 50,                    // int | null, 투명도 (%)
  "well_type_ceiling": false,                // bool, 우물형 천정 여부
  "area_ratio_pct": 3.0                      // float | null, URS 입력 면적 비율 (%)
}
```

### 2.1 `equipment[]` — Room 내 장비

```jsonc
{
  "instance_id": "Mixing Tank-1",            // string, 고유 ID (URS의 인스턴스)
  "name": "Mixing Tank 100L",                // string, 장비 종류
  "width_mm": 2000,                          // int, W
  "depth_mm": 2000,                          // int, D
  "height_mm": 2000,                         // int, H
  "weight_kg": 1000,                         // float | null
  "max_operating_weight_kg": 1100,           // float | null, 최대 운영 중량
  "process_no": ["P1-2. 배지 제조"]          // array of string
}
```

---

## 3. `airlocks[]` — 전실 명세

AirLock 객체. Room 옆에 별도 배열로 분리되어 있음.

```jsonc
{
  "al_id": "AL_PAL_IN_CELL_CULTURE",         // string, AL_ prefix
  "kind": "PAL_in",                          // "CAL" | "CAL_in" | "CAL_out" | "MAL" | "MAL_in" | "MAL_out" | "PAL" | "PAL_in" | "PAL_out"
  "clean_grade": "C",                        // CleanGrade
  "area_m2": 12.0,                           // float | null
  "flow_type": "cascade",                    // "cascade" | "sink" | "bubble"
  "connects_higher_room": null,              // string | null, room_id (룰 13 산출)
  "connects_lower_room": null,               // string | null, room_id
  "purpose": "personnel",                    // "personnel" | "material" | "common"
  "differential_pressure_Pa": 25.0           // float | null
}
```

---

## 4. `adjacency[]` — 인접 그래프 엣지

Room↔Room (또는 Room↔AL, Room↔Elevator) 의 인접 관계. Documentation Agent가 좌표 배치 시 핵심 입력.

```jsonc
{
  "from_id": "R_MEDIA_PREPARATION",          // string, 출발 노드
  "to_id": "R_BUFFER_PREPARATION",           // string, 도착 노드
  "relationship": "door",                    // "door" | "shared_wall" | "passthrough_only"
  "door_count": 1,                           // int, 0이면 wall_only
  "door_size_mm": 1000,                      // int | null, 1000=일반, 1500=MAL
  "door_swing_target": "low_pressure_side",  // "high_pressure_side" | "low_pressure_side" | null
  "flow_direction": "bidirectional",         // "one_way_in" | "one_way_out" | "bidirectional"
  "is_elevator_constraint": false            // bool, 엘리베이터 가상 노드 엣지
}
```

**가상 노드 ID** (외부 위치):
- `ELEVATOR_MATERIAL_IN` — 자재 반입 엘리베이터
- `ELEVATOR_WASTE_OUT` — 폐기물 반출 엘리베이터

---

## 5. `flow_paths` — 4종 동선

ID 시퀀스 (좌표 X). Documentation Agent가 동선 화살표 그릴 때 사용.

```jsonc
{
  "personnel_entry":
      ["R_LOBBY", "R_GOWNING", "R_SUPPLY_CORRIDOR", "R_MEDIA_PREPARATION"],
  "personnel_exit":
      ["R_PURIFICATION_2", "R_RETURN_CORRIDOR", "R_GOWNING", "R_LOBBY"],
  "material_entry":
      ["ELEVATOR_MATERIAL_IN", "R_MATEIAL_IN", "R_SUPPLY_CORRIDOR", "R_MEDIA_PREPARATION"],
  "waste_exit":
      ["R_PURIFICATION_2", "R_RETURN_CORRIDOR", "R_WASTE_OUT", "ELEVATOR_WASTE_OUT"],
  "product_process_order":
      ["R_MEDIA_PREPARATION", "R_BUFFER_PREPARATION", "R_INOCULATION",
       "R_CELL_CULTURE", "R_HARVEST", "R_PURIFICATION_1", "R_PURIFICATION_2"]
}
```

---

## 6. `zones` — 구역 그룹

```jsonc
{
  "process_zone":   ["R_MEDIA_PREPARATION", "R_BUFFER_PREPARATION", ...],  // 30개
  "auxiliary_zone": ["R_MATERIAL_STORAGE", "R_DS_STORAGE", ...],            // 12개
  "nc_zone":        ["R_OFFICE", "R_LOBBY", ...]                            // 6개
}
```

---

## 7. `constraints` — 정량 룰 (배치 시 지켜야 할 값)

GMP Layout Logic.xlsx에서 그대로 가져온 값들. Documentation Agent가 좌표 배치 시 제약 조건으로 사용.

```jsonc
{
  "corridor_width_mm": { "min": 1500, "preferred_min": 2000, "max": 3000 },
  "airlock_size_mm":   { "preferred": [3000, 3000], "min": [1500, 1500] },
  "ceiling_height_mm": { "default_min": 2700, "default_max": 3000 },
  "equipment_clearance_mm": {
    "between_equipment": 1000,
    "to_wall_min": 600,
    "to_wall_max": 1200
  },
  "process_zone_area_ratio": { "min": 0.40, "max": 0.70 },
  "supply_return_no_direct_connection": true,
  "color_legend": {
    "A": "Green-diagonal-black",
    "B": "Green",
    "C": "yellow",
    "D": "Blue",
    "CNC": "Gray-dotted-black",
    "NC": "Gray"
  }
}
```

---

## 8. `rationale[]` — 룰 적용 추적 로그

각 룰이 어떤 입력에 어떤 결정을 내렸는지 명시. **감사 추적성**의 핵심 데이터.
Documentation Agent에서는 일반적으로 사용하지 않지만, **`flags`가 있는 항목은 Validation Agent와 사용자에게 표시할 수 있음**.

```jsonc
{
  "rule_id": "rule_04_clean_grade",          // string, 룰 식별자
  "target_id": "R_MEDIA_PREPARATION",        // string, 대상 (room_id / al_id / "LAYOUT")
  "decision": "grade=C, color=yellow",       // string, 결정 요약
  "input_facts": {                           // object, 결정 근거 입력값
    "urs_clean_grade": "C",
    "category": "process",
    "closed_system_main_process": false
  },
  "applied_logic": "URS Grade C 통과 + 색상 'yellow' + 50% 투명",  // string, 사람이 읽는 설명
  "source_reference": "Excel: Layout 설계 원리 §5 (청정등급·색상)", // string, 출처
  "flags": [                                 // array, 의심 위반 마킹
    {
      "rule_id": "rule_03_room_size",
      "severity": "suspected_violation",     // "suspected_violation" | "warning" | "info"
      "note": "'Cell Culture'이 KB에 없음 → Algorithm B fallback (96.1 m²)"
    }
  ]
}
```

**Flag severity 의미**:
- `suspected_violation` — GMP 룰 위반 의심. **Validation Agent가 RAG로 cross-check 필요.**
- `warning` — 권장 범위 밖. 검토 필요.
- `info` — 정보 제공. 결정은 정상.

---

## 9. `meta` — 엔진 메타데이터

```jsonc
{
  "engine_version": "0.1.0",                  // string
  "knowledge_base_version": "GMP_Layout_Logic_0510.xlsx",
  "input_hash": "cba2bc09d96f",               // string, 같은 URS면 항상 같음 (결정론적 재현성)
  "generated_at": "2026-05-27T04:07:12.107537+00:00",  // ISO 8601 UTC
  "stats": {
    "rooms": 48,
    "airlocks": 18,
    "adjacency_edges": 23,
    "rationale_entries": 399,
    "flag_counts": {
      "info": 4,
      "suspected_violation": 20,
      "warning": 4
    }
  }
}
```

---

## 10. Documentation Agent에서 활용 가이드

### 10.1 좌표 배치에 필요한 최소 입력

| 도면 요소 | 필요한 키 |
|---|---|
| Room 박스 그리기 | `rooms[].area_m2` + `width_mm` + `depth_mm` + `background_color` + `transparency_pct` |
| 청정등급 표시 | `rooms[].clean_grade` + `constraints.color_legend` |
| 차압 라벨 | `rooms[].differential_pressure_Pa` + `airlocks[].differential_pressure_Pa` |
| Room 간 도어 | `adjacency[]` 의 `relationship == "door"` 항목 |
| 도어 swing 방향 | `adjacency[].door_swing_target` |
| 전실 위치 | `airlocks[]` + 연결된 `adjacency[]` 엣지 |
| 동선 화살표 | `flow_paths.{personnel/material/waste}_entry|exit` |
| 공정 흐름 다이어그램 | `flow_paths.product_process_order` |
| 복도 폭 | `constraints.corridor_width_mm.preferred_min` |
| 장비 배치 간격 | `constraints.equipment_clearance_mm` |
| 장비 아이콘 | `rooms[].equipment[]` 의 W·D·H + `name` |
| 엘리베이터 위치 표시 | `adjacency[]` 의 `is_elevator_constraint == true` 항목 + 가상 노드 |

### 10.2 권장 처리 순서

1. **`zones` 먼저 그룹화** — 도면 영역 3분할 (process / auxiliary / NC)
2. **`flow_paths.product_process_order`** 따라 process Room을 일렬로 배치 (`adjacency` 엣지가 인접해야 하는 Room 표시)
3. **`airlocks`를 인접 Room 사이에 배치** — `adjacency`의 `is_elevator_constraint`가 아닌 AL 관련 엣지
4. **엘리베이터 위치 표시** — 가상 노드 (`ELEVATOR_MATERIAL_IN` / `ELEVATOR_WASTE_OUT`)를 자재 반입/폐기물 반출 방향 (URS `building.material_inlet` / `waste_outlet`)에 배치
5. **`rooms[].equipment[]` 배치** — Room 내부에 W·D 사각형으로
6. **동선 화살표 그리기** — 4종 동선 시퀀스대로
7. **`rationale[].flags` 가 있는 Room/AL에 ⚠️ 표시** — Validation Agent 검토 안건 시각화

### 10.3 코드 사용 예시 (Python)

```python
from rule_engine import run_rule_engine, RuleEngineInput

input_spec = RuleEngineInput(...)            # URS parsing으로 채움
output = run_rule_engine(input_spec)

# JSON 파일로 저장
with open("output.json", "w", encoding="utf-8") as f:
    f.write(output.to_json(indent=2))

# 또는 dict로 직접 사용
output_dict = output.to_dict()
for room in output_dict["rooms"]:
    print(room["name_en"], room["area_m2"], room["clean_grade"])
```

---

## 11. 변경 이력

| 버전 | 날짜 | 변경 사항 |
|---|---|---|
| v0.1 | 2026-05-27 | 최초 작성. 회의 결정 #3·#4·#5 반영 (JSON 직렬화, `area_ratio_pct` 필드). |

---

## 12. 관련 자료

- `rule_engine/output_example.json` — 실제 URS 1건 산출 결과 (243 KB)
- `rule_engine/models.py` — Python dataclass 정의 (소스)
- `rule_engine/engine.py` — `run_rule_engine` orchestrator
- `Layout_RuleEngine_Report_v0.2.docx` — 아키텍처 설계 보고서
- 노션 [회의 자료 — Layout Rule Engine v0.1 prototype 결과 보고](https://www.notion.so/36c5b274338b81c382f3ce150c6f792d)
