# 📘 사용 설명서 — 내 URS 엑셀로 GMP 도면 만들기

> 이 문서 하나만 따라 하면 **본인 URS(엑셀)** 를 넣어 **GMP 평면도(SVG)** 를
> 만들 수 있습니다. 개발 경험이 없어도 복사·붙여넣기만 하면 됩니다.
>
> 전체 흐름:  **내 URS(.xlsx)  →  ① Rule Engine  →  spec.json  →  ② Drawing Agent  →  도면(.svg)**

---

## ⚡ 한눈에 (이미 익숙하신 분용)

```bash
# 레포 폴더 안에서 실행
python3 -m src.cli rule-engine  input_urs/내URS.xlsx  output/spec.json
python3 -m src.cli draw  output/spec.json  output/layout.svg  --flows main
# → output/layout.svg 를 브라우저로 열기
```

처음이시면 아래를 순서대로 따라오세요. 👇

---

## 1. 준비 (최초 한 번)

### 1-1. 레포 내려받기
```bash
git clone https://github.com/smartepic2026/Layout-Generator.git
cd Layout-Generator
git checkout drawing/floorplan-v2        # ← 최신 도면 브랜치 (꼭 체크아웃)
```

### 1-2. 파이썬 패키지 설치
```bash
python3 -m venv .venv && source .venv/bin/activate   # 가상환경 (권장, 윈도우는 .venv\Scripts\activate)
pip install -r requirements.txt
```
- **Python 3.10 이상** 필요 (3.13까지 확인).
- 엑셀을 읽는 `openpyxl`, 솔버 `ortools` 등이 자동 설치됩니다.

> 💡 이후 새 터미널을 열 때마다 `cd Layout-Generator` + `source .venv/bin/activate`
> 두 줄만 해주면 바로 쓸 수 있습니다.

### 1-3. 나중에 업데이트 받기 (중요)
이 코드는 계속 갱신됩니다. **클론은 받은 그 순간의 스냅샷**이라, 이후 바뀐 내용은
자동으로 들어오지 않습니다. 최신을 받으려면 **`git pull`** 을 직접 해야 합니다.

```bash
cd Layout-Generator
git checkout drawing/floorplan-v2   # 같은 브랜치에 있어야 함
git pull                            # 최신 코드·도면·문서 받기
```

> ⚠️ **본인이 직접 수정한 파일이 있으면** `git pull` 시 충돌(conflict)이 날 수 있습니다.
> 받아서 **실행·확인만** 한다면 충돌 걱정이 없습니다. 직접 고칠 일이 생기면 먼저 알려주세요.
>
> 💡 `git pull` 했는데 패키지 에러가 나면, 의존성이 바뀐 것일 수 있으니
> `pip install -r requirements.txt` 를 한 번 더 실행하세요.

---

## 2. 내 URS 엑셀 준비

### 2-1. 엑셀 파일은 어디에 둬요?
레포 안에 **본인 URS 전용 입력 폴더 `input_urs/`** 를 만들어 뒀습니다. **여기에 넣으세요.**
이 폴더에는 안내문(`README.md`)과 복사해서 쓸 **`예제_URS_템플릿.xlsx`** 가 들어 있습니다.

| 어디에 뒀나 | 명령에 적는 경로 |
|---|---|
| 레포 안 `input_urs/` (추천) | `input_urs/내URS.xlsx` |
| 바탕화면 (맥) | `/Users/내계정/Desktop/내URS.xlsx` 또는 `~/Desktop/내URS.xlsx` |
| 바탕화면 (윈도우) | `C:\Users\내계정\Desktop\내URS.xlsx` |

> ⚠️ 파일명에 **공백·한글**이 있으면 따옴표로 감싸세요 → `"input_urs/내 URS.xlsx"`

### 2-2. 엑셀 양식 (중요)
가장 안전한 방법: **`input_urs/예제_URS_템플릿.xlsx` 를 복사해서 값만 바꾸기.**
시트 구조·시트명은 그대로 두세요. 필요한 시트는 **2개**:

| 시트명 (그대로 유지) | 들어가는 내용 |
|---|---|
| **`Room 요구 규격서`** | Room 목록(청정도·목표 ACH·면적 비율·갱의·출입동선) + **row 4 에 건축물 메타**(층수·제공 면적·가로×세로·인원/자재/폐기물 출입구 방향) |
| **`제조 장비 규격서`** | Room 별 장비(규격 W×D×H·중량·세부공정 No.) |

> 시트명·열 위치가 다르면 `src/rule_engine/urs_parser.py` 상단 상수에서 맞출 수
> 있지만, **예제 양식을 그대로 쓰는 게 가장 속 편합니다.**

---

## 3. 실행 — 명령 2개

> 두 명령 모두 **레포 폴더(`Layout-Generator`) 안에서** 실행해야 합니다.

### ① URS 엑셀 → spec.json  (룰엔진)
```bash
python3 -m src.cli rule-engine  input_urs/내URS.xlsx  output/spec.json
```
성공하면 이렇게 나옵니다 👇
```
[OK]  input_urs/내URS.xlsx → output/spec.json
      rooms=48, airlocks=18, adjacency=27, rationale=399
      zones: process=30, aux=12, NC=6
```

### ② spec.json → 도면 SVG  (드로잉)
```bash
python3 -m src.cli draw  output/spec.json  output/layout.svg  --flows main
```
성공하면 👇
```
[OK]  output/spec.json → output/layout.svg
      rooms placed: 32, airlocks: 18, doors: 37
```
> 여기서 **`[WARN] 배치 누락된 방 …`** 이 뜨면 4번(옵션)의 `--strip` 항목을 보세요.

### ③ 도면 열기
`output/layout.svg` 파일을 **더블클릭 → 브라우저(크롬 등)로 열기**. 끝!

---

## 4. 도면 옵션 (draw)

```bash
python3 -m src.cli draw output/spec.json output/layout.svg [옵션]
```

| 옵션 | 기본 | 뜻 |
|---|---|---|
| `--flows main` | `full` | **동선을 깔끔하게** (종류별 대표 1경로). 검토용 추천 |
| `--flows full` | | 공정실별 **전체 동선**(꼼꼼히 볼 때, 좀 복잡) |
| `--flows off` | | 동선 없이 방·전실만 |
| `--strip` | (꺼짐) | ⚠️ **켜지 마세요.** 옛날 방식이라 방이 누락됩니다 |
| `--width N` `--height N` | URS값 | 건물 가로/세로(mm) 강제 지정 |

브라우저에서 SVG를 열면 동선이 종류별 그룹으로 묶여 있어, 개발자도구로 켜고 끌 수도 있습니다.

---

## 5. 도면 읽는 법

- **좌 → 우 청정도 구배**: NC(회색) → Grade D 보조(파랑) → Grade C 공정(노랑).
- **방 라벨**: 영문명 / 한글 / `등급 · 차압 · 면적 · 환기횟수(ACH)` / `천정고 · 갱의`.
- **전실(에어록)**: 박스 안에 `PAL_in`, `MAL_out` 등 + `cascade`(공기 흐름 타입).
- **동선 4색**(우측 범례): 인원(남색) · 자재(청록) · 폐기물(빨강) · 제품(보라).
  제품 동선은 공정실 사이 **벽을 가로지름**(규정: CIP 배관으로 운반).
- **복도**: 가운데 공급복도, 위·아래 리턴복도, NC↔Grade D 순환 복도.

참고용 완성 예시: `output/FINAL_layout_main.svg` (깔끔) / `output/FINAL_layout_full.svg` (전체 동선).

---

## 6. 자주 나는 에러 & 해결

| 증상 | 원인 / 해결 |
|---|---|
| `draw` 가 `rationale.*.target` 같은 **Pydantic 오류로 크래시** | 룰엔진 원본을 draw에 바로 넣은 경우. **반드시 ① rule-engine 단계를 먼저** 거친 `output/spec.json` 을 draw에 넣으세요 |
| `[WARN] 배치 누락된 방 …` / 방이 일부 안 그려짐 | `--strip` 을 쓴 경우. **옵션을 빼면**(기본) 전 방이 그려집니다 |
| 엑셀 파싱 오류 / `KeyError` | 시트명이 `Room 요구 규격서` · `제조 장비 규격서` 인지, 건축물 메타가 Room 시트 **row 4** 에 있는지 확인 |
| `No module named src` | 명령을 **레포 폴더 안에서** 실행했는지 확인 (`cd Layout-Generator`) |
| `ModuleNotFoundError` (openpyxl 등) | `pip install -r requirements.txt` 를 했는지, 가상환경이 켜져 있는지 확인 |
| `python3` 명령이 없다(윈도우) | `python` 으로 바꿔서 실행 |

---

## 7. 산출물 & 더 보기

| 파일 | 내용 |
|---|---|
| `output/spec.json` | 룰엔진 7블록(rooms·airlocks·adjacency·flow_paths·zones·constraints·rationale). 외부 Drawing Agent 계약 |
| `output/layout.svg` | 만들어진 도면 |
| `output/FINAL_layout_main.svg` / `_full.svg` | 참고용 최종 도면(대표 / 전체 동선) |
| `docs/alignment_audit.md` | 룰엔진 출력이 도면에 **어떻게 반영되는지** 필드별 추적표 |
| `docs/PROGRESS.md` · `docs/decisions.md` | 진행 상황 · 설계 결정 로그 |

---

### 막히면?
콘솔에 뜬 **마지막 에러 메시지 몇 줄**과 **어떤 명령을 쳤는지**만 알려주시면
바로 짚어드릴 수 있습니다. (위 6번 표에 대부분 답이 있습니다.)
