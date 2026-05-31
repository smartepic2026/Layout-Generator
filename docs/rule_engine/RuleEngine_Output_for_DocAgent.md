# Rule Engine Output — 실제 URS 산출 결과

> **For**: Documentation Agent 개발 팀
> **목적**: Rule Engine 이 Documentation Agent 로 넘기는 실제 출력 데이터를 사람이 읽기 좋게 렌더링한 참조 문서.
> **생성 시각**: 2026-05-29 10:21 (KST 기준 참고)
> **입력 URS**: `URS_ConceptualDesign for layout_0516.xlsx`
> **input_hash**: `cba2bc09d96f` — 같은 URS면 항상 동일 (결정론적 재현성)
>
> ⚠️ 이 문서는 **사람이 읽기 위한 렌더링**입니다. 실제 계약은 JSON (`output_example.json`) 이며, 필드 스펙은 `output_schema.md` 를 따릅니다.

---

## 0. 출력 요약 (meta)

| 항목 | 값 |
|---|---|
| engine_version | `0.1.0` |
| knowledge_base_version | `GMP_Layout_Logic_0510.xlsx` |
| input_hash | `cba2bc09d96f` |
| rooms | 48 |
| airlocks | 18 |
| adjacency_edges | 27 |
| rationale_entries | 399 |
| flag_counts | info=3, suspected_violation=21, warning=0 |

최상위 7개 데이터 블록 + meta. 아래에서 블록별로 실제 값을 보여줍니다.

---

## 1. `rooms[]` — Room 명세 (48개)

도면 박스 1개 = Room 1개. 면적·치수·색상·차압·환기 등 배치에 필요한 모든 값.

| # | room_id | 한글명 | 영문명 | cat | grade | flow | gowning | area(m²) | W×D(mm) | 천장(mm) | DP(Pa) | ACPH | color | 투명% |
|--:|---|---|---|---|---|---|---|--:|---|--:|--:|--:|---|--:|
| 1 | `R_MEDIA_PREPARATION` | 배지조제실 | Media preparation | process | C | Both-way | 무진복 | 100.0 | 14142×7071 | 2700 | 30 | 30 | yellow | 50 |
| 2 | `R_BUFFER_PREPARATION` | 버퍼조제실 | Buffer preparation | process | C | Both-way | 무진복 | 200.0 | 20000×10000 | 2700 | 30 | 30 | yellow | 50 |
| 3 | `R_INOCULATION` | Seed 접종실 | Inoculation | process | C | One-way | 무진복 | 40.0 | 8944×4472 | 2700 | 30 | 30 | yellow | 50 |
| 4 | `R_CAL_IN_INOCULATION` | Seed 접종 전실 | CAL-in Inoculation | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 5 | `R_CAL_OUT_INOCULATION` | Seed 접종 후실 | CAL-out Inoculation | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 6 | `R_CELL_CULTURE` | 배양실 | Cell Culture | process | C | One-way | 무진복 | 150.0 | 17321×8660 | 2700 | 30 | 30 | yellow | 50 |
| 7 | `R_PAL_IN_CELL_CULTURE` | 배양실 전실(P) | PAL-in Cell Culture | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 8 | `R_MAL_IN_CELL_CULTURE` | 배양실 전실(M) | MAL-in Cell Culture | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 9 | `R_PAL_OUT_CELL_CULTURE` | 배양실 후실(P) | PAL-out Cell Culture | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 10 | `R_MAL_OUT_CELL_CULTURE` | 배양실 후실(M) | MAL-out Cell Culture | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 11 | `R_HARVEST` | 회수실 | Harvest | process | C | One-way | 무진복 | 60.0 | 8944×6708 | 2700 | 30 | 30 | yellow | 50 |
| 12 | `R_PAL_IN_HARVEST` | 회수실 전실(P) | PAL-in Harvest | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 13 | `R_MAL_IN_HARVEST` | 회수실 전실(M) | MAL-in Harvest | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 14 | `R_PAL_OUT_HARVEST` | 회수실 후실(P) | PAL-out Harvest | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 15 | `R_MAL_OUT_HARVEST` | 회수실 후실(M) | MAL-out Harvest | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 16 | `R_PURIFICATION_1` | 정제실1 | Purification 1 | process | C | One-way | 무진복 | 300.0 | 24495×12247 | 2700 | 30 | 30 | yellow | 50 |
| 17 | `R_PAL_IN_PURIFICATION_1` | 정제실1 전실(P) | PAL-in Purification 1 | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 18 | `R_MAL_IN_PURIFICATION_1` | 정제실1 전실(M) | MAL-in Purification 1 | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 19 | `R_PAL_OUT_PURIFICATION_1` | 정제실1 후실(P) | PAL-out Purification 1 | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 20 | `R_MAL_OUT_PURIFICATION_1` | 정제실1 후실(M) | MAL-out Purification 1 | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 21 | `R_PURIFICATION_2` | 정제실2 | Purification 2 | process | C | One-way | 무진복 | 100.0 | 14142×7071 | 2700 | 30 | 30 | yellow | 50 |
| 22 | `R_PAL_IN_PURIFICATION_2` | 정제실2 전실(P) | PAL-in Purification 2 | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 23 | `R_MAL_IN_PURIFICATION_2` | 정제실2 전실(M) | MAL-in Purification 2 | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 24 | `R_PAL_OUT_PURIFICATION_2` | 정제실2 후실(P) | PAL-out Purification 2 | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 25 | `R_MAL_OUT_PURIFICATION_2` | 정제실2 후실(M) | MAL-out Purification 2 | process | C | One-way | 무진복 | — | — | 2700 | 30 | 30 | yellow | 50 |
| 26 | `R_PREPARATION` | 공정 준비실 | Preparation | process | C | Both-way | 무진복 | 80.0 | 9798×8165 | 2700 | 30 | 30 | yellow | 50 |
| 27 | `R_GOWNING` | 착의실 | Gowning | process | C | Both-way | 무진복 | 30.0 | 6708×4472 | 2700 | 30 | 30 | yellow | 50 |
| 28 | `R_SUPPLY_CORRIDOR` | 공급복도 | Supply corridor | process | C | Both-way | 무진복 | 150.0 | 15000×10000 | 2700 | 30 | 30 | yellow | 50 |
| 29 | `R_RETURN_CORRIDOR` | 리턴복도 | Return corridor | process | D | Both-way | 스크럽 | 250.0 | 19365×12910 | 2700 | 15 | 20 | Blue | 50 |
| 30 | `R_WASHING` | 세척실 | Washing | process | D | Both-way | 스크럽 | 60.0 | 7746×7746 | 2700 | 15 | 20 | Blue | 50 |
| 31 | `R_MATERIAL_STORAGE` | 자재 보관실 | Material storage | auxiliary | D | Both-way | 스크럽 | 100.0 | 12247×8165 | 2700 | 15 | 20 | Blue | 50 |
| 32 | `R_EQUIPMENT_STORAGE` | 장비 보관실 | Equipment storage | auxiliary | D | Both-way | 스크럽 | 100.0 | 12247×8165 | 2700 | 15 | 20 | Blue | 50 |
| 33 | `R_DS_STORAGE` | DS 보관실 | DS storage | auxiliary | D | Both-way | 스크럽 | 50.0 | 10000×5000 | 2700 | 15 | 20 | Blue | 50 |
| 34 | `R_IPC` | IPC 실 | IPC | auxiliary | D | Both-way | 스크럽 | 30.0 | 6364×4714 | 2700 | 15 | 20 | Blue | 50 |
| 35 | `R_CELL_BANK_STORAGE` | 세포주 보관실 | Cell bank storage | auxiliary | D | Both-way | 스크럽 | 20.0 | 4472×4472 | 2700 | 15 | 20 | Blue | 50 |
| 36 | `R_CORRIDOR` | 복도 | Corridor | auxiliary | D | Both-way | 스크럽 | 20.0 | 5477×3651 | 2700 | 15 | 20 | Blue | 50 |
| 37 | `R_MATERIAL_IN` | 자재반입실 | Material-in | auxiliary | CNC | Both-way | 스크럽 | — | — | 2700 | 5 | 10 | Gray-dotted-black | 50 |
| 38 | `R_WASTE_OUT` | 폐기물반출실 | Waste-out | auxiliary | CNC | Both-way | 스크럽 | 30.0 | 6708×4472 | 2700 | 5 | 10 | Gray-dotted-black | 50 |
| 39 | `R_GOWNING_FEMALE` | 갱의실 (여) | Gowning Female | auxiliary | CNC | Both-way | 스크럽 | 50.0 | 8660×5774 | 2700 | 5 | 10 | Gray-dotted-black | 50 |
| 40 | `R_GOWNING_MALE` | 갱의실 (남) | Gowning Male | auxiliary | CNC | Both-way | 스크럽 | 80.0 | 10954×7303 | 2700 | 5 | 10 | Gray-dotted-black | 50 |
| 41 | `R_CIP_SUPPLY` | CIP 공급실 | CIP supply | auxiliary | NC | Both-way | 일상복 | 60.0 | 8660×6928 | 2700 | 0 | — | Gray | 50 |
| 42 | `R_MONITORING` | 모니터링실 | Monitoring | auxiliary | NC | Both-way | 일상복 | 50.0 | 8660×5774 | 2700 | 0 | — | Gray | 50 |
| 43 | `R_OFFICE` | 사무실 | Office | NC | NC | Both-way | 일상복 | 100.0 | 12247×8165 | 2700 | 0 | — | Gray | 50 |
| 44 | `R_TOILET_FEMALE` | 화장실 (여) | Toilet (Female) | NC | NC | Both-way | 일상복 | 20.0 | 5477×3651 | 2700 | 0 | — | Gray | 50 |
| 45 | `R_TOILET_MALE` | 화장실 (남) | Toilet (Male) | NC | NC | Both-way | 일상복 | 25.0 | 6124×4082 | 2700 | 0 | — | Gray | 50 |
| 46 | `R_LOBBY` | 로비 | Lobby | NC | NC | Both-way | 일상복 | 50.0 | 8660×5774 | 2700 | 0 | — | Gray | 50 |
| 47 | `R_CORRIDOR_VISITOR` | 관람복도 | Corridor visitor | NC | NC | Both-way | 일상복 | 30.0 | 6708×4472 | 2700 | 0 | — | Gray | 50 |
| 48 | `R_LOUNGE` | 휴게실 | Lounge | NC | NC | Both-way | 일상복 | 30.0 | 6708×4472 | 2700 | 0 | — | Gray | 50 |

### 1.1 Room 내 장비 — 13개 Room 에 총 65점

Documentation Agent 가 Room 내부에 장비 아이콘(W×D)을 배치할 때 사용.

| room_id | instance_id | name | W×D×H(mm) | weight(kg) | max_op(kg) | process_no |
|---|---|---|---|--:|--:|---|
| `R_MEDIA_PREPARATION` | Weigh booth | Weigh booth | 3500×3000×3000 | 500 | 600 | P1-1. 배지 원료 칭량 |
| `R_MEDIA_PREPARATION` | Mixing Tank-1 100L | Mixing Tank-1 100L | 2000×2000×2000 | 1000 | 1100 | P1-2. 배지 제조 |
| `R_MEDIA_PREPARATION` | Mixing Tank-2 500L | Mixing Tank-2 500L | 2500×2000×3000 | 1500 | 2000 | P1-2. 배지 제조 |
| `R_MEDIA_PREPARATION` | Mixing Tank-3 2000L | Mixing Tank-3 2000L | 3000×2500×4000 | 2000 | 4000 | P1-2. 배지 제조 |
| `R_MEDIA_PREPARATION` | Mixing Tank-4 10000L | Mixing Tank-4 10000L | 4000×3000×5000 | 3000 | 13000 | P1-2. 배지 제조 |
| `R_BUFFER_PREPARATION` | Weigh booth | Weigh booth | 3500×3000×3000 | 500 | 600 | P2-1. 버퍼 원료 칭량 |
| `R_BUFFER_PREPARATION` | Mixing Tank-5 500L | Mixing Tank-5 500L | 2500×2000×3000 | 1500 | 2000 | P2-2. 버퍼 제조 |
| `R_BUFFER_PREPARATION` | Mixing Tank-6 2000L | Mixing Tank-6 2000L | 3000×2500×4000 | 2000 | 4000 | P2-2. 버퍼 제조 |
| `R_BUFFER_PREPARATION` | Mixing Tank-7 4000L | Mixing Tank-7 4000L | 3500×2500×5000 | 2000 | 6000 | P2-2. 버퍼 제조 |
| `R_BUFFER_PREPARATION` | Mixing Tank-8 10000L | Mixing Tank-8 10000L | 4000×3000×5000 | 4000 | 14000 | P2-2. 버퍼 제조 |
| `R_INOCULATION` | Centrifuge | Centrifuge | 1000×600×500 | 60 | 60 | P3-1. Cell bank 접종 |
| `R_INOCULATION` | Isolator | Isolator | 4000×2000×3000 | 1000 | 1000 | P3-1. Cell bank 접종 |
| `R_INOCULATION` | Cleanbench | Cleanbench | 2000×800×2000 | 200 | 200 | P3-2. Flask 배양 1, P3-2. Flask 배양 2 |
| `R_INOCULATION` | Incubator | Incubator | 1200×800×600 | 150 | 150 | P3-2. Flask 배양 1, P3-2. Flask 배양 2 |
| `R_CELL_CULTURE` | Wave Reactor 20L | Wave Reactor 20L | 1200×600×800 | 200 | 220 | P4-1. 배양 N-4 |
| `R_CELL_CULTURE` | BioReactor 100L | BioReactor 100L | 2000×2000×2500 | 1000 | 1100 | P4-2. 배양 N-3 |
| `R_CELL_CULTURE` | BioReactor 500L | BioReactor 500L | 2500×2000×3500 | 1500 | 2000 | P4-3. 배양 N-2 |
| `R_CELL_CULTURE` | BioReactor 2000L | BioReactor 2000L | 3000×2500×4500 | 2000 | 4000 | P4-4. 배양 N-1 |
| `R_CELL_CULTURE` | BioReactor 10000L | BioReactor 10000L | 4000×3000×5500 | 3000 | 11000 | P4-5. 생산배양 |
| `R_CELL_CULTURE` | Storage tank-1 2000L | Storage tank-1 2000L | 3000×2500×4000 | 1500 | 3500 | P4-5. 생산배양 |
| `R_HARVEST` | Continuous centrifuge | Continuous centrifuge | 3000×3000×3000 | 2000 | 2500 | P5-1. 연속원심분리 |
| `R_HARVEST` | Depth filter system *2 | Depth filter system *2 | 2000×600×1800 | 300 | 500 | P5-2. Depthfiltration |
| `R_HARVEST` | Storage tank-2 10000L | Storage tank-2 10000L | 3000×3000×5000 | 1500 | 11500 | P5-2. Depthfiltration |
| `R_PURIFICATION_1` | Buffer tank-1 2000L | Buffer tank-1 2000L | 3000×2500×4000 | 1500 | 3500 | P6-1. 크로마토그래피 1, P6-3. 크로마토그래피 2, P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Buffer tank-2 2000L | Buffer tank-2 2000L | 3000×2500×4000 | 1500 | 3500 | P6-1. 크로마토그래피 1, P6-3. 크로마토그래피 2, P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Buffer tank-3 2000L | Buffer tank-3 2000L | 3000×2500×4000 | 1500 | 3500 | P6-1. 크로마토그래피 1, P6-3. 크로마토그래피 2, P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Buffer tank-4 4000L | Buffer tank-4 4000L | 3500×2500×5000 | 2000 | 6000 | P6-1. 크로마토그래피 1, P6-3. 크로마토그래피 2, P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Buffer tank-5 4000L | Buffer tank-5 4000L | 3500×2500×5000 | 2000 | 6000 | P6-1. 크로마토그래피 1, P6-3. 크로마토그래피 2, P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Buffer tank-6 4000L | Buffer tank-6 4000L | 3500×2500×5000 | 2000 | 6000 | P6-1. 크로마토그래피 1, P6-3. 크로마토그래피 2, P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Chromatography system 1 | Chromatography system 1 | 2000×1200×2000 | 500 | 500 | P6-1. 크로마토그래피 1 |
| `R_PURIFICATION_1` | Column 1500mm | Column 1500mm | 2500×2000×3000 | 2000 | 2200 | P6-1. 크로마토그래피 1 |
| `R_PURIFICATION_1` | Storage tank-3 4000L | Storage tank-3 4000L | 3500×2500×5000 | 2000 | 2000 | P6-1. 크로마토그래피 1 |
| `R_PURIFICATION_1` | Storage tank-4 3000L | Storage tank-4 3000L | 3000×2500×4500 | 2000 | 5000 | P6-1. 크로마토그래피 1, P6-3. 크로마토그래피 2, P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Acid tank 200L | Acid tank 200L | 2000×2000×2500 | 500 | 700 | P6-2. Virus inactivation |
| `R_PURIFICATION_1` | Base tank 200L | Base tank 200L | 2000×2000×2500 | 500 | 700 | P6-2. Virus inactivation |
| `R_PURIFICATION_1` | Depth filter system | Depth filter system | 2000×600×1800 | 300 | 500 | P6-2. Virus inactivation |
| `R_PURIFICATION_1` | Reactor 5000L | Reactor 5000L | 3000×2500×5000 | 1500 | 1500 | P6-2. Virus inactivation |
| `R_PURIFICATION_1` | Storage tank-5 5000L | Storage tank-5 5000L | 3000×2500×5000 | 1500 | 1500 | P6-2. Virus inactivation |
| `R_PURIFICATION_1` | Chromatography system 2 | Chromatography system 2 | 2000×1200×2000 | 500 | 500 | P6-3. 크로마토그래피 2 |
| `R_PURIFICATION_1` | Column 1000mm | Column 1000mm | 2000×2000×2500 | 1800 | 2000 | P6-3. 크로마토그래피 2 |
| `R_PURIFICATION_1` | Storage tank-6 8000L | Storage tank-6 8000L | 3500×3000×5500 | 2500 | 10000 | P6-3. 크로마토그래피 2 |
| `R_PURIFICATION_1` | Chromatography system 3 | Chromatography system 3 | 2000×1200×2000 | 500 | 500 | P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Column 800mm | Column 800mm | 2000×2000×2500 | 1500 | 1600 | P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Storage tank-7 2000L | Storage tank-7 2000L | 3000×2500×4000 | 1500 | 3500 | P6-4. 크로마토그래피 3 |
| `R_PURIFICATION_1` | Nano filtration system | Nano filtration system | 2000×800×1500 | 500 | 500 | P6-5. Virus filtration |
| `R_PURIFICATION_2` | Storage tank-8 2000L | Storage tank-8 2000L | 3000×2500×4000 | 1500 | 1500 | P6-5. Virus filtration |
| `R_PURIFICATION_2` | Buffer tank-7 5000L | Buffer tank-7 5000L | 3500×2500×5000 | 2000 | 7000 | P7-1. 농축 및 버퍼교환 |
| `R_PURIFICATION_2` | Holding tank 500L | Holding tank 500L | 2500×2000×3000 | 800 | 1300 | P7-1. 농축 및 버퍼교환 |
| `R_PURIFICATION_2` | Storage tank-9 500L | Storage tank-9 500L | 2500×2000×3000 | 800 | 800 | P7-1. 농축 및 버퍼교환 |
| `R_PURIFICATION_2` | TFF system | TFF system | 2500×2000×2500 | 1000 | 1000 | P7-1. 농축 및 버퍼교환 |
| `R_PURIFICATION_2` | Filtration system | Filtration system | 2000×800×1500 | 200 | 200 | P7-2. Filtration |
| `R_PURIFICATION_2` | Bulk fill system | Bulk fill system | 2000×800×1500 | 200 | 200 | P7-3. Bulk fill |
| `R_PREPARATION` | Autoclave | Autoclave | 3000×2500×3000 | 2000 | 2000 | — |
| `R_PREPARATION` | Cleanbooth | Cleanbooth | 3000×2500×3000 | 500 | 600 | — |
| `R_WASHING` | COP system | COP system | 3000×2500×3000 | 1500 | 1500 | — |
| `R_DS_STORAGE` | Deep freezer 1 | Deep freezer 1 | 1200×1000×2000 | 200 | 250 | — |
| `R_DS_STORAGE` | Deep freezer 2 | Deep freezer 2 | 1200×1000×2000 | 200 | 250 | — |
| `R_DS_STORAGE` | Deep freezer 3 | Deep freezer 3 | 1200×1000×2000 | 200 | 250 | — |
| `R_DS_STORAGE` | Deep freezer 4 | Deep freezer 4 | 1200×1000×2000 | 200 | 250 | — |
| `R_IPC` | Deep freezer | Deep freezer | 900×1000×2000 | 150 | 200 | — |
| `R_IPC` | Freezer | Freezer | 900×1000×2000 | 150 | 200 | — |
| `R_IPC` | Refrigerator | Refrigerator | 900×1000×2000 | 150 | 200 | — |
| `R_CELL_BANK_STORAGE` | Cell tank (nitrogen) 1 | Cell tank (nitrogen) 1 | 1000×1000×1500 | 200 | 200 | — |
| `R_CELL_BANK_STORAGE` | Cell tank (nitrogen) 2 | Cell tank (nitrogen) 2 | 1000×1000×1500 | 200 | 200 | — |
| `R_CIP_SUPPLY` | CIP station | CIP station | 5000×2000×4000 | 2000 | 4000 | — |

---

## 2. `airlocks[]` — 전실 (18개)

PAL(인원)·MAL(자재)·CAL(공용) 전실. Room 사이에 배치.

| # | al_id | kind | grade | area(m²) | flow_type | purpose | DP(Pa) | higher_room | lower_room |
|--:|---|---|---|--:|---|---|--:|---|---|
| 1 | `AL_CAL_IN_INOCULATION` | CAL_in | C | — | cascade | common | 25 | R_INOCULATION | — |
| 2 | `AL_CAL_OUT_INOCULATION` | CAL_out | C | — | cascade | common | 25 | R_INOCULATION | — |
| 3 | `AL_PAL_IN_CELL_CULTURE` | PAL_in | C | — | cascade | personnel | 25 | R_CELL_CULTURE | — |
| 4 | `AL_MAL_IN_CELL_CULTURE` | MAL_in | C | — | cascade | material | 25 | R_CELL_CULTURE | — |
| 5 | `AL_PAL_OUT_CELL_CULTURE` | PAL_out | C | — | cascade | personnel | 25 | R_CELL_CULTURE | — |
| 6 | `AL_MAL_OUT_CELL_CULTURE` | MAL_out | C | — | cascade | material | 25 | R_CELL_CULTURE | — |
| 7 | `AL_PAL_IN_HARVEST` | PAL_in | C | — | cascade | personnel | 25 | R_HARVEST | — |
| 8 | `AL_MAL_IN_HARVEST` | MAL_in | C | — | cascade | material | 25 | R_HARVEST | — |
| 9 | `AL_PAL_OUT_HARVEST` | PAL_out | C | — | cascade | personnel | 25 | R_HARVEST | — |
| 10 | `AL_MAL_OUT_HARVEST` | MAL_out | C | — | cascade | material | 25 | R_HARVEST | — |
| 11 | `AL_PAL_IN_PURIFICATION_1` | PAL_in | C | — | cascade | personnel | 25 | R_PURIFICATION_1 | — |
| 12 | `AL_MAL_IN_PURIFICATION_1` | MAL_in | C | — | cascade | material | 25 | R_PURIFICATION_1 | — |
| 13 | `AL_PAL_OUT_PURIFICATION_1` | PAL_out | C | — | cascade | personnel | 25 | R_PURIFICATION_1 | — |
| 14 | `AL_MAL_OUT_PURIFICATION_1` | MAL_out | C | — | cascade | material | 25 | R_PURIFICATION_1 | — |
| 15 | `AL_PAL_IN_PURIFICATION_2` | PAL_in | C | — | cascade | personnel | 25 | R_PURIFICATION_2 | — |
| 16 | `AL_MAL_IN_PURIFICATION_2` | MAL_in | C | — | cascade | material | 25 | R_PURIFICATION_2 | — |
| 17 | `AL_PAL_OUT_PURIFICATION_2` | PAL_out | C | — | cascade | personnel | 25 | R_PURIFICATION_2 | — |
| 18 | `AL_MAL_OUT_PURIFICATION_2` | MAL_out | C | — | cascade | material | 25 | R_PURIFICATION_2 | — |

---

## 3. `adjacency[]` — 인접 그래프 (27 엣지)

Room↔Room (또는 Room↔Elevator) 의 인접 관계. 좌표 배치의 핵심 입력.

| # | from_id | to_id | relationship | doors | door_size | swing | flow_direction | elevator |
|--:|---|---|---|--:|--:|---|---|:--:|
| 1 | `R_MEDIA_PREPARATION` | `R_BUFFER_PREPARATION` | door | 1 | 1000 | — | bidirectional |  |
| 2 | `R_BUFFER_PREPARATION` | `R_INOCULATION` | door | 1 | 1000 | — | bidirectional |  |
| 3 | `R_INOCULATION` | `R_CELL_CULTURE` | door | 1 | 1000 | — | bidirectional |  |
| 4 | `R_CELL_CULTURE` | `R_HARVEST` | door | 1 | 1000 | — | bidirectional |  |
| 5 | `R_HARVEST` | `R_PURIFICATION_1` | door | 1 | 1000 | — | bidirectional |  |
| 6 | `R_PURIFICATION_1` | `R_PURIFICATION_2` | door | 1 | 1000 | — | bidirectional |  |
| 7 | `AL_CAL_IN_INOCULATION` | `R_INOCULATION` | door | 1 | 1000 | high_pressure_side | one_way_in |  |
| 8 | `R_INOCULATION` | `AL_CAL_OUT_INOCULATION` | door | 1 | 1000 | low_pressure_side | one_way_out |  |
| 9 | `AL_PAL_IN_CELL_CULTURE` | `R_CELL_CULTURE` | door | 1 | 1000 | high_pressure_side | one_way_in |  |
| 10 | `AL_MAL_IN_CELL_CULTURE` | `R_CELL_CULTURE` | door | 1 | 1500 | high_pressure_side | one_way_in |  |
| 11 | `R_CELL_CULTURE` | `AL_PAL_OUT_CELL_CULTURE` | door | 1 | 1000 | low_pressure_side | one_way_out |  |
| 12 | `R_CELL_CULTURE` | `AL_MAL_OUT_CELL_CULTURE` | door | 1 | 1500 | low_pressure_side | one_way_out |  |
| 13 | `AL_PAL_IN_HARVEST` | `R_HARVEST` | door | 1 | 1000 | high_pressure_side | one_way_in |  |
| 14 | `AL_MAL_IN_HARVEST` | `R_HARVEST` | door | 1 | 1500 | high_pressure_side | one_way_in |  |
| 15 | `R_HARVEST` | `AL_PAL_OUT_HARVEST` | door | 1 | 1000 | low_pressure_side | one_way_out |  |
| 16 | `R_HARVEST` | `AL_MAL_OUT_HARVEST` | door | 1 | 1500 | low_pressure_side | one_way_out |  |
| 17 | `AL_PAL_IN_PURIFICATION_1` | `R_PURIFICATION_1` | door | 1 | 1000 | high_pressure_side | one_way_in |  |
| 18 | `AL_MAL_IN_PURIFICATION_1` | `R_PURIFICATION_1` | door | 1 | 1500 | high_pressure_side | one_way_in |  |
| 19 | `R_PURIFICATION_1` | `AL_PAL_OUT_PURIFICATION_1` | door | 1 | 1000 | low_pressure_side | one_way_out |  |
| 20 | `R_PURIFICATION_1` | `AL_MAL_OUT_PURIFICATION_1` | door | 1 | 1500 | low_pressure_side | one_way_out |  |
| 21 | `AL_PAL_IN_PURIFICATION_2` | `R_PURIFICATION_2` | door | 1 | 1000 | high_pressure_side | one_way_in |  |
| 22 | `AL_MAL_IN_PURIFICATION_2` | `R_PURIFICATION_2` | door | 1 | 1500 | high_pressure_side | one_way_in |  |
| 23 | `R_PURIFICATION_2` | `AL_PAL_OUT_PURIFICATION_2` | door | 1 | 1000 | low_pressure_side | one_way_out |  |
| 24 | `R_PURIFICATION_2` | `AL_MAL_OUT_PURIFICATION_2` | door | 1 | 1500 | low_pressure_side | one_way_out |  |
| 25 | `ELEVATOR_MATERIAL_IN` | `R_MATERIAL_IN` | door | 1 | 1000 | — | one_way_in | ✓ |
| 26 | `R_WASTE_OUT` | `ELEVATOR_WASTE_OUT` | door | 1 | 1000 | — | one_way_out | ✓ |
| 27 | `R_WASHING` | `R_PREPARATION` | passthrough_only | 0 | — | — | bidirectional |  |

---

## 4. `flow_paths` — 4종 동선 + 공정 순서

동선 화살표를 그릴 ID 시퀀스. 좌표는 없으며 순서만 제공.

**인원 입실** (`personnel_entry`, 4 nodes):

`R_LOBBY` → `R_GOWNING` → `R_SUPPLY_CORRIDOR` → `R_MEDIA_PREPARATION`

**인원 퇴실** (`personnel_exit`, 4 nodes):

`R_PURIFICATION_2` → `R_RETURN_CORRIDOR` → `R_GOWNING` → `R_LOBBY`

**자재 반입** (`material_entry`, 4 nodes):

`ELEVATOR_MATERIAL_IN` → `R_MATERIAL_IN` → `R_SUPPLY_CORRIDOR` → `R_MEDIA_PREPARATION`

**폐기물 반출** (`waste_exit`, 4 nodes):

`R_PURIFICATION_2` → `R_RETURN_CORRIDOR` → `R_WASTE_OUT` → `ELEVATOR_WASTE_OUT`

**제품 공정 순서** (`product_process_order`, 7 nodes):

`R_MEDIA_PREPARATION` → `R_BUFFER_PREPARATION` → `R_INOCULATION` → `R_CELL_CULTURE` → `R_HARVEST` → `R_PURIFICATION_1` → `R_PURIFICATION_2`

---

## 5. `zones` — 구역 그룹

도면 영역을 3분할할 때 사용.

**주공정 구역** (`process_zone`, 30개): `R_MEDIA_PREPARATION`, `R_BUFFER_PREPARATION`, `R_INOCULATION`, `R_CAL_IN_INOCULATION`, `R_CAL_OUT_INOCULATION`, `R_CELL_CULTURE`, `R_PAL_IN_CELL_CULTURE`, `R_MAL_IN_CELL_CULTURE`, `R_PAL_OUT_CELL_CULTURE`, `R_MAL_OUT_CELL_CULTURE`, `R_HARVEST`, `R_PAL_IN_HARVEST`, `R_MAL_IN_HARVEST`, `R_PAL_OUT_HARVEST`, `R_MAL_OUT_HARVEST`, `R_PURIFICATION_1`, `R_PAL_IN_PURIFICATION_1`, `R_MAL_IN_PURIFICATION_1`, `R_PAL_OUT_PURIFICATION_1`, `R_MAL_OUT_PURIFICATION_1`, `R_PURIFICATION_2`, `R_PAL_IN_PURIFICATION_2`, `R_MAL_IN_PURIFICATION_2`, `R_PAL_OUT_PURIFICATION_2`, `R_MAL_OUT_PURIFICATION_2`, `R_PREPARATION`, `R_GOWNING`, `R_SUPPLY_CORRIDOR`, `R_RETURN_CORRIDOR`, `R_WASHING`

**보조 구역** (`auxiliary_zone`, 12개): `R_MATERIAL_STORAGE`, `R_EQUIPMENT_STORAGE`, `R_DS_STORAGE`, `R_IPC`, `R_CELL_BANK_STORAGE`, `R_CORRIDOR`, `R_MATERIAL_IN`, `R_WASTE_OUT`, `R_GOWNING_FEMALE`, `R_GOWNING_MALE`, `R_CIP_SUPPLY`, `R_MONITORING`

**NC 구역** (`nc_zone`, 6개): `R_OFFICE`, `R_TOILET_FEMALE`, `R_TOILET_MALE`, `R_LOBBY`, `R_CORRIDOR_VISITOR`, `R_LOUNGE`

---

## 6. `constraints` — 정량 룰 (배치 제약값)

```json
{
  "corridor_width_mm": {
    "min": 1500,
    "preferred_min": 2000,
    "max": 3000
  },
  "airlock_size_mm": {
    "preferred": [
      3000,
      3000
    ],
    "min": [
      1500,
      1500
    ]
  },
  "ceiling_height_mm": {
    "default_min": 2700,
    "default_max": 3000
  },
  "equipment_clearance_mm": {
    "between_equipment": 1000,
    "to_wall_min": 600,
    "to_wall_max": 1200
  },
  "process_zone_area_ratio": {
    "min": 0.4,
    "max": 0.7
  },
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

## 7. `rationale[]` — 룰 적용 추적 (399건, 그 중 flag 보유 24건)

전체 추적 로그는 분량이 커서 (감사용) JSON 을 참조. 여기서는 **flag 가 달린 항목만** 발췌합니다.
flag 가 있는 Room/AL 에 Documentation Agent 가 ⚠️ 표시를 하고, Validation Agent 가 RAG cross-check 대상으로 삼습니다.

| rule_id | target_id | severity | note |
|---|---|---|---|
| `rule_10_equipment` | `R_PREPARATION` | info | 공정 Room 'Preparation'에 process_no 없는 장비: ['Autoclave', 'Cleanbooth'] |
| `rule_10_equipment` | `R_WASHING` | info | 공정 Room 'Washing'에 process_no 없는 장비: ['COP system'] |
| `rule_03_room_size` | `R_CAL_IN_INOCULATION` | suspected_violation | 'CAL-in Inoculation' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_CAL_OUT_INOCULATION` | suspected_violation | 'CAL-out Inoculation' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_PAL_IN_CELL_CULTURE` | suspected_violation | 'PAL-in Cell Culture' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MAL_IN_CELL_CULTURE` | suspected_violation | 'MAL-in Cell Culture' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_PAL_OUT_CELL_CULTURE` | suspected_violation | 'PAL-out Cell Culture' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MAL_OUT_CELL_CULTURE` | suspected_violation | 'MAL-out Cell Culture' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_PAL_IN_HARVEST` | suspected_violation | 'PAL-in Harvest' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MAL_IN_HARVEST` | suspected_violation | 'MAL-in Harvest' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_PAL_OUT_HARVEST` | suspected_violation | 'PAL-out Harvest' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MAL_OUT_HARVEST` | suspected_violation | 'MAL-out Harvest' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_PAL_IN_PURIFICATION_1` | suspected_violation | 'PAL-in Purification 1' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MAL_IN_PURIFICATION_1` | suspected_violation | 'MAL-in Purification 1' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_PAL_OUT_PURIFICATION_1` | suspected_violation | 'PAL-out Purification 1' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MAL_OUT_PURIFICATION_1` | suspected_violation | 'MAL-out Purification 1' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_PAL_IN_PURIFICATION_2` | suspected_violation | 'PAL-in Purification 2' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MAL_IN_PURIFICATION_2` | suspected_violation | 'MAL-in Purification 2' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_PAL_OUT_PURIFICATION_2` | suspected_violation | 'PAL-out Purification 2' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MAL_OUT_PURIFICATION_2` | suspected_violation | 'MAL-out Purification 2' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_03_room_size` | `R_MATERIAL_IN` | suspected_violation | 'Material-in' 면적 추정 불가 — KB·장비·비율 모두 없음 |
| `rule_04_clean_grade` | `R_RETURN_CORRIDOR` | suspected_violation | 주공정 Room이 Grade D인데 closed_system_main_process=False. Excel §5에 따르면 폐쇄형 장비 미사용 시 Grade C 이상 권고. |
| `rule_04_clean_grade` | `R_WASHING` | suspected_violation | 주공정 Room이 Grade D인데 closed_system_main_process=False. Excel §5에 따르면 폐쇄형 장비 미사용 시 Grade C 이상 권고. |
| `rule_11_wash_prep` | `LAYOUT` | info | Washing ↔ Preparation은 passthrough COP만 공유. 사람 직접 통행을 차단해야 함 (Documentation Agent 처리). |

---

## 8. 참조

- 필드 스펙·타입 정의: `rule_engine/output_schema.md`
- 원본 JSON (계약): `rule_engine/output_example.json`
- Python dataclass 소스: `rule_engine/models.py`
- 활용 가이드 (좌표 배치 순서): `output_schema.md` §10
