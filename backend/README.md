# BioForge CD Studio — Backend (FastAPI)

URS 업로드 → Rule Engine → Validation(RAG) 파이프라인을 웹 서비스로 래핑한다.
프런트엔드(`index.html`)도 이 서버가 같은 포트에서 서빙하므로 별도 정적 서버가 필요 없다.

## 로컬 사이트 실행

```bash
# 레포 루트에서
pip install -r requirements.txt           # rule_engine / rag_interface 의존성
pip install -r backend/requirements.txt   # fastapi / uvicorn / python-multipart
python -m uvicorn backend.app:app --reload --port 8100
```

또는 OS에 맞는 실행 파일을 사용한다.

```bash
# macOS/Linux
./backend/run_backend.sh
```

Windows에서는 `backend/run_backend.bat`를 더블클릭하거나 터미널에서 실행한다.

서버 실행 후 브라우저에서 아래 주소를 연다.

```text
http://localhost:8100/
```

서버 터미널은 계속 열어 둔다. 터미널을 닫으면 백엔드도 종료된다.

### 사이트에서 도면 생성하기

1. 상단 상태가 `백엔드 연결됨 (LIVE)`인지 확인한다.
2. `예시 데이터로 채우기`를 누르면 서버의 `input_urs/URS_ConceptualDesign for layout_0607-1.xlsx`로 실제 파이프라인이 실행된다.
3. 직접 테스트하려면 URS `.xlsx` 파일을 업로드한다.
4. `파이프라인 실행`을 누른다.
5. 실행이 완료되면 `도면 (Drawing Agent)` 영역에 SVG 도면이 자동 렌더링된다.
6. 필요하면 `미리보기` 또는 `도면 다운로드`를 누른다.

`index.html` 파일을 브라우저에서 직접 열기보다 반드시 `http://localhost:8100/`로 접속한다. 직접 파일을 열면 브라우저 환경에 따라 백엔드 탐지가 실패할 수 있다.

### 자주 막히는 경우

- 화면이 계속 `DEMO` 또는 `백엔드 미연결`이면 서버가 켜져 있는지 확인한다: `http://localhost:8100/health`
- Safari/Chrome이 예전 JS를 캐시하면 `Cmd + Shift + R`로 강력 새로고침한다.
- 도면 XML 오류가 보이면 기존 run URL 캐시일 수 있으니 메인 화면에서 새로 실행한다. `/runs/{id}/drawing` 응답은 `Cache-Control: no-store`로 제공된다.
- `예시 데이터로 채우기`도 실제 `/runs/sample`을 호출하므로, 도면이 안 뜨면 백엔드 로그와 `/health`를 먼저 확인한다.

## 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/` | 프런트엔드(index.html) 서빙 |
| `GET` | `/health` | 상태 + 검증/Doc Agent 연결 여부 |
| `POST` | `/runs` | URS 업로드(multipart `file`) + 옵션 → `run_id`. 옵션: `exclude_airlock_rooms`, `bio_isolation`, `run_validation` |
| `POST` | `/runs/sample` | 서버 내 예시 URS(`input_urs/URS_ConceptualDesign for layout_0607-1.xlsx`)로 실제 파이프라인 실행 |
| `GET` | `/runs/{id}` | 진행 상태(queued→parsing→ruling→validating→done) + 단계별 로그 + stats |
| `GET` | `/runs/{id}/output` | 7블록 JSON (Rule Engine 출력) |
| `GET` | `/runs/{id}/validation` | 검증 verdict (confirmed/review/false + RAG 인용) |
| `GET` | `/runs/{id}/drawing` | 내부 Drawing Agent가 생성한 SVG 도면 반환 |

실행은 백그라운드 스레드에서 비동기로 진행되며, 프런트가 `/runs/{id}` 를 폴링해 진행 단계를 표시한다.

## Documentation Agent 연결 지점

`backend/doc_agent.py` 의 `DocumentationAgentPort` 가 연결 계약(7블록 JSON → 도면 bytes)이다.
기본값은 `DOC_AGENT_MODE=internal` 이며 repo 내부 `src.drawing_agent` 를 직접 호출해
`/runs/{id}/drawing` 에서 SVG를 반환한다.
외부 팀 모듈 수령 시 `DOC_AGENT_MODE=python|http|cli` 로 바꾸면 같은 endpoint를 외부
Doc Agent로 교체할 수 있다.

## 메모

- v0.1 은 in-memory run 저장소(단일 프로세스). 다중 워커/영속화는 M5 과제.
- RAG DB(`RAG_DB_build/data/`)가 없으면 검증을 자동으로 건너뛰고 Rule Engine 결과만 반환한다.
