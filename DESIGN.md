# Design System — Layout-Generator

> 이 프로젝트의 모든 시각적 산출물(SVG 도면, 다이어그램, CLI/Web UI, 발표 자료, 논문 그림)이
> 따르는 **단일 디자인 시스템**입니다. 실리콘밸리 톱티어 제품 디자인 + 건축 컨셉 다이어그램 +
> 정보 시각화 원칙을 통합한 프레임워크.

---

## 1. 디자인 철학 (Principles)

### 1.1 핵심 원칙 (Dieter Rams, 차용 & 우리 컨텍스트 적용)
1. **Honest** — 도면은 룰 위반을 미화하지 않는다. 위반은 시각적으로도 드러난다.
2. **Unobtrusive** — 색은 정보를 전달할 만큼만. 장식적 색 금지.
3. **Thorough to detail** — 1mm/0.5pt 단위까지 정렬. "거의 맞춤"은 잘못 맞춘 것.
4. **Useful** — 모든 시각 요소는 의사결정에 기여한다. data-ink ratio 최대화 (Tufte).
5. **Long-lasting** — 트렌디한 효과(neumorphism, glassmorphism) 금지. 10년 뒤에도 통한다.

### 1.2 레퍼런스 (어디서 영감을 가져왔나)

| 영역 | 레퍼런스 | 차용 포인트 |
|---|---|---|
| 디지털 제품 | **Linear** | 절제된 다크 톤, 정교한 hairline, generous whitespace |
| 디지털 제품 | **Vercel** | 흑백 미니멀리즘 + 전략적 액센트 색 |
| 디지털 제품 | **Stripe** | 타이포그래피 계층 마스터리, 숫자 정렬 |
| 디지털 제품 | **Figma** | 깔끔한 형상, 미묘한 그림자, UI 아이콘 시스템 |
| 건축 컨셉 | **BIG (Bjarke Ingels Group)** | 다이어그램으로 컨셉 설명, 강한 대비 |
| 건축 컨셉 | **SOM, OMA** | 흰 바탕 + 단일 액센트 컬러, 강한 타이포 |
| 정보 시각화 | **Edward Tufte** | data-ink ratio, small multiples, 무의미한 chartjunk 제거 |
| UI 시스템 | **Refactoring UI (Wathan & Schoger)** | 색 시스템 구성, 계층 표현, 미세 조정 노하우 |
| 컬러 시스템 | **Tailwind (50~950 scale), oklch()** | 지각 균일 색, 명도 일관성 |
| 접근성 | **WCAG 2.2 AA (4.5:1)** | 컬러 + 텍스트 대비 |

### 1.3 우리만의 차별화 — "GMP-grade Visual Honesty"
바이오 GMP 설계는 *눈으로 보고도* 안전성/규제를 판단할 수 있어야 합니다. 그래서:
- 청정등급 색은 직관적 위계(어두울수록 깨끗 X, 채도가 높을수록 더 규제됨)
- 차압 라벨은 숨기지 않음 — 도면에 항상 노출
- One-way flow 화살표는 도면의 "주역" 수준으로 강조

---

## 2. 컬러 시스템

### 2.1 베이스 (Neutral Scale)
중성 회색은 oklch로 지각 균일하게 설계. 배경/벽/텍스트의 99%는 이 스케일에서 옴.

| 토큰 | hex | 용도 |
|---|---|---|
| `--neutral-0`   | `#FFFFFF`     | 캔버스 외곽 |
| `--neutral-50`  | `#FAFAF9`     | 도면 캔버스 배경 (warm white) |
| `--neutral-100` | `#F5F5F4`     | 그리드 라인 (subtle) |
| `--neutral-200` | `#E7E5E4`     | 보조선, 범례 보더 |
| `--neutral-400` | `#A8A29E`     | 보조 텍스트, 치수선 |
| `--neutral-600` | `#57534E`     | 본문 텍스트 |
| `--neutral-800` | `#292524`     | 벽 (architectural line) |
| `--neutral-900` | `#1C1917`     | 헤더 텍스트, 건물 외곽선 |

### 2.2 청정등급 색 (Refined — Tailwind-grade 스케일)
원색 회피. 각 등급은 **fill (배경)**, **border (윤곽)**, **label (텍스트)** 3계층으로.

| 등급 | fill (50% opacity 권장) | border | label | 의미 |
|---|---|---|---|---|
| **A** | `#A7F3D0` (emerald-200) + diagonal `#064E3B` | `#047857` | `#064E3B` | 무균공정 barrier (Isolator/RABS) |
| **B** | `#6EE7B7` (emerald-300) | `#059669` | `#064E3B` | A를 둘러싼 Room |
| **C** | `#FCD34D` (amber-300) | `#D97706` | `#78350F` | 주공정 Room (default) |
| **D** | `#93C5FD` (blue-300) | `#2563EB` | `#1E3A8A` | 보조/주공정-closed |
| **CNC** | `#D6D3D1` (stone-300) + dotted `#44403C` | `#78716C` | `#1C1917` | 자재/세척/갱의/통로 |
| **NC** | `#E7E5E4` (stone-200) | `#A8A29E` | `#44403C` | 사무/화장실/로비 |

### 2.3 동선/Flow 색 (Categorical Accent)
4종 동선은 *데이터에 의미* 가 있는 색이라, 채도 있는 강조색을 절제 사용.

| 동선 | 화살표 색 | hex |
|---|---|---|
| Personnel (인원) | indigo | `#4F46E5` |
| Material (자재) | teal | `#0D9488` |
| Waste (폐기물) | rose | `#E11D48` |
| Product (제품/공정 흐름) | violet | `#7C3AED` |

### 2.4 차압/압력 (Sequential)
차압은 수치 데이터 → sequential blues (light → dark).
`#EFF6FF → #DBEAFE → #93C5FD → #3B82F6 → #1D4ED8` (0Pa → 30Pa+)

### 2.5 상태/룰 위반 (Semantic)
| 의미 | 색 |
|---|---|
| OK / Pass | `#10B981` (emerald-500) |
| Warning | `#F59E0B` (amber-500) |
| Hard violation | `#DC2626` (red-600) |
| Info | `#3B82F6` (blue-500) |

### 2.6 접근성 룰
- 모든 텍스트 vs 배경: WCAG AA 4.5:1 이상 (label 토큰이 fill 위에서 4.5:1 보장)
- 색맹 대비: fill만 의존 금지, 패턴(diagonal/dotted)도 병행 (Grade A, CNC)
- 인쇄(흑백) 대비: 패턴이 등급을 구분 (color-blind & B&W safe)

---

## 3. 타이포그래피

### 3.1 폰트 패밀리 (CSS @font-face 우선순위)
```css
--font-display: "Inter", "Pretendard", -apple-system, "Helvetica Neue", sans-serif;
--font-body:    "Inter", "Pretendard", -apple-system, "Helvetica Neue", sans-serif;
--font-mono:    "JetBrains Mono", "SF Mono", Menlo, monospace;
```
- Inter — 라틴 (Stripe/Linear/Figma 다 사용)
- Pretendard — 한글 (네이버 사용, Inter와 metric 정합)
- JetBrains Mono — 치수/수치 정렬 (tabular-figures)

### 3.2 스케일 (Perfect Fourth, 1.333 비율)
| 토큰 | px | 용도 |
|---|---|---|
| `--text-xs`  | 10  | 치수선, 범례 보조 |
| `--text-sm`  | 12  | 장비명, 룰 위반 라벨 |
| `--text-base`| 14  | Room 이름 본문 |
| `--text-md`  | 16  | Room 이름 (핵심 Room) |
| `--text-lg`  | 20  | 섹션 헤더, 범례 타이틀 |
| `--text-xl`  | 28  | 도면 타이틀 |
| `--text-2xl` | 40  | 발표/표지 |

### 3.3 사용 규칙
- **숫자는 무조건 tabular-figures** (`font-variant-numeric: tabular-nums`)
- **Room ID/장비명/등급 라벨은 uppercase + tracking 0.05em**
- **본문은 1.5 line-height**, 라벨은 1.2

---

## 4. 공간 / 그리드 / 레이아웃

### 4.1 8pt Grid System
모든 spacing, padding, sizing은 **4의 배수**, 권장 8의 배수.
```
4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 / 128
```

### 4.2 도면 캔버스 그리드
- 건물 실측 1mm = SVG 1unit (정확한 스케일)
- 보조 그리드: 1000mm 간격, `--neutral-100`, 0.5px hairline
- 메이저 그리드: 5000mm 간격, `--neutral-200`, 1px

### 4.3 도면 페이지 구조 (Title Block — 건축 도면 표준)
```
┌────────────────────────────────────────────────────────────────┐
│ [Project Title]                          [Logo / Sheet ID]    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│                    [DRAWING CANVAS]                           │
│                                                                │
│                                          ┌──────────────────┐ │
│                                          │ LEGEND           │ │
│                                          │ ▢ Grade A …      │ │
│                                          │ → Personnel       │ │
│                                          └──────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ Scale 1:200 │ Date │ Modality: mAb │ By: Rule Engine v0.1     │
└────────────────────────────────────────────────────────────────┘
```

---

## 5. 선 두께 / Z-order (도면 layering)

### 5.1 Stroke Weights (architectural convention)
| 요소 | Weight (px @ 1:200) | 비고 |
|---|---|---|
| 건물 외곽선 | 3 | `--neutral-900` |
| 외벽 | 2.5 | `--neutral-800` |
| 내벽 | 1.5 | `--neutral-800` |
| 도어 | 1.5 + 0.75 swing arc dashed | swing은 차압 흐름 방향 |
| 장비 윤곽 | 1 | `--neutral-600` |
| 치수선 / 보조선 | 0.5 | `--neutral-400` |
| 메이저 그리드 | 1 | `--neutral-200` |
| 마이너 그리드 | 0.5 | `--neutral-100` |

### 5.2 Z-order (SVG `<g>` 그룹 순서)
```
z0  배경 (neutral-50)
z1  마이너 그리드
z2  메이저 그리드
z3  건물 외곽선
z4  Room fill (등급별)
z5  Room border / 벽
z6  도어 + swing arc
z7  Airlock (다른 fill pattern)
z8  장비
z9  Flow 화살표 (4종)
z10 텍스트 라벨 (Room 이름, 등급 chip, 면적, 차압)
z11 치수선
z12 범례 & 타이틀 블록
z13 룰 위반 마커 (Hard violation 적색 outline)
```

---

## 6. 컴포넌트 (재사용 단위)

### 6.1 Grade Chip
Room 이름 옆에 붙는 작은 등급 표시.
```
┌─────┐
│  C  │   ← fill: grade-C, label: grade-C-text, 4px radius, 16x16
└─────┘
```

### 6.2 Pressure Badge
차압 표시. 숫자 + Pa 단위. 사각형, monospace.
```
[ +30 Pa ]   ← border: pressure scale에 따라 변화
```

### 6.3 Flow Arrow
- 굵기 1.5px, head 8x8
- 점선 = bidirectional, 실선 = one-way
- 색: §2.3 동선 색

### 6.4 Equipment Block
- fill: white
- border: 1px neutral-600
- 안에 장비명 (text-xs), 우상단 step ID badge

### 6.5 Door
- 1.5px 검은 선 + 90° 호 (swing direction)
- MAL은 1500~2000mm, PAL은 1000mm → 시각적으로 길이 다름

### 6.6 Airlock
- Room보다 더 진한 border (2px)
- 모서리에 작은 글자: `PAL-in`, `MAL-out` 등
- type별 미세한 패턴 차이 (cascade/sink/bubble)

### 6.7 Title Block (도면 우하단)
- monospace, all caps
- 필드: PROJECT / SCALE / DATE / MODALITY / SHEET / PREPARED BY

### 6.8 Legend (도면 우상단)
- 범례 박스: 흰 배경, 0.5px neutral-200 보더
- 등급 6개 + 동선 4종 + 차압 스케일 1개

---

## 7. 모션 & 인터랙션 (Drawing Agent web preview용)

> v1은 정적 SVG. v2에서 Web 미리보기 들어가면 적용.

- Easing: `cubic-bezier(0.2, 0.8, 0.2, 1)` (Linear/Vercel 풍)
- 호버: 150ms, opacity 0.85
- 룰 위반 강조: 적색 outline pulse 1.5s

---

## 8. 도면 스타일 가이드 — 실제 출력 시 체크리스트

품질 관리. Drawing Agent가 매번 통과해야 하는 체크.

- [ ] 캔버스 padding ≥ 64px (8pt grid)
- [ ] 모든 텍스트가 fill 위에서 contrast ≥ 4.5:1
- [ ] 그리드는 1mm × 1unit 정확 스케일
- [ ] 타이틀 블록 우하단 존재 (Project / Scale / Date / Sheet)
- [ ] 범례 우상단 존재 (등급 + 동선 + 차압)
- [ ] 모든 Room이 등급 chip + 면적 + 차압 라벨 가짐
- [ ] 모든 도어가 swing arc 가짐 (방향이 차압 흐름과 일치)
- [ ] One-way 구간은 화살표로 명시
- [ ] Hard constraint 위반은 적색 outline + 텍스트 마커
- [ ] 인쇄(흑백)에서도 등급 구분 가능 (패턴 차이)
- [ ] 색맹 시뮬 (deuteranopia) 에서도 동선 4종 구분 가능

---

## 9. 코드 토큰화 (구현용)

색·타이포·스페이싱 토큰은 `src/drawing_agent/design_tokens.py` 에서 단일 정의.
Drawing Agent의 모든 SVG 출력은 이 토큰만 참조 (마법 숫자 금지).

```python
# 예시 (실제 모듈은 Drawing Agent 단계에서 생성)
COLOR_NEUTRAL = { 0: "#FFFFFF", 50: "#FAFAF9", ..., 900: "#1C1917" }
GRADE_TOKENS = {
    "C": {"fill": "#FCD34D", "border": "#D97706", "label": "#78350F", "pattern": None},
    ...
}
TEXT = { "xs": 10, "sm": 12, "base": 14, "md": 16, "lg": 20, "xl": 28 }
GRID = 8  # base unit (px)
```

---

## 10. 변경 이력

- v0.1 (2026-05-26) — 초안. Linear/Vercel/Stripe + BIG/SOM/OMA + Tufte 통합 프레임워크.
