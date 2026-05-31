# GMP Layout Design Decision Tree
**대상**: mAb 8,000L culture Line (전체 면적 3,300 m² 기준)
**출처**: GMP_Layout_Logic_0510.xlsx — Layout 설계 원리 시트 (12개 항목)
**버전**: v0.1 (개념설계 수준)

---

## 0. 트리 구조의 표기 규칙
- `Phase N` : 설계 진행 단계 (직렬 수행)
- `D-x.y` : Decision Node (조건 분기)
- `A-x.y` : Action Node (Drawing 행위)
- `IF … → …` : 조건부 분기
- `[INPUT]` : 외부 입력값, `[OUTPUT]` : 산출물

---

## Phase 1. 사전조건 분석 (Pre-condition Analysis)

```
D-1.1  건축물 인터페이스 확인
  ├─ [INPUT] 원자재 반입구 좌표 (RAW_IN)
  ├─ [INPUT] 폐기물 반출구 좌표 (WASTE_OUT)
  └─ IF 층수 ≥ 2 → [INPUT] 엘리베이터 좌표 (ELEV)

D-1.2  전체 면적/규모 확인
  ├─ [INPUT] TOTAL_AREA  (default 3,300 m²)
  ├─ [INPUT] PROCESS_SCALE = "mAb 8,000L culture"
  └─ [INPUT] OVERLAP_PRODUCTION (Y/N, 다품목·공정 overlap 여부)

A-1.3  전역 좌표계 설정
  └─ 단위: mm, 원점: 건축물 외곽 좌하단
```

---

## Phase 2. Zoning (구역 분할)

```
D-2.1  3대 구역 분할
  ├─ 공정구역 (Process Area)
  │     ├─ 직접 제조 Room (배지/버퍼/배양/회수/정제/세척/준비/공급복도 등)
  │     └─ 면적 비율:
  │           IF OVERLAP_PRODUCTION == Y → 60~70% × TOTAL_AREA
  │           ELSE                       → 40~50% × TOTAL_AREA
  ├─ 보조구역 (Support Area)
  │     ├─ Cell bank / DS / 자재 / 장비 보관실, 갱의실, IPC, CIP 등
  │     ├─ 청정등급: Grade D 또는 CNC
  │     └─ 위치: 입구(RAW_IN)에 가까운 쪽
  └─ NC구역
        ├─ 화장실, 사무실, 모니터링/제어실, 로비
        └─ IF 별도 층/건물에 배치 계획 있음 → 본 Layout에서 생략

D-2.2  전체 동선 컨셉
  ├─ 시작: RAW_IN 근접 (배지/버퍼 조제) 
  ├─ 종료: WASTE_OUT 근접 (정제 후/DS 보관)
  └─ 단, Room 배열의 절대 우선순위 아님 (공정 특성 우선)

A-2.3  복도 골격 배치
  ├─ Supply Corridor → 중앙
  └─ Return Corridor → 테두리(perimeter)
```

---

## Phase 3. Room 청정등급 부여 (Clean Grade Classification)

EU GMP Annex 1: **(1) Grade A, (2) B, (3) C, (4) D, (5) CNC, (6) NC**

```
FOR EACH Room r:
  D-3.1  무균공정 여부 판정
    ├─ IF r에 층류장치(Isolator/RABS/Cleanbench/BSC) 존재
    │     → r 내 barrier = Grade A
    │     → barrier 둘러싼 Room 본체 = Grade B
    │
    └─ ELSE → D-3.2

  D-3.2  주요 제조공정 여부
    ├─ IF r ∈ {배지·버퍼 조제, 배양, 정제 …}  (주요 공정)
    │   ├─ IF 모든 제조공정이 폐쇄형(closed) 장비 → Grade D
    │   └─ ELSE → Grade C
    │
    └─ ELSE → D-3.3

  D-3.3  보조 기능 Room 판정
    ├─ IF r ∈ {자재 보관, 세척, 갱의, IPC, 통로(corridor)}
    │     → Grade D 또는 CNC
    │
    ├─ IF r ∈ {화장실, 사무실, 모니터링실, 로비}
    │     → NC
    │
    └─ ELSE (모호 시) → Grade D (보수적)

A-3.4  Layout 색상 부여 (50% 투명도)
  ├─ Grade A  : Green-diagonal Black
  ├─ Grade B  : Green
  ├─ Grade C  : Yellow
  ├─ Grade D  : Blue
  ├─ CNC      : Gray-dotted Black
  └─ NC       : Gray
```

### 참고 권장 청정등급 (Room 범례 시트 기반)

| Room | 청정등급 | 권장면적(m²) |
|---|---|---|
| 배지 조제실 | C 또는 D | 100 |
| 버퍼 조제실 | C 또는 D | 200 |
| Seed 접종실 | B 또는 C | 40 |
| 배양실1 (Seed train) | C 또는 D | 150 |
| 배양실2 (Cell Culture) | C 또는 D | 150 |
| 회수실 (Harvest) | C 또는 D | 60 |
| 정제실1 (Purification 1) | C 또는 D | 300 |
| 정제실2 (Purification 2) | C 또는 D | 100 |
| 공정 준비실 | C 또는 D | 80 |
| 세척실 | C 또는 D | 60 |
| 공급복도 | C 또는 D | 150 |
| 리턴복도 | D 또는 CNC | 250 |
| Cell bank 보관실 | D 또는 CNC | 20 |
| DS 보관실 | D 또는 CNC | 50 |

---

## Phase 4. Room 크기 결정 (Room Sizing)

```
FOR EACH Room r:
  D-4.1  Room 형상
    ├─ Default → 직사각형(정사각형 포함)
    └─ IF 공간 구조상 불가 → 직사각형 합으로 구성

  D-4.2  Room 내부 면적 산정
    ├─ 입력: 장비 목록 (제조장비 범례 시트 참조)
    │       e.g. 배양실 ← Wave Reactor 20L, BioReactor 100/500/2000/10000L, Storage 2000L
    ├─ 산식: Area_min = Σ(장비 footprint) + 장비간 간격(≥1000mm) + 벽-장비(600~1200mm)
    └─ A-4.2 r.area = max(Area_min, 권장면적)

  D-4.3  복도 폭(width) 결정
    ├─ Default 2000~3000 mm
    ├─ IF 전체 면적 부족 → 1500~2000 mm 허용
    └─ Hard min = 1500 mm

  D-4.4  전실(Air-Lock) 크기
    ├─ IF 면적 여유 → 3000 × 3000 mm (이상)
    └─ ELSE → 사람·물품 통과 가능한 최소 크기 (e.g. PAL 12 m², MAL 16 m²)

  D-4.5  천정 높이(H) 결정
    ├─ Default 2700 ~ 3000 mm
    ├─ IF 장비 높이 > 2700 mm → 우물형 천정(well type ceiling)
    └─ IF 장비 = 10,000L bioreactor → 하단 service area, head만 Room 노출

  A-4.6  체적 산정
    └─ Volume = Area × H  (well type 천정 시 부분 보정)
       → 환기횟수(ACPH) 결정 인자
              Grade A: 0.36~0.54 m/s (풍속)
              Grade B: 40~60 ACPH
              Grade C: 20~40 ACPH
              Grade D: 6~20 ACPH

  D-4.7  주요 공정 Room 합산 면적 검증
    └─ IF Σ(주요 공정 Room 면적) ∉ [40%, 70%] × TOTAL_AREA
          → 면적 재조정 루프 (D-4.2 회귀)
```

---

## Phase 5. Room 배열 (Room Arrangement — Process Flow 기반)

```
A-5.1  공정 순서대로 1차 정렬
  mAb 공정 순서:
    Cell bank storage → Media prep → Buffer prep → Inoculation(Seed)
      → Cell Culture(배양1·2) → Harvest(회수) → Purification 1
      → [Virus Filtration]  ← 경계
      → Purification 2 → DS storage

D-5.2  One-way (편도) Flow 적용 구간 판정
  ├─ Virus Filtration **前** 공정 Room (Seed 접종실, 배양실, 회수실, 정제실1)
  │     → One-way Flow (입구 ≠ 출구)
  │     → 입구는 Supply Corridor 측, 출구는 Return Corridor 측
  │
  └─ Virus Filtration **後** 공정 Room (정제실2, DS 등) → 양방향 가능

A-5.3  Room 도어 위치 1차 결정
  └─ 자재/사람 출입 동선이 최단이 되는 변(edge)에 도어 부착

D-5.4  부속(Adjacent) Room 필요 여부
  └─ IF 공정 Room이 부속실 필요(e.g. 정제실1 내 부분 격리)
        → 단일 도어로 연결, 사람·물품 자유 왕래
```

---

## Phase 6. 전실(Air Lock) 배치

```
FOR EACH 인접 Room 쌍 (r1, r2):

  D-6.1  AL 필요 여부
    ├─ IF Grade(r1) ≠ Grade(r2)             → AL 필요
    ├─ IF 공정 중요도 구분 필요 (e.g. Virus 前후)  → AL 필요
    └─ ELSE → AL 생략

  D-6.2  AL 개수 결정 (해당 공정 Room 기준)
    ├─ IF Grade(r) == B  AND  one-way
    │     → 4개 (PAL-in, MAL-in, PAL-out, MAL-out)
    │
    ├─ ELIF Grade(r) == C  AND  one-way
    │     ├─ IF 공간 여유 → 4개 (PAL-in, MAL-in, PAL-out, MAL-out)
    │     └─ ELSE        → 2개 (AL-in, AL-out  ※ PAL+MAL 통합)
    │
    └─ ELIF 양방향 Flow
          → 1개 (AL)

  D-6.3  AL 타입 (압력 패턴) 결정
    ├─ Default → Cascade
    │     공기 흐름: 高차압 Room → AL → 低차압 Room
    │
    ├─ IF Biological safety로 r1↔r2 공기 격리 필요
    │     ├─ AL이 양쪽보다 낮은 압력 → Sink (양쪽 오염원 차단)
    │     └─ AL이 양쪽보다 높은 압력 → Bubble (외부 침입 차단)

  A-6.4  AL과 복도 연결 규칙
    ├─ One-way Room의 입구 측 AL → Supply Corridor 연결
    └─ One-way Room의 출구 측 AL → Return Corridor 연결

  D-6.5  AL Grade 부여
    ├─ MAL-in/out, PAL-in/out (Grade B 인접) → B 또는 C 또는 D
    ├─ CAL (Common AL)                       → C 또는 D
    └─ 보조구역 진입 AL                       → CNC 또는 NC
```

---

## Phase 7. 복도(Corridor) 설계

```
D-7.1  복도 유형 분리
  ├─ Supply Corridor : 인원 입실 + 자재 반입 (청정도 ↑)
  └─ Return Corridor : 인원 퇴실 + 폐기물 반출 (청정도 ↓)

A-7.2  복도 연결 규칙 (HARD CONSTRAINT)
  ├─ Supply와 Return은 **직접 연결 금지**
  │     → 교차오염(cross contamination) 원천 차단
  │
  └─ Return Corridor 끝단 → 보조구역(Grade D 또는 CNC)으로 출구

D-7.3  복도 폭
  └─ 2000~3000 mm (최소 1500 mm)
```

---

## Phase 8. 도어(Door) 설계

```
FOR EACH Door d on Room r:

  D-8.1  도어 폭
    ├─ Default 1000 mm (swing door)
    └─ IF d ∈ MAL (자재용) → 1500 ~ 2000 mm

  A-8.2  도어 열림 방향
    └─ Room 간 차압이 흐르는 방향으로 열림
       (자연적으로 견고히 닫히도록 — passive fail-safe)

  A-8.3  도어 위치
    └─ Room 내·외 동선 최단 위치에 부착

  D-8.4  Room별 도어 개수
    └─ 용도에 따라 1 ~ 4개 이상
```

---

## Phase 9. 제조 장비 배치 (Equipment Placement)

```
FOR EACH Room r:

  A-9.1  공정 순서대로 장비 배치
    └─ 입력: 제조장비 범례 시트의 "단위 공정" 컬럼 순

  D-9.2  장비 간 간격
    └─ ≥ 1000 mm  (작업 및 청소 공간 확보)

  D-9.3  장비-벽 간격
    ├─ 600 ~ 1200 mm
    └─ 청소 및 유틸리티 접근성 고려

  D-9.4  벽면 부착 여부
    ├─ IF 전기/유틸리티 공급 = 벽면형 → 장비를 벽면 인접 배치
    └─ IF 전기/유틸리티 공급 = 천정형 → 장비를 Room 중앙 배치 허용

  D-9.5  대형 장비 특수 처리
    └─ IF 장비 = BioReactor 10,000L  (또는 H > Room 천정고)
          → 하단(스커트) = service area로 노출, head space만 Room 내 노출
          → 또는 well type ceiling 적용
```

---

## Phase 10. 세척실 / 준비실 (Washing / Preparation)

```
A-10.1  연결 경로
  ├─ 세척실 ↔ Return Corridor  (출구 측 AL 경유)
  └─ 준비실 ↔ Supply Corridor

A-10.2  Pass-through COP 공유
  └─ 세척실과 준비실은 **인접 배치**, Pass-through COP를 공유

D-10.3  세척실 ↔ 준비실 사람 왕래 (HARD CONSTRAINT)
  └─ 물리적으로 차단 (직접 통행 금지)
     → 세척실은 Return, 준비실은 Supply 경로 분리 보장
```

---

## Phase 11. NC 구역 배치

```
D-11.1  NC Room 필요성 판정
  ├─ IF 별도 층/건물에 배치 계획 있음
  │     → 본 Layout에서 생략 가능
  │
  └─ ELSE → A-11.2

A-11.2  NC Room 배치 원칙
  ├─ 별도 영역으로 구분 (공정·보조구역 형태에 방해 ×)
  └─ 화장실, 사무실, 모니터링/제어실, 로비
```

---

## Phase 12. 차압(Differential Pressure) 부여

```
FOR EACH Room r:

  A-12.1  차압 표기 단위
    └─ Pa, 외부 대기압 = 0 Pa

  D-12.2  청정등급 간 차압
    └─ 인접 Room 등급 다를 시 ≥ 10 ~ 15 Pa 압력차 유지
       서열: Grade B > Grade C > Grade D > CNC > NC

  D-12.3  동일 등급 Room 간 차압
    ├─ Default → 0 Pa (차압 미부여 허용)
    │
    └─ 예외: Virus Removal 전후 정제실
          → DP(정제실2) ≥ DP(정제실1) + 0.5 Pa

  A-12.4  급기/배기 균형 설계
    └─ Room별 supply/exhaust 풍량 조합으로 목표 차압 형성
```

---

## 부록 A. 출입복장 분기 (Phase 3 의 종속 규칙)

```
FOR EACH Room r (사람 진입 시):
  ├─ IF Grade(r) == B → 무균복 (over gowning)
  ├─ IF Grade(r) == C → 무진복 (over gowning)
  └─ IF Grade(r) ∈ {D, CNC} → 스크럽 (degowning and gowning)
```

→ 갱의실(Gowning Room)의 위치와 개수 결정 시 위 규칙으로 분기.

---

## 부록 B. Design Agent 구현 시 권장 데이터 흐름

```
[INPUT] ─→ Phase 1 ─→ Phase 2 ─→ Phase 3 ─→ Phase 4 ──┐
                                                       │ (Room 정의 완료)
                                                       ▼
                       Phase 5 (배열) ←─────── Phase 6 (AL) ←──── Phase 7 (복도)
                            │
                            ▼
                       Phase 8 (도어) → Phase 9 (장비) → Phase 10 (세척/준비)
                            │
                            ▼
                       Phase 11 (NC) → Phase 12 (DP)
                            │
                            ▼
                       [OUTPUT] 개념설계 평면도 (DXF/SVG)
```

각 Phase는 **(검증 → 부분 수정 루프)** 가 권장됨.
- 예: Phase 4 종료 후 Phase 2의 "주요 공정 Room 40~70%" 제약 재검증
- 예: Phase 6 종료 후 Phase 7의 "Supply↔Return 직접 연결 금지" 재검증
- 예: Phase 12 종료 후 인접 등급 차압 일관성 재검증

---

## 부록 C. Hard Constraint 요약 (Agent의 종료 검증 체크리스트)

| # | 제약 (Hard Constraint) | 근거 |
|---|---|---|
| C1 | 공급복도와 리턴복도는 직접 연결 금지 | 교차오염 방지 |
| C2 | 세척실과 준비실 사람 왕래 물리적 차단 | 교차오염 방지 |
| C3 | One-way Room의 입구·출구 분리 (입구 AL ≠ 출구 AL) | Virus 前 공정 Bio-safety |
| C4 | Grade B Room (one-way) → 전실 4개 필수 | EU GMP Annex 1 |
| C5 | 인접 등급 간 차압 ≥ 10~15 Pa | EU GMP Annex 1 |
| C6 | 등급 서열 : B > C > D > CNC > NC | EU GMP Annex 1 |
| C7 | 복도 폭 ≥ 1500 mm | 인원·자재 동선 |
| C8 | 장비 간 간격 ≥ 1000 mm, 장비-벽 ≥ 600 mm | 작업·청소 공간 |
| C9 | 주요 공정 Room 합 ∈ [40%, 70%] × TOTAL_AREA | 면적 효율 |
| C10 | 도어 열림 방향 = 차압 흐름 방향 | 자연 폐쇄 |

