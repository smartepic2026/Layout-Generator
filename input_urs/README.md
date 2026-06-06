# 📥 여기에 본인 URS 엑셀을 넣으세요

이 폴더는 **본인의 URS(.xlsx)** 를 넣는 전용 입력 폴더입니다.
여기에 파일을 두고 아래 두 명령만 실행하면 GMP 평면도(SVG)가 만들어집니다.

> 전체 흐름:  **내 URS(.xlsx) → ① Rule Engine → spec.json → ② Drawing Agent → 도면(.svg)**

---

## 1. URS 엑셀 준비

- 이 폴더 안에 있는 **`예제_URS_템플릿.xlsx`** 를 복사해서 값만 바꾸는 것을 추천합니다.
  (시트명·열 위치가 그대로라 바로 인식됩니다.)
- 완성한 파일을 **이 `input_urs/` 폴더 안에** 두세요. 예: `input_urs/내URS.xlsx`

> ⚠️ 파일명에 공백·한글이 있으면 명령에서 따옴표로 감싸세요 → `"input_urs/내 URS.xlsx"`

---

## 2. 실행 (레포 폴더 `Layout-Generator` 안에서)

```bash
# ① URS 엑셀 → spec.json  (룰엔진)
python3 -m src.cli rule-engine  "input_urs/내URS.xlsx"  output/spec.json

# ② spec.json → 도면.svg  (드로잉 에이전트)
python3 -m src.cli draw  output/spec.json  output/내도면.svg
```

- 결과 도면은 `output/내도면.svg` 로 나옵니다 (브라우저로 열면 보임).
- 더 자세한 옵션·에러 해결표는 **`docs/USAGE.md`** 참고.

---

## 메모

- 이 폴더의 `예제_URS_템플릿.xlsx` 는 지우지 마세요(형식 기준).
- 시트명·열 위치가 다른 URS라면 `src/rule_engine/urs_parser.py` 상단 상수에서 맞출 수 있습니다.
