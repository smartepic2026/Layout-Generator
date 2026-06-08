# Documentation Agent 연결 가이드

외부 팀의 Doc Agent(7블록 JSON → **SVG 도면**)를 백엔드에 연결하는 방법.
연결 지점은 `backend/doc_agent.py` 하나이며, **환경변수 `DOC_AGENT_MODE`** 로 전환한다.
코드 수정 없이 스위치만 바꾸면 `/runs/{id}/drawing` 이 503(미연결)에서 실제 SVG 반환으로 바뀐다.

```
URS → RuleEngine → 7블록 JSON ──▶ DocumentationAgentPort.generate(json) ──▶ SVG bytes
                                   (doc_agent.py · 어댑터가 외부 모듈 호출)
```

## 입출력 계약 (외부 팀과 확정)
- 입력: 7블록 JSON dict — `rule_engine/output_schema.md` / `output_example.json`
- 출력: **SVG** (좌표 단위 mm). PDF/DXF 로 바꾸면 `DRAWING_FORMAT` 환경변수로 변경.

## 모드 전환

| DOC_AGENT_MODE | 의미 | 추가 환경변수 |
|---|---|---|
| `none` (기본) | 미연결 — 503, 프런트는 placeholder | — |
| `python` | (a) 같은 파이썬 런타임에서 import | `DOC_AGENT_MODULE`, `DOC_AGENT_FUNC`(기본 render) |
| `http` | (b) 별도 HTTP 서비스 호출 | `DOC_AGENT_URL`, `DOC_AGENT_TIMEOUT` |
| `cli` | (c) 실행파일/CLI + 파일 교환 | `DOC_AGENT_CMD` |

### (a) 파이썬 모듈로 받은 경우
외부 함수 시그니처(협의): `render(output_json: dict) -> bytes | str(SVG)`

Windows(cmd) 예:
```
set DOC_AGENT_MODE=python
set DOC_AGENT_MODULE=their_doc_agent
set DOC_AGENT_FUNC=render
python -m uvicorn backend.app:app --port 8000
```
모듈이 import 경로에 있어야 한다(레포 루트에 두거나 `pip install`).

### (b) HTTP 서비스로 받은 경우
규약(협의): `POST {DOC_AGENT_URL}` body=7블록 JSON → 200, body=SVG bytes
```
set DOC_AGENT_MODE=http
set DOC_AGENT_URL=http://localhost:9000/render
python -m uvicorn backend.app:app --port 8000
```

### (c) 실행파일/CLI로 받은 경우
규약(협의): `{DOC_AGENT_CMD} <input.json> <output.svg>` 실행 → output.svg 생성
```
set DOC_AGENT_MODE=cli
set DOC_AGENT_CMD=C:\doc_agent\doc_agent.exe
python -m uvicorn backend.app:app --port 8000
```
(파이썬 스크립트면 `set DOC_AGENT_CMD=python C:\doc_agent\main.py`)

## 확인
1. 서버 기동 후 `http://localhost:8000/health` 에서
   `"doc_agent_connected": true`, `"doc_agent_mode": "python|http|cli"` 확인.
   초기화 실패 시 `"doc_agent_error"` 에 원인이 찍힌다(미연결 유지).
2. 프런트엔드 도면 카드의 상태 표시가 빨강 "미연결" → 파랑 "연결됨"으로 바뀐다.
3. URS 실행 후 "미리보기/다운로드" 가 실제 SVG 를 가져온다.

## 어디를 바꿔 코딩으로 연결하나 (옵션)
환경변수가 아니라 코드로 고정하고 싶으면 `backend/doc_agent.py` 의 어댑터
`generate()` 본문(주석 처리된 import 부분)을 외부 모듈에 맞게 채우면 된다.
세 어댑터(`PythonImportDocAgent`/`HttpDocAgent`/`CliDocAgent`)가 이미 준비돼 있다.
