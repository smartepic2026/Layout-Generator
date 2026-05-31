"""작은 pytest 호환 runner — 외부 pytest 없이 우리 테스트를 돌리는 임시 도구.

향후 환경에서 pytest 설치가 가능해지면 본 파일은 더 이상 사용되지 않고,
표준 `pytest rule_engine/tests/` 명령으로 동일한 테스트가 그대로 동작한다.
이 파일은 pytest API의 극히 일부만 emulate한다.

지원:
    - @pytest.fixture (인자 없는 형태만)
    - @pytest.mark.parametrize(arg_names, arg_values)
    - 함수 이름이 test_로 시작하는 테스트 자동 발견
    - 함수 시그니처 파라미터 = fixture 이름이면 자동 주입

지원하지 않음:
    - fixture scope, autouse, indirect parametrize, hooks 등 pytest 고급 기능.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
import traceback
import types
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------------------
# pytest shim — sys.modules에 가짜 pytest를 미리 등록한다.
# ---------------------------------------------------------------------------

_pytest = types.ModuleType("pytest")


def _fixture(fn: Callable | None = None, /, *args, **kwargs):
    """@pytest.fixture (인자 유무 모두) — 식별을 위해 _is_fixture 마킹만."""
    def _wrap(f):
        f._is_fixture = True  # type: ignore[attr-defined]
        return f
    if fn is not None and callable(fn):
        return _wrap(fn)
    return _wrap


class _Mark:
    @staticmethod
    def parametrize(arg_names: str, arg_values: list):
        def decorator(fn):
            existing = getattr(fn, "_parametrize", [])
            existing = list(existing)
            existing.append((arg_names, arg_values))
            fn._parametrize = existing  # type: ignore[attr-defined]
            return fn
        return decorator


_pytest.fixture = _fixture
_pytest.mark = _Mark()
sys.modules["pytest"] = _pytest


# ---------------------------------------------------------------------------
# Runner 본체
# ---------------------------------------------------------------------------

def _collect_fixtures(conftest_module) -> dict[str, Callable]:
    """conftest 모듈에서 fixture 데코레이터가 붙은 함수만 수집."""
    return {
        name: fn
        for name, fn in inspect.getmembers(conftest_module, callable)
        if getattr(fn, "_is_fixture", False)
    }


def _resolve_fixture(name: str, fixtures: dict[str, Callable], cache: dict) -> Any:
    """fixture를 lazy 평가하여 값을 캐시한다."""
    if name in cache:
        return cache[name]
    fn = fixtures.get(name)
    if fn is None:
        raise NameError(f"fixture '{name}' 를 찾을 수 없음")
    sig = inspect.signature(fn)
    kwargs = {
        p: _resolve_fixture(p, fixtures, cache) for p in sig.parameters
    }
    value = fn(**kwargs)
    cache[name] = value
    return value


def _expand_parametrize(
    fn: Callable,
) -> list[tuple[str, dict]]:
    """parametrize 메타데이터를 (label, kwargs-overrides) 리스트로 풀어낸다.

    여러 개 누적된 경우는 cartesian product를 한다 (pytest 동작과 동일).
    """
    params = getattr(fn, "_parametrize", None)
    if not params:
        return [("", {})]
    # 누적된 parametrize들을 cartesian 곱.
    cases: list[tuple[str, dict]] = [("", {})]
    for arg_names_str, arg_values in params:
        names = [n.strip() for n in arg_names_str.split(",")]
        new_cases: list[tuple[str, dict]] = []
        for label, base in cases:
            for values in arg_values:
                if not isinstance(values, tuple):
                    values = (values,)
                overrides = dict(base)
                for k, v in zip(names, values):
                    overrides[k] = v
                # 라벨 합성
                value_label = "-".join(repr(v) for v in values)
                composite = f"{label}[{value_label}]" if label else f"[{value_label}]"
                new_cases.append((composite, overrides))
        cases = new_cases
    return cases


def _run_test(
    fn: Callable,
    fixtures: dict[str, Callable],
) -> list[tuple[str, bool, str]]:
    """단일 테스트 함수를 (parametrize 포함) 실행하고 결과 리스트 반환."""
    results: list[tuple[str, bool, str]] = []
    sig = inspect.signature(fn)
    param_names = list(sig.parameters)
    for case_label, overrides in _expand_parametrize(fn):
        cache: dict = dict(overrides)  # parametrize 값을 fixture cache에 미리 주입
        try:
            kwargs = {p: _resolve_fixture(p, fixtures, cache) for p in param_names}
            fn(**kwargs)
            results.append((case_label, True, ""))
        except Exception:
            results.append((case_label, False, traceback.format_exc(limit=4)))
    return results


def discover_and_run(tests_pkg: str = "rule_engine.tests") -> int:
    """tests 패키지 아래의 모든 test_*.py를 찾아 실행. 0=all pass."""
    # conftest 먼저 import 해서 fixture 수집.
    conftest = importlib.import_module(f"{tests_pkg}.conftest")
    fixtures = _collect_fixtures(conftest)

    # tests 하위 모듈 순회.
    pkg = importlib.import_module(tests_pkg)
    pkg_path = Path(pkg.__file__).parent if pkg.__file__ else None
    if pkg_path is None:
        print("ERROR: tests 패키지 경로를 찾을 수 없음")
        return 2

    total = passed = failed = 0
    failures: list[tuple[str, str]] = []

    for module_info in pkgutil.walk_packages([str(pkg_path)], prefix=f"{tests_pkg}."):
        name = module_info.name
        if "conftest" in name or name.endswith("_minirunner"):
            continue
        leaf = name.rsplit(".", 1)[-1]
        if not leaf.startswith("test_"):
            continue
        try:
            mod = importlib.import_module(name)
        except Exception:
            print(f"  IMPORT FAIL  {name}")
            print(traceback.format_exc(limit=3))
            failed += 1
            continue
        for fn_name, fn in inspect.getmembers(mod, inspect.isfunction):
            if not fn_name.startswith("test_"):
                continue
            for case_label, ok, tb in _run_test(fn, fixtures):
                total += 1
                full = f"{name}::{fn_name}{case_label}"
                if ok:
                    passed += 1
                    print(f"  PASS  {full}")
                else:
                    failed += 1
                    print(f"  FAIL  {full}")
                    failures.append((full, tb))

    print("=" * 70)
    print(f"  total={total}  passed={passed}  failed={failed}")
    if failures:
        print("\n=== Failure details ===")
        for name, tb in failures:
            print(f"\n--- {name} ---\n{tb}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(discover_and_run())
