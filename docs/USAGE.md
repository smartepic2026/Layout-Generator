# 사용 설명서 — 본인 URS 로 도면 생성하기

> 대상: 레포를 받아 **직접 본인 URS 를 넣어 테스트**하려는 분.
> 흐름: `URS(.xlsx)` → **Rule Engine** → `spec.json` → **Drawing Agent** → `도면(.svg)`

---

## 1. 설치 (최초 1회)

```bash
git clone https://github.com/smartepic2026/Layout-Generator.git
cd Layout-Generator
git checkout drawing/floorplan-v2        # ← 최신 도면 작업 브랜치

python3 -m venv .venv && source .venv/bin/activate   # (권장) 가상환경
pip install -r requirements.txt
```

- **Python 3.10+ (3.13 까지 확인됨)**.
- 핵심 의존성: `pydantic`, `openpyxl`(xlsx 파싱), `ortools`(CP-SAT), `svgwrite`.
- SVG 는 **브라우저로 바로 열림**. PNG 로 변환하려면 `pip install cairosvg` (선택).

---

## 2. 본인 URS 준비

입력은 **xlsx 한 파일**입니다. 예제 `examples/teammate_urs_0516.xlsx` 를 복사해
값만 바꾸세요. 필요한 시트는 2개:

| 시트명 | 내용 |
|---|---|
| **`Room 요구 규격서`** | Room 목록(청정도·목표 ACH·면적 비율·갱의·출입동선) + **row 4 에 건축물 메타**(층수·제공 면적·가로×세로·인원/자재/폐기물 출입구 방향) |
| **`제조 장비 규격서`** | Room 별 장비(규격 W×D×H·중량·세부공정 No.) |

> 시트명·열 위치는 `src/rule_engine/urs_parser.py` 상단 상수(`_SHEET_ROOMS`,
> `_SHEET_EQUIPMENT`)에 정의돼 있습니다. 양식이 다르면 거기만 맞추면 됩니다.
> 가장 안전한 방법은 **예제 xlsx 의 시트 구조를 그대로 두고 값만 교체**하는 것.

---

## 3. 실행 — 2단계

```bash
# (1) URS.xlsx → 7블록 spec.json   (룰엔진 + 정렬 어댑터)
python3 -m src.cli rule-engine  <내URS.xlsx>  output/spec.json

# (2) spec.json → 도면 SVG
python3 -m src.cli draw  output/spec.json  output/layout.svg
```

예시:
```bash
python3 -m src.cli rule-engine examples/teammate_urs_0516.xlsx output/spec.json
python3 -m src.cli draw output/spec.json output/layout.svg
# → output/layout.svg 를 브라우저로 열기
```

(1) 실행 시 콘솔에 `rooms / airlocks / adjacency / zones` 개수가 출력됩니다.
(2) 실행 시 `rooms placed / airlocks / doors` 와, **배치 누락된 방이 있으면 `[WARN]`** 이 출력됩니다.

---

## 4. draw 옵션

```bash
python3 -m src.cli draw output/spec.json output/layout.svg [옵션]
```

| 옵션 | 기본 | 설명 |
|---|---|---|
| `--flows full\|main\|off` | `full` | 동선 표현. **`main`=대표 1경로(깔끔)**, `full`=공정실별 전체(comb), `off`=동선 없음 |
| `--strip` | (꺼짐) | 레거시 strip-band 토폴로지 강제. **켜지 마세요** — 일부 방이 누락됩니다. 기본(gradient)이 전 방 배치 |
| `--width N` / `--height N` | URS 값 | 건물 가로/세로(mm) 강제 override |

깔끔한 검토는 `--flows main` 을 권장:
```bash
python3 -m src.cli draw output/spec.json output/layout.svg --flows main
```

SVG 를 브라우저로 열면 동선이 종류별 그룹(`<g id="flow-personnel">` …)이라
개발자도구/CSS 로 켜고 끌 수 있습니다.

---

## 5. 결과 읽는 법

- 좌→우 **청정도 구배**: NC(회색) → Grade D 보조(파랑) → Grade C 공정(노랑).
- 방 라벨: `영문명 / 한글 / Grade·차압·면적·ACPH / 천정고·갱의`.
- 전실(에어록): 박스 안에 `PAL_in` 등 종류 + `cascade`(공기흐름 타입).
- 동선 4색(우측 범례): 인원(남)·자재(청)·폐기물(적)·제품(보). 제품은 공정실 간
  벽을 가로지름(규정: CIP 배관 운반).

---

## 6. 자주 묻는 것

- **draw 가 크래시(`rationale.*.target` 등 Pydantic 오류)** → raw 룰엔진 출력을
  바로 draw 에 넣은 경우. 반드시 `rule-engine` 단계(어댑터 포함)를 먼저 거친
  `spec.json` 을 draw 에 넣으세요.
- **방이 일부 안 그려짐 / `[WARN]`** → `--strip` 을 쓴 경우입니다. 옵션을 빼면(기본
  gradient) 전 방이 배치됩니다.
- **xlsx 파싱 오류** → 시트명이 `Room 요구 규격서` / `제조 장비 규격서` 인지,
  건축물 메타가 Room 시트 row 4 에 있는지 확인.

---

## 7. 산출물 위치

- `output/spec.json` — 룰엔진 7블록(rooms/airlocks/adjacency/flow_paths/zones/
  constraints/rationale). 외부 Drawing Agent 계약.
- `output/layout.svg` — 도면.
- 참고 최종본: `output/FINAL_layout_main.svg` (대표 동선) / `output/FINAL_layout_full.svg` (comb).
- 정렬 추적: `docs/alignment_audit.md` (룰엔진 출력이 도면에 어떻게 반영되는지 필드별).
