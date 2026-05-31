# NNE Pharmaplan 모범배치 — B3 Golden Fixture 재료

> **출처:** NNE Pharmaplan, *Bacterial Bio PilotPlant — Equipment Layout*,
> Green Cross Corporation, Doc. No. 0617C05016, Rev. 001, Conceptual Design.
> (Google Drive CD 폴더 / 업로드 Equipment_Layout_example.pdf)
> **용도:** B3 golden fixture (방법 B = 구조 검증, 정밀 좌표 아님).
> **목적:** 전문가가 실제 설계한 모범 배치. 우리 P-series 점수가 이 배치를
> strip-band보다 높게 평가하는지 = 점수 수식 타당성 검증.
> **한계:** 좌표는 그리드(X4~X12 가로, Y1~Y6 세로) 기반 상대 위치만. 정밀
> (x,y)는 방법 A에서 후속. 이 파일은 "어느 방-어느 장비-인접-공정순서" 구조용.

---

## 1. 건물 그리드 (캔버스 근사)

가로 축 X4~X12, 칸 폭(좌→우): 8.10 / 8.12 / 7.80 / 7.20 / 7.80 / 7.80 / 7.20 / 7.00 (m)
세로 축 Y1~Y6, 칸 높이(위→아래): 7.30 / 8.20 / 9.50 / 8.70 / 8.30 (m)
→ 대략 전체 가로 ~62 m × 세로 ~42 m. (CP-SAT/캔버스 근사용)

주: 도면상 좌측(X4~X8, Y3~Y6 영역)에 GMP 공정부가 밀집, 우측/상단은
기술구역(HVAC/WFI/전기)·방문자 동선.

---

## 2. 방(Room) 목록 + 구역

### 주공정 (process)
- Media & Buffer Preparation
- Seed Lab
- Fermentation
- Purification I
- Purification II
- Purification III
- Preparation (준비실)
- Weighing room (계량실)
- Cleaning (세척)
- Killtank (불활성화 탱크실)
- Sterile Storage (멸균 보관)
- Coldroom (냉장실)
- Storage Bulk (벌크 보관)
- IPC (공정중검사)

### 동선/전실 (corridor / airlock)
- Supply Corridor (공급 복도) — clean 측
- Return Corridor (리턴 복도) — dirty 측
- PAL (인원 전실, 다수)
- MAL (자재 전실, 다수)
- PB (Pass Box, 벽 너머 자재 전달)
- Ante (전실/대기)
- AL (에어록)
- Unload (하역)

### 보조/비분류 (auxiliary / NC)
- Gowning male / Gowning female (갱의 남/여)
- Toilet
- Office
- HVAC (공조기계실)
- WFI, PW, Electrical, Server (유틸리티/서버)
- Technical Area
- Janitor
- Storage Material (자재 보관)
- Visitors corridor (방문자 동선 — line of sight 창)

---

## 3. 방별 장비 (room → equipment, 면적 m²)

> 면적은 도면 표기 그대로. 같은 방 안 여러 장비는 병렬/공정 장비 혼재.

**Seed Lab**
- BSC (Biosafety Cabinet) 1.8
- Deep Freezer -80°C 1.4 (x2)
- Shaking Incubator 1.0 (x2)
- Fermenter 40L 1.4
- (관련) Microscope/pH meter/Water Bath 테이블 1.7

**Fermentation**
- Fermenter 300L 9.4
- Continuous Centrifuge 1.5
- High Speed Centrifuge 1.5
- BSC 1.8
- Table (pH-meter) 2.0
- Filter Integrity Tester 0.5
- Mobile Cart 2x Pump/Welder 0.9
- Mobile Storage Tank 300L 1.1
- Mobile CIP 2.0
- Filter Kit 0.2um 1.0
- Refrigerator 1.0

**Media & Buffer Preparation**
- Floor Balance 1000kg 1.5
- Table / pH Meter / Stirrer
- Filter Integrity Tester 2.0
- Mobile Cart Filter Kit 0.2um 1.0
- Tank 300L 3.9
- Mobile Tank 250L 0.9
- Mobile Cart 2x Pump 0.5 (x2)
- Palletank (single-use bag 50L) 0.5 (x5)

**Purification I**
- BSC (FHA) 1.8
- Filter Kit 0.2um 1.0
- Table (Pump/pH-meter) 0.9
- Filter Integrity Tester 0.6
- Äkta II 1.0 (x2)
- UF/DF 1.6 (x2)
- Mobile Tank (HA Ads) 200L 1.4
- Table (Balance/Pump/pH-meter) 2.0

**Purification II**
- BSC (Pump/pH-meter/Balance) 1.8
- Refrigerator 1.0
- Incubator 40°C 1.0
- Table 1.0
- Filter Kit 0.2um 1.0

**Purification III**
- BSC (PT) 1.8
- BSC (PRN) 1.8
- BSC (FHA) 1.8
- Table (Pump/pH-meter/Welder/Integrity tester) 2.0
- DF System 0.6
- Refrigerator 1.0

**IPC (In-Process Control)**
- Table 1 (Microscope/pH meter/Water Bath/Microcentrifuge) 1.7
- Table 2 (PC/label printer/Spectrometer) 0.8
- Table 4 (Table Top Cent/Shaker/Power Supply) 1.7
- Incubator 40°C 1.0
- Table 5 (ELISA Washer/Reader) 1.8
- Refrigerator 1.0
- BSC 1.8

**Preparation**
- Hot Air Sterilizer 1.0
- Autoclave 1000L 2.5
- (별도) Autoclave 1000L 1.8

**Cleaning**
- Washing Machine 680L 1.9
- Sinks x3 2.5
- Dryer 2.0
- Passbox 0.9
- Table 0.8

**Weighing room**
- Table / Hood / Balance 1·2·3 2.0

**Gowning (입구)**
- Shoe Wash 1.0
- Desinfection Dryer 2.0
- Refrigerator 1.0
- BSC 1.8

---

## 4. 인접 관계 (adjacency) — 핵심 구조

> 좌표 대신 "무엇이 무엇과 붙어야 하는가"가 golden의 핵심. 점수 P2 검증용.

- **Supply Corridor**가 주공정 방들(Seed Lab, Fermentation, Purification I/II/III,
  Media&Buffer Prep)의 **clean 측 진입**을 담당. 모든 공정 방은 supply corridor로 진입.
- **Return Corridor**가 **dirty 측 배출** 담당. supply와 return은 분리(직접 연결 금지).
- 공정 방 사이 인원 이동은 **단방향**(supply→방→return), 단 Purification I만 예외.
- PAL(인원)·MAL(자재)이 각 공정 방 진입부에 쌍으로 배치.
- **Cleaning ↔ Preparation**: Pass-through(PB)만 공유, 사람 직접 통행 차단.
- Killtank는 Fermentation/Purification 인접(폐액 불활성화).
- Biosafety 구역(Seed Lab, Fermentation)은 gown-over-gown, 별도 PAL.

---

## 5. 공정 순서 (product process order) — P1 검증용

```
Media & Buffer Prep → Seed Lab → Fermentation
  → Purification I → Purification II → Purification III
  → (Sterile Storage / Storage Bulk)
```

자재 흐름: Unload → Weighing → Prep → 공정
폐기 흐름: 공정 → Killtank → Return Corridor → Waste out

---

## 6. 동선 4종 (도면 범례: Flow = Personnel / Material / Bulk / Waste)

- **Personnel**: Gowning → Supply Corridor → (PAL) → 공정 방 → (PAL) → Return Corridor
- **Material**: Unload → MAL → 공정 방
- **Bulk**: 공정 산물 이동 (Fermentation → Purification → Storage Bulk)
- **Waste**: 공정 → Killtank → Return Corridor → 외부

LAF(Laminar Air Flow) 구역 별도 표기. clean(supply)과 dirty(return) 동선이
교차하지 않는 것이 이 배치의 핵심 GMP 원칙.

---

## 7. 이 golden으로 검증할 것 (B3 합격 기준)

1. 이 NNE 배치를 P1·P2·P6·P7에 넣었을 때, **strip-band baseline보다
   높은 점수**가 나와야 한다 (특히 P1 공정순서, P2 인접/응집).
2. 안 나오면 → 우리 점수 수식이 "전문가가 잘 한 배치를 못 알아본다"는
   신호 → 어느 P가 문제인지 진단 → CP-SAT 가기 전에 수식 보정.

## 8. 보류 자료 (나중에 꺼낼 것 — 지금 안 씀)

- **방법 A (정밀 좌표 golden)**: 위 그리드(X4~X12/Y1~Y6)+면적으로 각
  장비의 정밀 (x,y)를 읽어 좌표 수준 비교. → Phase C에서 CP-SAT 결과를
  전문가 배치와 좌표로 대조할 때.
- **NNE 매핑 워크북 (URS_NNE_Mapping_v0.3, F1~F10 역공학 수식)**:
  점수 수식 보강·특허 명세 단계에서. 특히 F3(Class↔Filter↔ACR↔Pressure)
  = 특허 스모킹건.
- **과거 URS 3.6 장비 사양**: 실데이터 golden / rule_engine 3.6 연결 후 검증.