"""Documentation Agent 연결 레이어 (Doc Agent Port + 어댑터 3종).

Documentation Agent(7블록 JSON → 도면) 를 백엔드에 꽂는 단일 지점.
기본값은 이 repo 의 `src.drawing_agent` 를 직접 호출하는 internal adapter 이다.
외부 팀 모듈을 받으면 환경변수로 python/http/cli adapter 로 교체할 수 있다.

연결 방법은 **환경변수 DOC_AGENT_MODE 한 줄**로 전환한다 (코드 수정 불필요):

    DOC_AGENT_MODE=internal (기본) — repo 내 drawing_agent 직접 호출
    DOC_AGENT_MODE=none     — 미연결, 503
    DOC_AGENT_MODE=python  — (a) 같은 파이썬 런타임에서 import
    DOC_AGENT_MODE=http    — (b) 별도 HTTP 서비스 호출
    DOC_AGENT_MODE=cli     — (c) 실행파일/CLI + 파일 교환

각 모드별 추가 환경변수는 아래 어댑터 docstring 참고.
출력 포맷은 SVG 로 고정(협의 결과). 외부 팀이 PDF/DXF 로 바꾸면
DRAWING_FORMAT / MEDIA_TYPE 환경변수로 덮어쓸 수 있다.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
from typing import Optional


class DocAgentNotConnected(RuntimeError):
    """Documentation Agent 가 아직 연결되지 않았음을 알리는 예외."""


# 협의된 기본 출력 포맷 — SVG.
DRAWING_FORMAT = os.environ.get("DRAWING_FORMAT", "svg")
MEDIA_TYPE = os.environ.get("MEDIA_TYPE", {
    "svg": "image/svg+xml", "pdf": "application/pdf", "dxf": "image/vnd.dxf",
}.get(DRAWING_FORMAT, "application/octet-stream"))


class DocumentationAgentPort:
    """7블록 출력 → 도면 bytes 변환 계약.

    입력 계약: rule_engine/output_schema.md / output_example.json (7블록 JSON dict)
    출력 계약: 도면 bytes (기본 SVG) — drawing_format / media_type 로 표기.
    """

    drawing_format: str = DRAWING_FORMAT
    media_type: str = MEDIA_TYPE

    def generate(self, output_json: dict) -> bytes:
        raise NotImplementedError

    @staticmethod
    def _as_bytes(result) -> bytes:
        """어댑터 결과를 bytes 로 정규화 (str·bytes·path 모두 허용)."""
        if isinstance(result, (bytes, bytearray)):
            return bytes(result)
        if isinstance(result, (str, os.PathLike)):
            p = pathlib.Path(result)
            if p.exists():                       # 경로면 파일을 읽는다
                return p.read_bytes()
            return str(result).encode("utf-8")   # SVG 문자열이면 인코딩
        raise TypeError(f"Doc Agent 결과 타입을 도면 bytes 로 변환 불가: {type(result)}")


# ===========================================================================
# (a) 파이썬 import 어댑터 — 같은 런타임에서 외부 모듈 호출
# ===========================================================================
class PythonImportDocAgent(DocumentationAgentPort):
    """외부 Doc Agent 가 파이썬 패키지로 제공될 때.

    환경변수:
        DOC_AGENT_MODULE  (기본 "doc_agent")   — import 할 모듈명
        DOC_AGENT_FUNC    (기본 "render")      — 7블록 dict 를 받아 SVG(str|bytes) 반환하는 함수

    외부 팀 함수 시그니처(협의): render(output_json: dict) -> bytes | str(SVG)
    """

    def __init__(self) -> None:
        import importlib
        module_name = os.environ.get("DOC_AGENT_MODULE", "doc_agent")
        func_name = os.environ.get("DOC_AGENT_FUNC", "render")
        module = importlib.import_module(module_name)
        self._render = getattr(module, func_name)

    def generate(self, output_json: dict) -> bytes:
        return self._as_bytes(self._render(output_json))


# ===========================================================================
# (b) HTTP 서비스 어댑터 — 별도 프로세스/서버로 제공
# ===========================================================================
class HttpDocAgent(DocumentationAgentPort):
    """외부 Doc Agent 가 별도 HTTP 서비스로 제공될 때.

    환경변수:
        DOC_AGENT_URL      (기본 "http://localhost:9000/render")
        DOC_AGENT_TIMEOUT  (기본 "180" 초)

    호출 규약(협의): POST {url}  body=7블록 JSON  →  200, body=도면 bytes(SVG)
    """

    def __init__(self) -> None:
        self.url = os.environ.get("DOC_AGENT_URL", "http://localhost:9000/render")
        self.timeout = float(os.environ.get("DOC_AGENT_TIMEOUT", "180"))

    def generate(self, output_json: dict) -> bytes:
        import httpx  # backend/requirements.txt 에 이미 포함
        r = httpx.post(self.url, json=output_json, timeout=self.timeout)
        r.raise_for_status()
        return r.content


# ===========================================================================
# (c) CLI / 실행파일 어댑터 — 파일 교환
# ===========================================================================
class CliDocAgent(DocumentationAgentPort):
    """외부 Doc Agent 가 실행파일/CLI 로 제공될 때 (입력 JSON → 출력 SVG 파일).

    환경변수:
        DOC_AGENT_CMD  (기본 "doc_agent")  — 실행 명령(공백 분리 인자 허용)

    호출 규약(협의): {CMD} <input.json> <output.svg>  실행 후 output.svg 생성.
    예) DOC_AGENT_CMD="python C:/doc_agent/main.py"
        DOC_AGENT_CMD="C:/doc_agent/doc_agent.exe"
    """

    def __init__(self) -> None:
        self.cmd = os.environ.get("DOC_AGENT_CMD", "doc_agent")

    def generate(self, output_json: dict) -> bytes:
        workdir = pathlib.Path(tempfile.mkdtemp(prefix="docagent_"))
        in_path = workdir / "input.json"
        out_path = workdir / f"drawing.{self.drawing_format}"
        in_path.write_text(json.dumps(output_json, ensure_ascii=False), encoding="utf-8")
        subprocess.run(
            self.cmd.split() + [str(in_path), str(out_path)],
            check=True, capture_output=True,
        )
        if not out_path.exists():
            raise DocAgentNotConnected(
                f"Doc Agent CLI 가 출력 파일을 만들지 않았습니다: {out_path}")
        return out_path.read_bytes()


# ===========================================================================
# (d) Internal adapter — 이 repo 의 drawing_agent 직접 호출
# ===========================================================================
class InternalDrawingAgent(DocumentationAgentPort):
    """현재 repo 의 Drawing Agent 를 FastAPI backend 에 직접 연결한다.

    입력은 팀원 Rule Engine 7블록 dict 이므로 anti-corruption adapter 를 거쳐
    `src.contract.schemas.RuleEngineOutput` 으로 변환한 뒤 SVG 를 생성한다.

    환경변수:
        DOC_AGENT_FLOW_MODE      (기본 "full") — full/main/off
        DOC_AGENT_VARIANT_SEED   (기본 "42")
        DOC_AGENT_VARIANT_INDEX  (기본 "0")
    """

    def __init__(self) -> None:
        self.flow_mode = os.environ.get("DOC_AGENT_FLOW_MODE", "full")
        self.variant_seed = int(os.environ.get("DOC_AGENT_VARIANT_SEED", "42"))
        self.variant_index = int(os.environ.get("DOC_AGENT_VARIANT_INDEX", "0"))

    def generate(self, output_json: dict) -> bytes:
        from src.contract.schemas import RuleEngineOutput
        from src.drawing_agent.data.tier1_ruleengine import adapt_external_dict
        from src.drawing_agent.floorplan import generate_floorplan

        spec = RuleEngineOutput.model_validate(adapt_external_dict(output_json))
        svg, _layout = generate_floorplan(
            spec,
            dynamic_rooms=True,
            flow_mode=self.flow_mode,
            variant_seed=self.variant_seed,
            variant_index=self.variant_index,
        )
        return svg.encode("utf-8")


# ===========================================================================
# 팩토리 — DOC_AGENT_MODE 로 어댑터 선택
# ===========================================================================
_ADAPTERS = {
    "internal": InternalDrawingAgent,
    "python": PythonImportDocAgent,
    "http": HttpDocAgent,
    "cli": CliDocAgent,
}


def get_doc_agent() -> Optional[DocumentationAgentPort]:
    """현재 환경에 맞는 어댑터 인스턴스(또는 미연결 시 None).

    DOC_AGENT_MODE 가 internal/빈값이면 repo 내 drawing_agent 를 연결한다.
    none/off/stub 이면 None(미연결).
    설정돼 있으나 초기화 실패(모듈 없음 등)면 예외를 그대로 올려 시작 시 알린다.
    """
    mode = os.environ.get("DOC_AGENT_MODE", "internal").strip().lower()
    if mode in ("none", "off", "stub"):
        return None
    if mode == "":
        mode = "internal"
    if mode not in _ADAPTERS:
        raise ValueError(
            f"알 수 없는 DOC_AGENT_MODE={mode!r} — internal/none/python/http/cli 중 하나여야 함")
    return _ADAPTERS[mode]()


def current_mode() -> str:
    return os.environ.get("DOC_AGENT_MODE", "internal").strip().lower() or "internal"
