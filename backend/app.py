"""BioForge CD Studio — Backend API (FastAPI).

실제 파이프라인을 웹 서비스로 래핑한다:
    URS(xlsx) 업로드 → load_urs_as_input → run_rule_engine → run_with_validation_loop
    → 7블록 JSON + 검증 verdict 를 프런트엔드에 제공.

Documentation Agent(도면 생성) 연결은 backend/doc_agent.py 가 담당한다.
기본 DOC_AGENT_MODE=internal 로 repo 내 Drawing Agent 를 직접 호출한다.
외부 팀 Doc Agent 로 바꾸려면 none/python/http/cli 모드로 전환한다.
자세한 연결법: backend/DOC_AGENT_CONNECT.md

실행:
    pip install -r backend/requirements.txt
    uvicorn backend.app:app --reload --port 8100
    → http://localhost:8100  (프런트엔드가 같은 서버에서 서빙됨)
"""
from __future__ import annotations

import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

# --- 프로젝트 루트(레포)를 import 경로에 추가 -------------------------------
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rule_engine import run_rule_engine                       # noqa: E402
from rule_engine.urs_parser import load_urs_as_input          # noqa: E402
from rule_engine.models import FlowPolicy, Overrides          # noqa: E402

# 검증(RAG) 은 선택적으로만 import — DB 가 없는 환경에서도 룰 엔진은 동작하도록.
try:
    from rule_engine import run_with_validation_loop
    from rule_engine.validators.rag_validator import make_calibrated_rag_validator
    from rag_interface import search as _rag_search
    _VALIDATION_AVAILABLE = True
except Exception:                                             # pragma: no cover
    _VALIDATION_AVAILABLE = False

# --- Documentation Agent 연결 (backend/doc_agent.py) ------------------------
from backend.doc_agent import (                               # noqa: E402
    DocumentationAgentPort, current_mode, get_doc_agent,
)

_CONNECTED_DOC_AGENT: Optional[DocumentationAgentPort]
_DOC_AGENT_ERROR: Optional[str]
try:
    _CONNECTED_DOC_AGENT = get_doc_agent()
    _DOC_AGENT_ERROR = None
except Exception as e:                                        # 어댑터 초기화 실패
    _CONNECTED_DOC_AGENT = None
    _DOC_AGENT_ERROR = f"{type(e).__name__}: {e}"
    print(f"[doc_agent] 초기화 실패(미연결 유지): {_DOC_AGENT_ERROR}", file=sys.stderr)


# ===========================================================================
# Run 상태 저장소 (in-memory) — v0.1 동기/단일 프로세스용
# ===========================================================================
RUNS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()
UPLOAD_DIR = ROOT / "backend" / "_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_URS = ROOT / "input_urs" / "URS_ConceptualDesign for layout_0607-1.xlsx"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(run: dict, step: str, msg: str) -> None:
    run["log"].append({"t": _now(), "step": step, "msg": msg})


def _execute(run_id: str, xlsx_path: Path, exclude_airlock: bool,
             bio_isolation: bool, run_validation: bool) -> None:
    """백그라운드 스레드에서 파이프라인을 실행하며 상태를 갱신한다."""
    run = RUNS[run_id]
    try:
        run["status"] = "parsing"
        _log(run, "parse", f"URS 워크북 파싱: {xlsx_path.name}")
        kwargs: dict[str, Any] = {
            "overrides": Overrides(exclude_airlock_rooms=exclude_airlock),
        }
        if bio_isolation:
            kwargs["flow_policy"] = FlowPolicy(
                airlock_default_type="cascade",
                supply_return_corridor_separate=True,
                biological_safety_isolation=True,
            )
        inp = load_urs_as_input(xlsx_path, **kwargs)
        _log(run, "parse",
             f"방 {len(inp.urs_rooms)}개 · 장비 {len(inp.urs_equipment)}개 인식")

        run["status"] = "ruling"
        _log(run, "rule", "15개 GMP 룰 + derive 적용")
        out = run_rule_engine(inp)
        import json as _json
        run["output"] = _json.loads(out.to_json())
        st = out.meta["stats"]
        _log(run, "rule",
             f"7블록 산출: 방 {st['rooms']} / 전실 {st['airlocks']} / "
             f"인접 {st['adjacency_edges']} / rationale {st['rationale_entries']}")

        if run_validation and _VALIDATION_AVAILABLE:
            run["status"] = "validating"
            _log(run, "valid", "RAG 검증: 규제 DB 대조")
            validator = make_calibrated_rag_validator(rag_search=_rag_search)
            res = run_with_validation_loop(
                input_spec=inp, validator=validator,
                output_dir=str(UPLOAD_DIR / run_id), max_retries=1,
            )
            run["validation"] = res.final_verdict.to_json()
            v = res.final_verdict
            import collections
            c = collections.Counter(a.verdict for a in v.acknowledged_flags)
            _log(run, "valid",
                 f"verdict={v.status} · 확정 {c.get('confirmed_violation',0)} / "
                 f"검토 {c.get('needs_user_review',0)} / 오탐 {c.get('false_alarm',0)}")
        else:
            run["validation"] = None
            _log(run, "valid", "검증 건너뜀 (옵션 off 또는 RAG DB 미설치)")

        run["drawing_available"] = _CONNECTED_DOC_AGENT is not None
        _log(run, "doc",
             f"Drawing Agent 연결됨 (mode={current_mode()})"
             if run["drawing_available"] else "Drawing Agent 미연결 — DOC_AGENT_MODE 설정 필요")

        run["status"] = "done"
        run["finished_at"] = _now()
    except Exception as e:                                    # pragma: no cover
        run["status"] = "error"
        run["error"] = f"{type(e).__name__}: {e}"
        run["traceback"] = traceback.format_exc()
        _log(run, "error", run["error"])


# ===========================================================================
# FastAPI app
# ===========================================================================
app = FastAPI(title="BioForge CD Studio API", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

FRONTEND = ROOT / "index.html"


@app.get("/")
def index() -> Response:
    if FRONTEND.exists():
        return FileResponse(str(FRONTEND), headers={"Cache-Control": "no-store"})
    return JSONResponse({"service": "BioForge CD Studio API", "see": "/docs"})


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "validation_available": _VALIDATION_AVAILABLE,
        "doc_agent_connected": _CONNECTED_DOC_AGENT is not None,
        "doc_agent_mode": current_mode(),
        "doc_agent_format": getattr(_CONNECTED_DOC_AGENT, "drawing_format", "svg"),
        "doc_agent_error": _DOC_AGENT_ERROR,
        "active_runs": len(RUNS),
    }


@app.post("/runs")
async def create_run(
    file: UploadFile = File(...),
    exclude_airlock_rooms: bool = Form(False),
    bio_isolation: bool = Form(False),
    run_validation: bool = Form(True),
) -> dict:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "URS 엑셀(.xlsx/.xls) 파일을 업로드하세요.")
    run_id = uuid.uuid4().hex[:12]
    dest = UPLOAD_DIR / f"{run_id}_{file.filename}"
    dest.write_bytes(await file.read())
    return _start_run(
        run_id, dest, file.filename, exclude_airlock_rooms, bio_isolation, run_validation,
    )


@app.post("/runs/sample")
async def create_sample_run(
    exclude_airlock_rooms: bool = Form(False),
    bio_isolation: bool = Form(False),
    run_validation: bool = Form(True),
) -> dict:
    if not SAMPLE_URS.exists():
        raise HTTPException(404, f"sample URS not found: {SAMPLE_URS.name}")
    run_id = uuid.uuid4().hex[:12]
    dest = UPLOAD_DIR / f"{run_id}_{SAMPLE_URS.name}"
    dest.write_bytes(SAMPLE_URS.read_bytes())
    return _start_run(
        run_id, dest, SAMPLE_URS.name, exclude_airlock_rooms, bio_isolation, run_validation,
    )


def _start_run(
    run_id: str,
    xlsx_path: Path,
    filename: str,
    exclude_airlock_rooms: bool,
    bio_isolation: bool,
    run_validation: bool,
) -> dict:
    with _LOCK:
        RUNS[run_id] = {
            "run_id": run_id, "status": "queued", "filename": filename,
            "created_at": _now(), "finished_at": None, "log": [],
            "output": None, "validation": None, "drawing_available": False,
            "options": {
                "exclude_airlock_rooms": exclude_airlock_rooms,
                "bio_isolation": bio_isolation,
                "run_validation": run_validation,
            },
        }
    t = threading.Thread(
        target=_execute,
        args=(run_id, xlsx_path, exclude_airlock_rooms, bio_isolation, run_validation),
        daemon=True,
    )
    t.start()
    return {"run_id": run_id, "status": "queued"}


def _get(run_id: str) -> dict:
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, f"run not found: {run_id}")
    return run


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = _get(run_id)
    stats = (run["output"] or {}).get("meta", {}).get("stats") if run["output"] else None
    return {
        "run_id": run_id, "status": run["status"], "filename": run["filename"],
        "options": run["options"], "log": run["log"], "stats": stats,
        "drawing_available": run["drawing_available"],
        "has_validation": run["validation"] is not None,
        "error": run.get("error"),
    }


@app.get("/runs/{run_id}/output")
def get_output(run_id: str) -> Any:
    run = _get(run_id)
    if run["output"] is None:
        raise HTTPException(409, f"output not ready (status={run['status']})")
    return run["output"]


@app.get("/runs/{run_id}/validation")
def get_validation(run_id: str) -> Response:
    run = _get(run_id)
    if run["validation"] is None:
        raise HTTPException(409, f"validation not available (status={run['status']})")
    return Response(content=run["validation"], media_type="application/json")


@app.get("/runs/{run_id}/drawing")
def get_drawing(run_id: str) -> Response:
    """도면 반환. Drawing Agent 연결 시 실제 SVG, 미연결 시 503."""
    run = _get(run_id)
    if run["output"] is None:
        raise HTTPException(409, "먼저 파이프라인을 실행해 7블록 사양을 산출하세요.")
    if _CONNECTED_DOC_AGENT is None:
        detail = "Drawing Agent 미연결 — DOC_AGENT_MODE=internal 또는 외부 adapter 설정이 필요합니다."
        if _DOC_AGENT_ERROR:
            detail += f" (초기화 오류: {_DOC_AGENT_ERROR})"
        raise HTTPException(503, detail)
    try:
        drawing = _CONNECTED_DOC_AGENT.generate(run["output"])
    except Exception as e:                                    # 외부 모듈 실행 오류
        raise HTTPException(502, f"Doc Agent 도면 생성 실패: {type(e).__name__}: {e}")
    return Response(
        content=drawing,
        media_type=_CONNECTED_DOC_AGENT.media_type,
        headers={"Cache-Control": "no-store"},
    )
