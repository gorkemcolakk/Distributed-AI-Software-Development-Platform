"""
S5-06 (Berat İnan): pass rate of the tests the Testing Agent generated.

After a run, the Master runs the generated pytest files against the generated backend on a temporary
copy of the workspace (the app may create app.db) and counts passed / failed / errored tests from the
JUnit XML report. The pass rate is a benchmark metric for the testing model: it is stored with the run
(db_manager.save_generated_test_result) and compared per model (db_manager.get_generated_test_pass_rates).

Like the smoke test this executes model-written code, so it only runs with MASTER_SMOKE_TEST=true.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TIMEOUT = 90.0


def find_test_files(workspace: Path) -> List[Path]:
    """Generated pytest files (test_*.py / *_test.py) in the workspace."""
    return [p for p in sorted(workspace.rglob("*.py"))
            if p.name.startswith("test_") or p.name.endswith("_test.py")]


def _python_dirs(root: Path) -> List[str]:
    """Every folder holding a .py file, so `from main import app` works wherever the backend was written."""
    dirs = {str(p.parent) for p in root.rglob("*.py")}
    return [str(root)] + sorted(dirs - {str(root)})


def parse_junit(xml_path: Path) -> Dict[str, Any]:
    """Counts and per-test outcomes from a pytest --junitxml report."""
    root = ET.parse(xml_path).getroot()
    cases = []
    for case in root.iter("testcase"):
        outcome, message = "passed", None
        for tag in ("failure", "error", "skipped"):
            child = case.find(tag)
            if child is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = (child.get("message") or child.text or "").strip()[:200] or None
                break
        cases.append({"name": case.get("name"), "file": case.get("classname"), "outcome": outcome,
                      "message": message})
    # Collection errors (e.g. the test file cannot import the backend) show up as <testsuite errors="1">
    # with no <testcase>, so they are counted from the suite attributes too.
    suite_errors = sum(int(s.get("errors") or 0) for s in root.iter("testsuite"))
    counted_errors = sum(1 for c in cases if c["outcome"] == "error")
    return {"cases": cases, "collection_errors": max(0, suite_errors - counted_errors)}


def summarize(cases: List[Dict[str, Any]], collection_errors: int = 0) -> Dict[str, Any]:
    passed = sum(1 for c in cases if c["outcome"] == "passed")
    failed = sum(1 for c in cases if c["outcome"] == "failed")
    errors = sum(1 for c in cases if c["outcome"] == "error") + collection_errors
    skipped = sum(1 for c in cases if c["outcome"] == "skipped")
    executed = passed + failed + errors  # skipped tests are not part of the rate
    return {"passed": passed, "failed": failed, "errors": errors, "skipped": skipped, "total": executed,
            "pass_rate": round(passed / executed, 4) if executed else None}


def run_generated_tests(workspace_path: Any, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """PASSED when every generated test passes, FAILED otherwise, SKIPPED when there are no test files."""
    workspace = Path(str(workspace_path or ""))
    if not workspace_path or not workspace.is_dir():
        return {"status": "SKIPPED", "reason": "çalışma alanı yok", "pass_rate": None, "cases": []}
    tests = find_test_files(workspace)
    if not tests:
        return {"status": "SKIPPED", "reason": "üretilmiş test dosyası yok", "pass_rate": None, "cases": []}

    if importlib.util.find_spec("pytest") is None:
        return {"status": "SKIPPED", "reason": "pytest kurulu değil (pip install -r requirements.txt)",
                "pass_rate": None, "cases": [], "test_files": [t.name for t in tests]}

    with tempfile.TemporaryDirectory(prefix="gentests-") as tmp:
        copy = Path(tmp) / "app"
        shutil.copytree(workspace, copy)
        report = Path(tmp) / "junit.xml"
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(_python_dirs(copy) + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(copy),
               f"--junitxml={report}"] + [str(copy / t.relative_to(workspace)) for t in tests]
        try:
            proc = subprocess.run(cmd, cwd=str(copy), env=env, capture_output=True, text=True,
                                  timeout=timeout, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return {"status": "FAILED", "reason": f"{timeout:.0f} sn içinde bitmedi", "pass_rate": 0.0,
                    "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0, "cases": [],
                    "test_files": [t.name for t in tests]}
        if not report.exists():
            return {"status": "FAILED", "reason": (proc.stderr or proc.stdout or "pytest çıktı vermedi").strip()[-300:],
                    "pass_rate": 0.0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "total": 1, "cases": [],
                    "test_files": [t.name for t in tests]}
        parsed = parse_junit(report)

    summary = summarize(parsed["cases"], parsed["collection_errors"])
    if summary["total"] == 0:
        status, reason = "SKIPPED", "çalıştırılabilir test bulunamadı"
    else:
        status = "PASSED" if summary["passed"] == summary["total"] else "FAILED"
        reason = f"{summary['passed']}/{summary['total']} test geçti (%{summary['pass_rate'] * 100:.0f})"
        if parsed["collection_errors"]:
            reason += f", {parsed['collection_errors']} dosya yüklenemedi"
    return {"status": status, "reason": reason, **summary, "cases": parsed["cases"],
            "test_files": [t.name for t in tests]}
