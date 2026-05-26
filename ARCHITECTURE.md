# Architecture — Layout-Generator

상세 설계 문서. README의 요약을 깊이 있게 풀어 씁니다.

---

## 1. Rule Engine 내부 흐름

```
URS (JSON)
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  schemas.URSInput  (Pydantic 검증)                                │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  engine.run_rule_engine()                                         │
│                                                                   │
│    1) select_required_rooms(urs)  ── kb/rooms_mab.json           │
│    2) FOR r in rooms:                                             │
│         rule_04.assign_clean_grade(r, urs)                        │
│         rule_10.attach_equipment(r, urs)  ── kb/equipment.json   │
│         rule_03.calc_room_area(r, urs)                            │
│    3) rule_06.assign_airlocks(rooms, urs)                         │
│    4) rule_08.build_corridors(rooms, urs)                         │
│    5) rule_05.partition_zones(rooms)                              │
│    6) build_adjacency(rooms, airlocks, urs)                       │
│    7) rule_07.select_al_flow_type(adjacency, urs)                 │
│    8) rule_13.compute_pressure_cascade(rooms, adjacency)          │
│    9) rule_09.place_door(adjacency, pressures)                    │
│   10) rule_11.link_wash_prep(rooms, adjacency)                    │
│   11) rule_12.attach_nc_rooms(urs, rooms)                         │
│   12) attach_acph(rooms)  ── kb/acph_table.json                   │
│   13) attach_gowning(rooms)  ── kb/gowning_table.json             │
│                                                                   │
│   → 매 단계 rationale 로그 append                                  │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  validators.check_hard_constraints(output)                        │
│    C1 ~ C10 (위반 시 즉시 raise)                                   │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
schemas.RuleEngineOutput  (7-block JSON)
```

---

## 2. 7-블록 스키마 상세

### 2.1 rooms[]
```python
class Room(BaseModel):
    id: str                          # "R_MEDIA_PREP"
    name_ko: str
    name_en: str
    category: Literal["process", "auxiliary", "NC"]
    clean_grade: Literal["A","B","C","D","CNC","NC"]
    area_m2: float
    ceiling_height_mm: int = 3000
    has_well_ceiling: bool = False
    volume_m3: float
    background_color: str            # 룰 4
    transparency_pct: int = 50
    differential_pressure_Pa: float  # 룰 13
    air_changes_per_hour: int        # 환기 시트
    recovery_time_min: int | None
    gowning_type: str                # "무진복" 등
    gowning_method: str              # "over gowning" 등
    equipment: list[Equipment]
    one_way_flow: bool = False
    notes: str = ""
```

### 2.2 airlocks[]
```python
class Airlock(BaseModel):
    id: str
    type: Literal["CAL","CAL_in","CAL_out","MAL","MAL_in","MAL_out",
                  "PAL","PAL_in","PAL_out"]
    clean_grade: Literal["A","B","C","D","CNC","NC"]
    area_m2: float
    flow_type: Literal["cascade","sink","bubble"]
    connects_higher: str             # room/zone id
    connects_lower: str
    purpose: Literal["personnel_entry","personnel_exit",
                     "material_entry","material_exit","common"]
    differential_pressure_Pa: float
```

### 2.3 adjacency[]
```python
class Adjacency(BaseModel):
    from_id: str                     # room or airlock id
    to_id: str
    relationship: Literal["door","shared_wall","passthrough_only"]
    door_count: int = 1
    door_size_mm: int = 1000
    door_swing_to: str | None        # 차압 흐름 방향
    flow_direction: Literal["one_way_in","one_way_out","bidirectional"]
```

### 2.4 flow_paths
4종 동선 + 제품 공정 순서:
- personnel_entry / personnel_exit
- material_entry / waste_exit
- product_process_order (룰 5)

### 2.5 zones
- process_zone[], auxiliary_zone[], nc_zone[]

### 2.6 constraints
Drawing Agent가 배치 시 지킬 정량 룰. 색상 범례 포함.

### 2.7 rationale[]
```python
class Rationale(BaseModel):
    rule_id: str                     # "rule_4_clean_grade"
    target: str                      # "R_INOCULATION"
    decision: str
    reason: str
    source: str                      # "GMP Layout Logic_0510 §4"
```

---

## 3. Knowledge Base (KB) 파일

`src/rule_engine/kb/` 아래 JSON으로 분리. 룰과 데이터를 분리해서 추후 modality 확장(vaccine/ADC/cell therapy) 시 KB만 추가하면 됨.

| 파일 | 출처 | 용도 |
|------|------|------|
| `rooms_mab.json` | GMP Layout Logic Room 법령 시트 | Room 카탈로그 (40여 종) |
| `equipment.json` | 제조장비 범례 시트 | 장비 카탈로그 (80여 종) |
| `grade_colors.json` | 룰 4 | 등급별 색상/투명도 |
| `acph_table.json` | 환기횟수 시트 | grade → ACPH, recovery time |
| `gowning_table.json` | 갱의 방식 시트 | grade → 복장/방식 |
| `flow_policy_defaults.json` | 룰 1/8 | one-way flow 적용 구간 |

---

## 4. Drawing Agent (v1) 구상

> v1은 결정론적 baseline. RL 들어가기 전 sanity check용.

### 4.1 입력
Rule Engine output (7블록 JSON)

### 4.2 알고리즘 (v1, 결정론적)
1. **Bounding box 결정**: building.total_floor_area, 가로/세로 비율
2. **Zone partition**: 면적 비율에 따라 process / auxiliary / NC 영역 분할
3. **공급/리턴 복도 배치**: process zone 중앙(공급) + 외곽(리턴)
4. **Process Room 배치**: 공정 순서(`flow_paths.product_process_order`)대로 공급복도 한쪽에 정렬
5. **Airlock 배치**: adjacency에 따라 Room 경계에 부착
6. **장비 배치**: Room 내부에 공정 순서대로 (장비-벽 600mm, 장비-장비 1000mm)
7. **렌더링**: svgwrite로 SVG. 등급별 색상 + 투명도 + 동선 화살표 + 차압 라벨

### 4.3 v2 (RL)
배치를 sequential decision으로 보고 PPO로 학습 — [docs/rl_guide.md](docs/rl_guide.md) 참고.

---

## 5. Reward Function 설계

```python
def score(spec, layout) -> ScoreReport:
    score = 100.0
    violations = []

    # Hard constraints (C1~C10) — 하나라도 위반 시 즉시 큰 페널티
    for c in HARD:
        if not c.check(spec, layout):
            score -= 50      # 또는 즉시 fail
            violations.append(c.id)

    # Soft scoring
    score += 5 * flow_separation_quality(layout)        # 동선 분리도
    score += 5 * pressure_cascade_smoothness(layout)
    score += 3 * corridor_efficiency(layout)
    score += 3 * equipment_clearance_margin(layout)
    score += 2 * area_ratio_fit(layout, [0.4, 0.7])
    # ... 도면 미적 품질 (대칭/정렬도) 등

    return ScoreReport(total=score, violations=violations, breakdown=...)
```

---

## 6. RL 환경 (gymnasium)

```python
class LayoutEnv(gym.Env):
    """
    observation: 부분 배치된 그리드 + 남은 Room queue + 현재 단계
    action: (room_id, x, y, rotation)
    step: 1개 Room 배치 → reward(증분) 반환
    done: 모든 Room 배치 완료 OR hard constraint 위반
    """
```

자세한 학습 절차/하이퍼파라미터는 RL 단계 진입 시 `docs/rl_guide.md`에서 다룬다.

---

## 7. 테스트 전략

- **Unit**: 각 룰 함수 단위 (rule_01 ~ rule_13)
- **Integration**: URS → 7블록 JSON 엔드투엔드
- **Golden**: `examples/urs_mab_8000L.json` 입력 → `examples/golden_output.json` 대조
- **Validator**: 의도적으로 룰 위반 케이스 만들어서 validator가 잡아내는지

---

## 8. 확장성 노트

- **다른 modality**: `kb/rooms_vaccine.json` 등을 추가, `select_required_rooms()`에서 분기
- **다층 layout**: 룰 1 axis 결정에서 엘리베이터 좌표 입력받아 층간 그래프로 확장
- **DP/Aseptic filling**: Grade A/B isolator 룰 보강
