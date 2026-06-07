# 0607 피드백 전수 감사 → 마스터 작업목록 (D-035)

> 2026-06-07 ultracode 워크플로우(5 에이전트) 증거기반 감사. 의존순 정렬.
> 출처: 면적/제약위반/피드백상태/하드코딩 4감사 + 종합.

## 확인된 현재 상태 (피드백 16항목)

- (low) A1 NC↔D Gowning gate — DONE (CNC gowning touches NC복도 + D복도)
- (low) A2 D↔C Gowning gate — DONE (C gowning touches D복도 + C복도)
- (low) A3 NC↔D MAL-in gate — DONE (CNC material-in touches NC복도 + D복도)
- (low) A4 D↔C MAL-in gate — DONE (C supply-MAL-in touches D복도 + C복도)
- (low) A5 All Grade-D rooms touch D복도 — DONE (FINAL_full.png blockage fixed)
- (med) A6 Room-only-via-corridor access — PARTIAL (3 violations; 2 intended, 1 unintended)
- (high) B7 Material flow sequence — NOT_DONE (spec skips NC복도, D복도, second MAL-in)
- (low) B8 Waste terminus = Waste-out — DONE
- (high) B9 Personnel flow — NOT_DONE (skips CNC gowning + NC→D→C corridor progression)
- (med) B10 Product flow — NOT_DONE in spec (stops at Purif2; DS-storage tail only added at render)
- (high) B11 Parallel arrows overlap on shared corridor — NOT_DONE (per-key constant offset)
- (med) C12 Area proportionality — PARTIAL (correlated r=0.83 but ratio spread 0.49–4.25)
- (high) D13 Harvest/Purif1 equipment overlaps flow line — NOT_DONE
- (med) E14 Left↔right mirror diversity (NC>D>C vs C<D<NC) — NOT_DONE
- (med) E15 Intra-zone room arrangement randomization — NOT_DONE
- (high) E16 URS total area & W×H aspect ratio not reflected — NOT_DONE

## 마스터 작업목록 (의존순)

### W1 [high|area] URS→spec 계약에 건물 footprint(총면적+종횡비/W×H) 싣기 — spec.building 채우기
- **why**: 검증됨: output/_spec_v13.json 의 building=None. cli.py L109-110 이 width=78500,height=42500 하드코딩 기본값으로 solve() 호출 → 캔버스 3336㎡(aspect 1.85)가 URS와 무관하게 고정. 단, 이 URS는 dimensions '78500*42500'/total 3340㎡ 가 우연히 일치해 area 감사에서는 정상으로 보였을 뿐(E16). 다른 URS면 즉시 깨짐. 면적·캔버스·일반화 다수 항목의 선행.
- **approach**: [rule_engine 수정] src/rule_engine/urs_parser._parse_building_meta 가 이미 dimensions/total_area_m2 를 파싱하므로(area 감사 확인), derive 단계에서 spec.building = {width_mm, height_mm, total_area_m2, target_aspect} 를 RuleEngineOutput 계약에 채워 직렬화. [drawing_agent 수정] cli.py cmd_draw: --width/--height 미지정 시 spec.building 에서 가져오도록, layout_solver.solve(): building_w_mm/h_mm 기본값을 spec.building 우선·없으면 _auto_canvas_for_rooms 폴백. 두 영역 공유 JSON 계약(building 필드)으로만 통신.
- **depends_on**: none

### W2 [high|hardcode] rule_engine 가 is_corridor/corridor_role(supply|return|aux|visitor) 및 subzone(저장/갱의/후방지원) 속성을 spec 에 채우기 — 속성기반 분류의 계약 선행
- **why**: 검증됨: 스키마에 is_corridor/corridor_role 필드는 있으나 실측 48방 중 is_corridor=True 0개, corridor_role 전부 empty. 반면 is_airlock=18개·gowning_type 은 채워짐(단 gowning_type='무진복'이 공정실에도 붙어 단독 판별자 불가). drawing_agent 의 ID-substring 하드코딩(복도/갱의/D존)을 속성기반으로 바꾸려면 엔진이 이 속성을 먼저 채워야 함. 이게 비면 W7·W8·W13·W14 의 de-hardcode 가 전부 폴백으로 죽음.
- **approach**: [rule_engine 수정] derive 단계에서 각 room 에 is_corridor=True + corridor_role 설정(supply/return/aux/visitor), 저장·갱의·후방지원 구분용 subzone(또는 기존 category/clean_grade 조합으로 충분한지 확인). gowning 은 gowning_type 존재 AND category=='gowning' 같은 복합조건이 되도록 category 정합성도 확인. [drawing_agent] 이후 W7/W8/W13/W14 가 이 속성을 1차로 읽고 ID 정규식을 폴백으로만 둠.
- **depends_on**: none

### W3 [high|constraints] post-solve 기하 검증기 신설 — 그려진 Layout 을 spec.constraints 에 대해 재검증
- **why**: 검증됨: rag_validator.py/validation_interface.py 는 rule_engine JSON만 검증, Layout 객체를 받지 않음 → missing door/equipment shrink·overflow/door-size override/corridor over-width/NC→D door 등 기하 위반이 전혀 안 잡힘. 검증기를 먼저 만들어야 이후 모든 수정(W4~W16)의 효과를 정량 측정 가능(CLAUDE.md: violation 수·점수 개선율 측정 원칙). 그래서 의존성 초반에 배치.
- **approach**: [drawing_agent 수정] src/drawing_agent/ 에 geometric validator 추가: (a) spec.adjacency door 커버리지(공유벽 있으면 door 존재?), (b) 장비 footprint==spec & 방내포함, (c) between_equipment/to_wall_min 실치수 clearance, (d) corridor_width_mm 밴드(min/preferred/max), (e) 모든 door 의 grade-cascade(인접 등급 1단계 초과 금지), (f) 면적 비례(drawn/spec ratio, 복도 제외). violations 리스트 출력 + cli draw 경로에 wiring. rule_engine 영역 import 금지(공유 JSON만).
- **depends_on**: W1

### W4 [high|area] 전역 단일 면적 스케일 도입 — 구역별 독립 100% 충전 폐기 (비례 붕괴의 근본 원인)
- **why**: 검증됨: layout_solver.py L662 w_nc=W*0.13, L663 w_d=W*0.16 등 컬럼 폭이 고정 비율이라 구역마다 spec→drawn 스케일 제각각(NC 1.74x, D 0.86x, 공정행 1.49~1.52x). 같은 spec 100㎡가 R_OFFICE 173.9㎡ vs R_MATERIAL_STORAGE 98.1㎡(1.77배). area 감사·feedback C12(ratio 0.49~4.25) 동일 근본원인 — 통합.
- **approach**: [drawing_agent 수정] _solve_gmp_gradient: 전역 s = (캔버스가용면적 / 총spec면적) 산출 후 모든 방 drawn≈spec*s 목표. 컬럼 폭 W*0.13/W*0.16 고정비율을 각 구역 spec 면적 합에 비례하도록 동적 산출(w_nc ∝ Σarea(nc), w_d ∝ Σarea(d), w_c ∝ Σarea(공정)). 남는 공간은 복도/여백으로 흡수(target_fill<1.0).
- **depends_on**: W1

### W5 [high|area] 공정행 종횡비 floor-clamp 제거/완화 — 작은 방 일괄 부풀림 차단 (INOCULATION 40㎡→123㎡ 3.08x)
- **why**: 검증됨: L540 _place_row_aspect→L366 _alloc_dim(max_aspect=1.9). floor=min(h/1.9, w/n)=8053mm 가 모든 작은 방을 같은 폭으로 클램프 → spec 40/60/80㎡ 가 전부 8053mm·123.2㎡ 동일하게 그려져 면적 정보 소실. feedback C12 의 process room inflation 과 동일 원인.
- **approach**: [drawing_agent 수정] _place_row_aspect/_alloc_dim: max_aspect 완화 또는 면적 비례 우선; 가장 견고하게는 공정행도 _place_treemap(_squarify) 로 통일해 면적∝값 수학 보장(슬리버는 squarify 가 자연 억제). 행 밴드 높이를 키워 floor 자체를 낮추는 것도 가능. W4 의 동적 컬럼폭과 함께 적용.
- **depends_on**: W4

### W6 [med|area] Grade D pair-row 배치를 squarify 로 교체 — 5:1 spec 이 8.33:1 로 왜곡되는 문제 제거
- **why**: 검증됨: L505-508 _place_d_zone_rows row_weight=max(left_area, sum(rights)) 로 행 높이 결정 → Equipment 100㎡:Cell_bank 20㎡ spec 5:1 이 도면 8.33:1. pair행 방들이 전폭행 대비 절반 스케일(CIP 0.49x, IPC 0.59x). area 감사 finding3.
- **approach**: [drawing_agent 수정] _place_d_zone_rows 의 수동 좌우/전폭 묶음(max() 가중치) 제거하고 D 구역 전체를 _squarify(L439) 로 배치 → 면적∝값 보장. 좌우열 D복도 접촉 힌트(touch dict)는 squarify 결과 rect 의 기하 위치로 재계산. W8(하드코딩 제거)과 함께 리팩터.
- **depends_on**: W4

### W7 [med|area] 복도 폭을 corridor_width_mm 기준으로 cap + return 미러 이중계상 제거 + 면적감사에서 복도 분리
- **why**: 검증됨: L705 C-zone ratios=[0.06,0.36,0.14,0.36,0.08] 고정비율이 spec 면적 무시. SUPPLY_CORRIDOR h=5950>max3000(2배 과폭), RETURN_CORRIDOR_S h=3400>3000. RETURN spec250 이 두 미러(137+182.7=319.7㎡)로 이중계상. R_CORRIDOR spec20→85㎡(4.25x). area+constraints 두 감사 공통.
- **approach**: [drawing_agent 수정] _solve_gmp_gradient: 복도 밴드 두께를 corridor_width_mm.preferred~max(<=3000) 로 cap, 여유면적은 인접 공정실에 재분배. RETURN 미러는 spec250 을 두 rect 로 분배(각~125) 하거나 한 방+미러 annotation. W3 검증기에서 복도는 면적 비례 비교 대상에서 제외(동선폭 기준).
- **depends_on**: W2,W4

### W8 [high|hardcode] _place_d_zone_rows 의 ID-substring take() 매칭을 속성기반으로 교체
- **why**: 검증됨: L471-487 take()가 i.upper() substring(MATERIAL_STORAGE/EQUIPMENT/GOWNING_FEMALE/MONITOR/DS_STORAGE/CIP/IPC/CELL_BANK). 개명 시 9개 전부 None→generic full-width 폴백으로 팀장 2D배치 소실. hardcode 감사 최우선.
- **approach**: [drawing_agent 수정] take() 를 속성조건으로: 저장=category=='auxiliary'&&grade D, 갱의=gowning_type 존재&&category=='gowning', 후방지원=NC&&aux. 복도접촉은 squarify 후 기하로 판정. W2 의 subzone 계약확장이 있으면 그것을 1차로 사용. ID substring 은 폴백만. W6 의 squarify 교체와 동시 진행.
- **depends_on**: W2,W6

### W9 [high|equipment] 장비를 실제 spec footprint(W_mm×D_mm)로 배치 — 시각축소 0.80→0.25 제거
- **why**: 검증됨: L1050 EQUIPMENT_VISUAL_SCALE=0.80, L1052 MIN 0.25, _place_equipment_grid use_actual_mm 기본 False. 실측 65개 장비 평균 placed/spec 면적 0.343(6~64%). 축소 때문에 between_equipment≥1000mm 검사가 인위적으로 통과(307쌍 0위반) — 실치수로도 방마다 여유 충분(Purif1 426㎡ vs 필요 255.5㎡)하므로 축소 불필요.
- **approach**: [drawing_agent 수정] _place_equipment_grid: gradient 경로에서 use_actual_mm=True 로 호출(_solve_gmp_gradient L761). 회전만 허용·면적 스케일 금지. baselines.json/strip-band 경로는 기존 False 유지(CLAUDE.md baseline 불변). W3 검증기로 between_equipment 를 실제 packing 제약으로 검사, 안 들어가면 방 확대 or infeasible 플래그(은밀 축소 금지).
- **depends_on**: W3

### W10 [high|equipment] 보조실 장비가 벽 밖으로 돌출하는 문제 수정 — 방내 containment 강제 (wall_gap 최대 -5755mm)
- **why**: 검증됨(constraints 감사): 10개 장비가 음수 벽clearance(R_DS_STORAGE Deep freezer -2005~-5755mm, CIP -1408, IPC -3194~-5694, Cell_bank -4212~-5462). 작은 보조실(11.8~29.4㎡)에서 6% 축소에도 grid 가 방을 넘침. to_wall_min=600 위반.
- **approach**: [drawing_agent 수정] _place_equipment_grid / _pack_row_major: 각 PlacedEquipment.rect 를 room.rect - to_wall_min(600) 내부로 clamp, 한 행에 안 들어가면 다음 행 wrap or 방당 개수 축소. 모든 PlacedEquipment.rect 가 room.rect 에 완전 포함됨을 assert. W9(실치수)와 함께 — 실치수면 더 큰 방이 필요할 수 있으니 W9 이후.
- **depends_on**: W9

### W11 [high|equipment] 장비가 제품동선을 가로막지 않도록 동선 레인 확보 (D13: Harvest/Purif1 교차)
- **why**: 검증됨(feedback D13): 제품동선이 방 중심-중심으로 장비박스 관통(HARVEST 2교차, PURIF1 4교차, INOC 3). _place_equipment_grid 가 방 중심 근처로 grid-pack 하며 동선 경로 무인지.
- **approach**: [drawing_agent 수정] (a) renderer 의 제품동선을 dead-center 대신 방 가장자리/장비 통로 레인으로 라우팅, 또는 (b) _place_equipment_grid 가 입/출구 도어 위치를 잇는 밴드를 비워두고 그 양옆에 packing. 장비 grid origin 을 entry/exit door 좌표와 정합. W9/W10(실치수·containment) 이후.
- **depends_on**: W9,W10

### W12 [high|flow] flow_paths 시퀀스 정확화 — 자재/인원/제품 동선이 NC→D→C 게이트 전체를 거치도록 (B7/B9/B10)
- **why**: 검증됨: flow_paths 키 personnel_entry/exit, material_entry, waste_exit, product_process_order 존재하나 (B7) material_entry 가 Material-in(CNC)→Supply 로 점프(D복도·2차 MAL-in C 누락), (B9) personnel 이 C-grade R_GOWNING 만 쓰고 CNC gowning M/F·NC/D복도 hop 생략, (B10) product_process_order 가 Purif2 에서 끝(Supply+DS storage 꼬리는 render-time 패치). 세 항목 모두 동일 파일.
- **approach**: [rule_engine 수정] src/rule_engine/derive/flow_paths.py: material=NC복도→Material-in(CNC)→D복도→Material-in(C)/Supply-MAL-in→Supply→공정 MAL-in→공정. personnel=Lobby→NC복도→Gowning M/F(CNC)→D복도→Gowning(C)→Supply→공정 (+역순 exit). product=…→Purif2→Supply→MAL-in(C)→D복도→DS storage 까지 spec 에 포함(renderer 패치 제거). gowning 은 clean_grade 로 CNC→C 명시 선택. Media/Buffer-prep prefix vs Inoc 시작은 팀장 확인 필요.
- **depends_on**: W2

### W13 [high|hardcode] 갱의 게이트 판별 de-hardcode + grade-D 게이트 허용 (GMP 위반 위험)
- **why**: 검증됨: 갱의 게이트가 GOWNING substring + grade∈{A,B,C} + process 동시조건. 실측 개명 시 process_gowning=None(방이 공정행으로), grade D 로 바꾸면 필터 탈락 None, R_CHANGE_W/M 개명 시 gownings=[]→NC복도 직결도어 미생성=갱의없이 NC→D 가능(GMP 위반). L342 R_GOWNING 리터럴 우선.
- **approach**: [drawing_agent 수정] gowning_type 존재 1차, grade A/B/C 하드코딩 제거(D→C entry 허용), 리터럴 R_GOWNING 대신 supply 인접/면적/PPO 기반 결정론 선택. NC↔D 게이트는 gowning_type+grade(CNC/D)+aux. 게이트 0개면 경고 annotation. W2 속성·W13 시퀀스와 정합.
- **depends_on**: W2

### W14 [high|constraints] spec.adjacency door 누락 보강 + door 폭 spec 보존 + NC→D 합성도어 금지
- **why**: 검증됨: (a) 26 door adjacency 중 8개 미그려짐 — 제품 process chain Media→…→Purif2 6개 도어(5쌍은 15300mm 벽 공유로 자명배치 가능)+ELEVATOR 2개. (b) 실측 door_size 분포 spec={1000:18,1500:8} 인데 _normalize_door_widths 가 전부 1500 으로 강제(57개). (c) NC→D 합성도어 2개(CIP_SUPPLY↔IPC, MONITORING↔DS_STORAGE) grade skip airlock 없음.
- **approach**: [drawing_agent 수정] solve 후 spec.adjacency(relationship=='door') 순회하며 공유벽 있으면 _ensure_door 로 PlacedDoor 생성, width_mm=adj.door_size_mm 보존(PlacedDoor.adj 저장). _normalize_door_widths 는 합성 게이트 도어에만 한정 or 전역 override 제거. 합성 백룸 도어는 양측 clean_grade 가 pressure_grade_order 에서 1단계 초과면 금지(or NC 지원실은 NC/CNC 복도로 라우팅). ELEVATOR_* 노드는 인접 material-in/waste-out 게이트로 매핑. W3 검증기로 커버리지 확인.
- **depends_on**: W3

### W15 [med|hardcode] 복도/AL/핀/양방향AL/AL-fake-room 의 ID-substring·dead-path 정리 (잔여 하드코딩)
- **why**: 검증됨: (a) 복도 판별이 _SUPPLY/_RETURN/_AUX 정규식만 의존, corridors[0/1] 인덱스가 spec 순서 의존. (b) mat_in/waste_out 핀이 MATERIAL_IN/WASTE substring('WASTE' 광범위→R_WASTEWATER_UTIL 오핀 위험). (c) _place_both_way_als 가 type∈{CAL,PAL,MAL} 정확매칭이나 실제는 *_in/*_out 뿐 → bw_als=[] 죽은코드. (d) AL fake-room 폴백 ^R_(P|M|C)AL_ + grade=='B' dead path. is_airlock=18 정상.
- **approach**: [drawing_agent 수정] 복도=corridor_role 1차·정규식 폴백, corridors 선택을 corridor_role 명시(인덱스 제거). 핀=flow_paths material in/out 끝점 or room.io_direction 1차, 'WASTE_OUT' 구체토큰 우선. _place_both_way_als=type.split('_')[0]∈{CAL,PAL,MAL} or in/out 쌍묶기, 0건시 annotation. AL=is_airlock/airlock_id 1차, 접두 확장·area==0 완화. 0개/dead-path 는 경고 annotation. W2 의존.
- **depends_on**: W2

### W16 [low|constraints] airlock 치수를 spec area_m2(예 9㎡→3000×3000)로 + preferred 목표 (품질 미달)
- **why**: 검증됨: 18개 AL 모두 depth h=2754mm 고정(< preferred 3000, spec area_m2 9㎡ 정사각 footprint 도 미달). width 2416~3800. min[1500,1500]은 초과(하드위반 아님, 품질 shortfall).
- **approach**: [drawing_agent 수정] AL 배치 시 spec.airlocks[i].area_m2 로 정사각 크기 산출(9㎡→3000×3000), 방 depth 허용 시 airlock_size_mm.preferred 목표. 고정 2754mm depth 제거. constraints 감사 finding.
- **depends_on**: W3

### W17 [med|diversity] --seed 플러밍 + 좌우 미러(NC>D>C ↔ C<D<NC) 다양성 (E14)
- **why**: 검증됨: cli.py draw 에 --seed 인자 없음, layout_solver.py 에 random/shuffle/mirror 기능 전무(corridor_mirror 는 정적 라벨뿐). 밴드순서 NC|NC복도|D|D복도|C 매 실행 고정. CLAUDE.md 결정론(seed 고정 시 재현) 준수 필요.
- **approach**: [drawing_agent 수정] cli.py draw 에 --seed 추가→solve() 로 전달. seed 로 5밴드 좌우 미러(및 유효 배치 선택). seed 고정 시 동일 출력(재현성). 면적/게이트 수정(W4~W8) 이후라야 미러가 의미. W2 속성으로 미러 후에도 복도/게이트 판별 유지.
- **depends_on**: W4,W7

### W18 [med|diversity] 구역내 방 배치 seeded 순열 (룰 준수 다양성) (E15) + R_TOILET_MALE 복도접속 (A6)
- **why**: 검증됨: _place_d_zone_rows 가 방 ID 하드코딩·고정순서 → 매 실행 동일. seed 플러밍 없음. 추가: R_TOILET_MALE 이 어떤 복도와도 접하지 않음(R_LOUNGE/R_TOILET_FEMALE 만 인접)=의도치 않은 A6 위반. CIP_SUPPLY/MONITORING 후방접근은 의도됨(팀장 확인).
- **approach**: [drawing_agent 수정] W17 의 --seed 위에서 각 구역 내 방을 adjacency/grade 제약 하 seeded permutation(constraint_compiler 가 인코딩한 제약으로 CP-SAT 가능해 enumerate 후 seed 선택). W8 의 속성기반 _place_d_zone_rows 일반화 위에 적용. 별건으로 모든 NC 방(toilet 포함)이 visitor 복도에 접하도록 _ensure_rooms_touch_corridor 보강.
- **depends_on**: W8,W17
