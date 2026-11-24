"""
S5 (Eren Görkem Çolak): smoke test of the generated application.

After a run, the Master starts the generated FastAPI backend in a separate Python process (on a
temporary copy of the workspace, through FastAPI's TestClient, no open port) and calls /health and
every endpoint of the shared contract. The result says whether the delivered app really answers,
not only whether the agents returned files.

This executes model-written code on the Master machine, so it is opt-in: MASTER_SMOKE_TEST=true.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TIMEOUT = 40.0

# Runs inside the child process: imports the backend, calls the endpoints, prints one JSON line.
_RUNNER = r'''
import importlib.util, json, sys
result = {"checks": [], "error": None}
try:
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location("generated_backend", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = TestClient(module.app)
    endpoints = json.loads(sys.argv[2])
    token = None

    def sample(field):
        name = field.lower()
        if name in ("id",) or name.endswith("_id") or name in ("price", "amount", "quantity", "year", "age"):
            return 1
        if name in ("completed", "done", "is_active"):
            return False
        if name.endswith("s") and name not in ("address", "status", "password", "username"):
            return [1]
        return "smoke-" + name

    for ep in [{"method": "GET", "path": "/health"}] + endpoints:
        method, path = ep["method"], ep["path"]
        has_param = any(part.startswith(("{", ":")) for part in path.split("/"))
        url = "/".join("1" if part.startswith(("{", ":")) else part for part in path.split("/"))
        body = {f: sample(f) for f in ep.get("request") or []}
        headers = {"Authorization": "Bearer " + token} if token else {}
        try:
            if method == "GET":
                resp = client.get(url, headers=headers)
            else:
                resp = client.request(method, url, json=body, headers=headers)
            code = resp.status_code
            if path.endswith("/login") and code < 300:
                try:
                    data = resp.json()
                    token = str(data.get("token") or data.get("access_token") or "") or None
                except Exception:
                    pass
        except Exception as exc:
            code = 500
            ep = dict(ep, error=type(exc).__name__ + ": " + str(exc)[:160])
        # 404/405 on a fixed path means the route was never written; on /items/{id} the item may just not exist
        missing = code in (404, 405) and not has_param
        result["checks"].append({"method": method, "path": path, "status_code": code,
                                 "ok": code < 500 and not missing,
                                 "error": ep.get("error") or ("uç nokta yok" if missing else None)})
except Exception as exc:
    result["error"] = type(exc).__name__ + ": " + str(exc)[:300]
print("SMOKE_RESULT " + json.dumps(result))
'''


def is_enabled() -> bool:
    return os.environ.get("MASTER_SMOKE_TEST", "false").strip().lower() in ("1", "true", "yes", "on")


def find_backend(workspace: Path) -> Optional[Path]:
    """The generated Python file that defines the FastAPI app (tests are skipped)."""
    for path in sorted(workspace.rglob("*.py")):
        if path.name.startswith("test"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "FastAPI(" in text:
            return path
    return None


def run_smoke_test(workspace_path: Any, contract: Optional[Dict[str, Any]],
                   timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """PASSED when the app imports, every contract route exists and none answers 5xx; FAILED otherwise; SKIPPED without a backend."""
    workspace = Path(str(workspace_path or ""))
    if not workspace_path or not workspace.is_dir():
        return {"status": "SKIPPED", "reason": "çalışma alanı yok", "checks": []}
    backend = find_backend(workspace)
    if backend is None:
        return {"status": "SKIPPED", "reason": "FastAPI backend dosyası bulunamadı", "checks": []}

    endpoints: List[Dict[str, Any]] = list((contract or {}).get("endpoints") or [])
    with tempfile.TemporaryDirectory(prefix="smoke-") as tmp:
        copy = Path(tmp) / "app"
        shutil.copytree(workspace, copy)  # the app may create app.db; keep the real workspace clean
        target = copy / backend.relative_to(workspace)
        try:
            proc = subprocess.run([sys.executable, "-c", _RUNNER, str(target), json.dumps(endpoints)],
                                  cwd=str(target.parent), capture_output=True, text=True,
                                  timeout=timeout, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return {"status": "FAILED", "reason": f"{timeout:.0f} sn içinde bitmedi", "checks": [],
                    "backend_file": backend.name}

    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("SMOKE_RESULT ")), None)
    if line is None:
        return {"status": "FAILED", "reason": (proc.stderr or "çıktı yok").strip()[-300:], "checks": [],
                "backend_file": backend.name}
    data = json.loads(line[len("SMOKE_RESULT "):])
    checks = data.get("checks") or []
    if data.get("error"):
        return {"status": "FAILED", "reason": f"uygulama başlamadı: {data['error']}", "checks": checks,
                "backend_file": backend.name}
    passed = sum(1 for c in checks if c["ok"])
    status = "PASSED" if checks and passed == len(checks) else "FAILED"
    return {"status": status, "reason": f"{passed}/{len(checks)} uç nokta çalıştı",
            "checks": checks, "backend_file": backend.name}
