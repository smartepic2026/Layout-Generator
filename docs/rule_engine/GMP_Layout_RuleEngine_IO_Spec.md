# GMP Layout Rule Engine — I/O 스펙 (v0.1 draft)

**근거 자료:** `GMP Layout Logic_0510.xlsx` (Layout 설계 원리 12조 + Room 범례 40종 + 제조장비 범례 80여종 + 환기횟수표 + 출입복장표)

**파이프라인 위치:**
```
[사용자 요구사항] → [Rule Engine (이 문서)] → [Documentation Agent (도면 렌더링)]
                       ↑                              ↑
            Input 스키마                   Output 스키마 (Room 리스트 + 인접 그래프 + 제약)
```
좌표 배치(mm 단위 x,y)는 Documentation Agent의 책임. Rule Engine은 "무엇이, 어디에, 어떤 관계로 있어야 하는가"만 결정.

---

## 1. INPUT 스키마

### 1.1 product (제품/공정 특성)
| 필드 | 타입 | 예시 | 근거 룰 |
|---|---|---|---|
| `modality` | enum | `mAb` / `vaccine` / `ADC` / `cell_therapy` | 룰 1 (전체 배열 컨셉) |
| `culture_scale_L` | int | 8000 | Room 범례 기준값 |
| `n_product_types` | int | 1 (단일) / N (다품목) | 룰 3 (Room 크기 비율 40~70%) |
| `production_mode` | enum | `single_batch` / `overlap_batch` / `multi_product` | 룰 3 |
| `aseptic_filling_onsite` | bool | false (DS까지만) / true (DP 포함) | 룰 4 (Grade A/B 필요 여부) |
| `virus_filtration_required` | bool | true (mAb) | 룰 1 (편도 flow 적용 범위) |
| `closed_system_main_process` | bool | true이면 주공정 Grade D 허용 | 룰 4 |

### 1.2 building (건축 제약)
| 필드 | 타입 | 예시 | 근거 룰 |
|---|---|---|---|
| `total_floor_area_m2` | float | 3300 | Room 범례 기준 |
| `floor_level` | int | 1 (지상) / 2,3,… | 룰 1 (엘리베이터 고려) |
| `material_inlet_direction` | enum | `N`/`S`/`E`/`W` | 룰 1 |
| `waste_outlet_direction` | enum | `N`/`S`/`E`/`W` | 룰 1 |
| `elevator_position` | enum/null | 다층일 때 필요 | 룰 1 |
| `support_area_position_preference` | enum | `near_entrance` | 룰 1 |

### 1.3 flow_policy (동선/흐름 정책)
| 필드 | 타입 | 예시 | 근거 룰 |
|---|---|---|---|
| `one_way_flow_required_until` | enum | `virus_filtration` (mAb 기본) | 룰 1 |
| `supply_return_corridor_separate` | bool | true | 룰 8 |
| `airlock_default_type` | enum | `cascade` / `sink` / `bubble` | 룰 7 |
| `biological_safety_isolation` | bool | true이면 sink/bubble 강제 | 룰 7 |

### 1.4 organization (조직/인원 정책)
| 필드 | 타입 | 예시 | 근거 룰/시트 |
|---|---|---|---|
| `gender_separated_gowning` | bool | true (여/남 분리) | Room 범례 (갱의실 여/남) |
| `include_office_onsite` | bool | true/false | 룰 12 (NC 구역) |
| `include_toilet_onsite` | bool | true | 룰 12 |
| `include_monitoring_room_onsite` | bool | true | 룰 12 |
| `include_lobby_onsite` | bool | true | 룰 12 |

### 1.5 overrides (선택사항 — 특정 Room 강제 포함/제외/사이즈)
```json
{
  "force_include_rooms": ["DS storage"],
  "force_exclude_rooms": ["Cell bank storage"],
  "area_overrides": { "Purification 1": 350 }
}
```

---

## 2. OUTPUT 스키마

### 2.1 rooms (Room 객체 리스트)
```json
{
  "id": "R_MEDIA_PREP",
  "name_ko": "배지 조제실",
  "name_en": "Media preparation",
  "category": "process",           // process | auxiliary | NC
  "clean_grade": "C",              // A | B | C | D | CNC | NC
  "area_m2": 100,
  "ceiling_height_mm": 3000,
  "well_type_ceiling": false,
  "volume_m3": 300,
  "background_color": "yellow",    // 룰 4 색상 매핑
  "transparency_pct": 50,          // 룰 4
  "differential_pressure_Pa": 30,  // 룰 13
  "air_changes_per_hour": 25,      // 환기 횟수 시트
  "recovery_time_min": 18,
  "gowning_type": "무진복",         // 출입복장 시트
  "gowning_method": "over gowning",
  "equipment": [
    { "name": "Weigh booth", "W": 3500, "D": 3000, "H": 3000, "weight_kg": 500, "max_op_weight_kg": 600 },
    { "name": "Mixing Tank 2000L", "W": 3000, "D": 2500, "H": 4000, ... }
  ],
  "notes": "주공정 룸. closed system 미적용으로 Grade C 권장."
}
```

### 2.2 airlocks (전실 객체 리스트)
```json
{
  "id": "AL_001",
  "type": "PAL_in",                // CAL | CAL_in | CAL_out | MAL | MAL_in | MAL_out | PAL | PAL_in | PAL_out
  "clean_grade": "C",
  "area_m2": 12,
  "flow_type": "cascade",          // cascade | sink | bubble
  "connects_higher": "R_INOCULATION",
  "connects_lower": "R_SUPPLY_CORRIDOR",
  "purpose": "personnel_entry",
  "differential_pressure_Pa": 22
}
```

### 2.3 adjacency (인접/연결 그래프 — 핵심 산출물)
```json
{
  "from": "R_SUPPLY_CORRIDOR",
  "to": "AL_001",
  "relationship": "door",          // door | shared_wall | passthrough_only
  "door_count": 1,
  "door_size_mm": 1000,            // MAL의 경우 더 크게
  "door_swing_to": "R_SUPPLY_CORRIDOR",  // 차압 흐름 방향에 따라 닫히는 방향
  "flow_direction": "one_way_in"   // one_way_in | one_way_out | bidirectional
}
```

### 2.4 flow_paths (동선)
```json
{
  "personnel_entry": ["LOBBY", "GOWNING_F", "AUX_PAL", "SUPPLY_CORRIDOR", "PAL_IN", "ROOM_X"],
  "personnel_exit":  ["ROOM_X", "PAL_OUT", "RETURN_CORRIDOR", "GOWNING_F", "LOBBY"],
  "material_entry":  ["EXT", "AUX_MAL_IN", "MATERIAL_STORAGE", "MAL_IN", "ROOM_X"],
  "waste_exit":      ["ROOM_X", "MAL_OUT", "RETURN_CORRIDOR", "AUX_MAL_OUT", "EXT"],
  "product_process_order": [
    "MEDIA_PREP", "BUFFER_PREP", "INOCULATION", "SEED_TRAIN", "CELL_CULTURE",
    "HARVEST", "PURIFICATION_1", "PURIFICATION_2", "DS_STORAGE"
  ]
}
```

### 2.5 zones (구역 그룹)
```json
{
  "process_zone":   ["R_MEDIA_PREP", "R_BUFFER_PREP", "R_INOCULATION", …],
  "auxiliary_zone": ["R_MATERIAL_STORAGE", "R_GOWNING_F", …],
  "nc_zone":        ["R_OFFICE", "R_TOILET_F", "R_LOBBY", …]
}
```

### 2.6 constraints (Documentation Agent가 배치 시 지켜야 할 제약)
```json
{
  "corridor_width_mm": { "min": 1500, "preferred_min": 2000, "max": 3000 },
  "airlock_size_mm":   { "preferred": [3000, 3000], "min_passable": [1500, 1500] },
  "ceiling_height_mm": { "default": [2700, 3000], "tall_equipment_well_ceiling": true },
  "equipment_clearance_mm": {
    "between_equipment": 1000,
    "equipment_to_wall": [600, 1200]
  },
  "process_zone_area_ratio": { "min": 0.40, "max": 0.70 },
  "supply_return_no_direct_connection": true,
  "color_legend": {
    "A": "Green-diagonal-black", "B": "Green",
    "C": "yellow", "D": "Blue",
    "CNC": "Gray-dotted-black", "NC": "Gray"
  }
}
```

### 2.7 rationale (룰 추적 로그 — 디버깅/감사용)
```json
[
  { "rule": "rule_4_clean_grade", "target": "R_INOCULATION",
    "decision": "Grade B", "reason": "modality=mAb & aseptic_inoculation → 층류장치 둘러싼 Room은 Grade B" },
  { "rule": "rule_7_airlock", "target": "R_INOCULATION",
    "decision": "4 airlocks (PAL_in, MAL_in, PAL_out, MAL_out)", "reason": "Grade B는 one-way flow 강제" }
]
```

---

## 3. 룰 → 함수 매핑 (코드 모듈 설계)

| Excel 룰 | 함수 후보 | 산출 |
|---|---|---|
| 룰 1 (전체 배열 컨셉) | `derive_layout_axis(building, flow_policy)` | 공급→공정→리턴 axis 방향 |
| 룰 2 (Room 구성) | `expand_room_shape_constraints(rooms)` | 직사각형 합 제약 |
| 룰 3 (Room 크기) | `calc_room_area(room, equipment_list, product)` | area_m2 |
| 룰 4 (청정등급) | `assign_clean_grade(room, product, flow_policy)` | Grade A/B/C/D/CNC/NC + 색상 |
| 룰 5 (배열) | `partition_zones(rooms, product)` | process / auxiliary / NC |
| 룰 6 (전실 배열) | `assign_airlocks(rooms, flow_policy)` | airlock 객체들 |
| 룰 7 (전실 타입) | `select_al_flow_type(adj_rooms, flow_policy)` | cascade / sink / bubble |
| 룰 8 (복도) | `build_corridors(zones, flow_policy)` | supply_corridor, return_corridor |
| 룰 9 (도어) | `place_door(adjacency, pressures)` | door_size, swing_direction |
| 룰 10 (장비 배치) | `attach_equipment(room, equipment_legend)` | room.equipment[] + 간격 제약 |
| 룰 11 (세척/준비실) | `link_wash_prep(rooms)` | passthrough COP 공유 인접 |
| 룰 12 (NC) | `attach_nc_rooms(organization)` | NC 영역 Room |
| 룰 13 (차압) | `compute_pressure_cascade(rooms, grades)` | room.DP 값 |
| 환기횟수 시트 | `compute_acph(room.grade, room.volume)` | ACPH, recovery time |
| 출입복장 시트 | `assign_gowning(room.grade)` | gowning_type/method |

**최종 오케스트레이션:**
```python
def run_rule_engine(input_spec: dict) -> dict:
    rooms = select_required_rooms(input_spec)
    for r in rooms: assign_clean_grade(r, input_spec)
    for r in rooms: attach_equipment(r, input_spec); calc_room_area(r, …)
    airlocks = assign_airlocks(rooms, input_spec)
    adjacency = build_adjacency(rooms, airlocks, input_spec)
    apply_pressure_cascade(rooms, adjacency)
    apply_acph(rooms); apply_gowning(rooms)
    flow_paths = derive_flow_paths(rooms, adjacency, input_spec)
    zones = partition_zones(rooms)
    constraints = bundle_constraints()
    rationale = collect_rationale()
    return { "rooms":rooms, "airlocks":airlocks, "adjacency":adjacency,
             "flow_paths":flow_paths, "zones":zones,
             "constraints":constraints, "rationale":rationale }
```

---

## 4. 미해결 이슈 (다음에 결정 필요)

1. **modality 확장:** mAb 외 vaccine/ADC/cell_therapy의 Room 범례/장비 범례를 추가로 확보해야 함 (현재 엑셀은 mAb만). 우선 mAb 룰을 mAb-specific으로 격리하고, `select_required_rooms(modality)`를 modality 디스패처로 둘 예정.
2. **DS storage 위치:** 현재 보조 구역이지만 Cold chain 요구사항 따라 별도 zone 가능.
3. **다층 layout:** 엘리베이터 위치 룰이 정의돼 있으나 룰 엔진에서 층간 연결 그래프를 어떻게 표현할지 결정 필요.
4. **충전 라인 포함 시:** Grade A/B 영역 (Isolator, RABS 등) 추가 룰 정의 필요.
5. **검증/충돌 룰:** 면적 합 ≠ 전체 면적, 차압 cascade 충돌 등 자동 검출 규칙 정의 필요.
