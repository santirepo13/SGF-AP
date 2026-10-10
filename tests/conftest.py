"""Runtime trace collector used by tests/coverage.py.

The collector records real test locals and SQL-like execute calls without
writing credentials, hashes, passwords, or connection strings.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import pytest

from tests.support.postgres import workflow_database  # noqa: F401; shared pytest fixture
from tests.ticket_workflow.measurement import WorkflowMeasurement

_ACTIVE: dict[str, Any] | None = None
_RESULTS: dict[str, dict[str, Any]] = {}
_MEASUREMENT = WorkflowMeasurement()


def _safe(value: Any) -> str:
    text = repr(value)
    text = re.sub(r"(?i)(password|passwd|secret|token|hash|credential)\s*['\"]?\s*[:=]\s*['\"][^'\"]*['\"]", r"\1=<redacted>", text)
    text = re.sub(r"(?i)(postgres(?:ql)?://)[^\s'\"]+", r"\1<redacted>", text)
    return text[:2000]


def _trace(frame, event, arg):
    _MEASUREMENT.trace(frame, event, _ACTIVE.get("case_id", "") if _ACTIVE else "")
    if _ACTIVE is None:
        return _trace
    if event == "call" and frame.f_code.co_name in {"execute", "executemany"}:
        query = frame.f_locals.get("query") or frame.f_locals.get("sql")
        params = frame.f_locals.get("params") or frame.f_locals.get("parameters")
        if query is not None:
            _ACTIVE.setdefault("queries", []).append({
                "query": _safe(query),
                "params": _safe(params),
            })
    if event in {"call", "line", "return"} and frame.f_code.co_name.startswith("test_"):
        _ACTIVE.setdefault("locals", {}).update({
            key: _safe(value)
            for key, value in frame.f_locals.items()
            if key not in {"request", "monkeypatch", "capsys", "capfd"}
        })
    return _trace


def pytest_runtest_call(item):
    global _ACTIVE
    item.user_properties.append(("nodeid", item.nodeid))
    parameters = {}
    callspec = getattr(item, "callspec", None)
    if callspec is not None:
        parameters = {key: _safe(value) for key, value in callspec.params.items()}
    _ACTIVE = {"case_id": getattr(getattr(item, "callspec", None), "id", item.nodeid),
               "parameters": parameters, "locals": {}, "queries": []}
    previous = sys.gettrace()
    sys.settrace(_trace)
    try:
        yield
    finally:
        sys.settrace(previous)
        _RESULTS[item.nodeid] = dict(_ACTIVE)
        _ACTIVE = None


pytest_runtest_call = pytest.hookimpl(hookwrapper=True)(pytest_runtest_call)


def pytest_sessionfinish(session, exitstatus):
    target = os.environ.get("SGFAP_TRACE_FILE")
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    measurement_path = path.with_name("workflow_coverage.json")
    measurement_path.write_text(json.dumps(_MEASUREMENT.result(), ensure_ascii=False, indent=2), encoding="utf-8")
