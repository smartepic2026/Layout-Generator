# BioForge CD Studio — Backend (FastAPI)

URS 업로드 → Rule Engine → Validation(RAG) 파이프라인을 웹 서비스로 래핑한다.
프런트엔드(`index.html`)도 이 서버가 같은 포트에서 서빙하므로 별도 정적 서버가 필요 없다.

## 실행

```bash
# 레포 루트에서
pip install -r requirements.txt           # rule_engine / rag_interface 의존성
pip install -r backend/requirements.txt   # fastapi / uvicorn / python-multipart
python -m uvicorn backend.app:app --reload --port 8100
```

또는 `backend/run_backend.bat`(Windows) · `backend/run_backend.sh`(mac/Linux) 더블클릭/실행.

브라우저에서 **http://localhost:8100** 접속 → 프런트엔드가 열리고 자동으로 "백엔드 연결됨(LIVE)" 상태가 된다.
서버를 켜지 않고 `index.html` 을 그냥 열면 내장 예시 결과로 동작하는 **데모 모드**로 떨어진다.

## 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/` | 프런트엔드(index.html) 서빙 |
| `GET` | `/health` | 상태 + 검증/Doc Agent 연결 여부 |
| `POST` | `/runs` | URS 업로드(multipart `file`) + 옵션 → `run_id`. 옵션: `exclude_airlock_rooms`, `bio_isolation`, `run_validation` |
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
