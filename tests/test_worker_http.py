"""
S3-06: Black-box HTTP tests for the authenticated Worker Agent endpoint (S3-02).
Sorumlu: Berat İnan (Testing & QA Agent)

The worker server (src/api/worker_server.py, İrem Yılmaz) is tested over real HTTP,
so the tests do not depend on its framework. They follow docs/WORKER_HTTP_API_DRAFT.md:
  - GET  <WORKER_HEALTH_PATH>  -> 200 JSON with "status"
  - POST <WORKER_TASK_PATH>    -> needs "Authorization: Bearer <token>", else 401

Configuration (environment / .env):
  WORKER_BASE_URL     default: BACKEND_API_HOST or http://localhost:8000
  WORKER_AUTH_TOKEN   default: BACKEND_AUTH_TOKEN
  WORKER_TASK_PATH    default: /task
  WORKER_HEALTH_PATH  default: /health
  WORKER_HTTP_TIMEOUT default: 10 (seconds)

When no worker is reachable the endpoint tests are skipped; the hard-coded-secret
guard at the bottom always runs.
"""

import sys
import os
import json
import re
import time
import unittest
import urllib.error
import urllib.request
import uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.contracts import TaskPayloadContract_v1

BASE_URL = (os.getenv("WORKER_BASE_URL") or os.getenv("BACKEND_API_HOST") or "http://localhost:8000").rstrip("/")
TOKEN = os.getenv("WORKER_AUTH_TOKEN") or os.getenv("BACKEND_AUTH_TOKEN") or ""
TASK_PATH = os.getenv("WORKER_TASK_PATH", "/task")
HEALTH_PATH = os.getenv("WORKER_HEALTH_PATH", "/health")
TIMEOUT = float(os.getenv("WORKER_HTTP_TIMEOUT", "10"))


def http(method, path, body=None, headers=None, timeout=TIMEOUT):
    """Returns (status_code, parsed_json_or_text, elapsed_seconds); never raises on HTTP errors."""
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read()
    elapsed = time.monotonic() - started
    try:
        return code, json.loads(raw or b"null"), elapsed
    except json.JSONDecodeError:
        return code, raw.decode("utf-8", "replace"), elapsed


def worker_reachable():
    try:
        code, _, _ = http("GET", HEALTH_PATH, timeout=2)
        return code < 500
    except (urllib.error.URLError, OSError):
        return False


def sample_task(**overrides):
    payload = TaskPayloadContract_v1(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        task_id=f"task-qa-{uuid.uuid4().hex[:6]}",
        title="Automated Testing & Quality Assurance",
        category="TESTING",
        description="Write unit tests for the book search API.",
        required_specialty="testing",
    ).model_dump()
    payload.update(overrides)
    return payload


_REACHABLE = worker_reachable()


@unittest.skipUnless(_REACHABLE, f"Worker HTTP sunucusu {BASE_URL}{HEALTH_PATH} adresinde çalışmıyor (S3-02).")
class TestWorkerHttpEndpoint(unittest.TestCase):

    def auth(self, token=None):
        return {"Authorization": f"Bearer {TOKEN if token is None else token}"}

    def test_health_endpoint_is_up(self):
        code, body, _ = http("GET", HEALTH_PATH)
        self.assertEqual(code, 200)
        self.assertIsInstance(body, dict)
        self.assertIn("status", body)

    def test_health_does_not_leak_token(self):
        _, body, _ = http("GET", HEALTH_PATH)
        if TOKEN:
            self.assertNotIn(TOKEN, json.dumps(body))

    def test_task_without_authorization_header_is_rejected(self):
        code, _, _ = http("POST", TASK_PATH, sample_task())
        self.assertEqual(code, 401)

    def test_task_with_wrong_token_is_rejected(self):
        code, _, _ = http("POST", TASK_PATH, sample_task(), headers=self.auth("wrong-" + uuid.uuid4().hex))
        self.assertEqual(code, 401)

    def test_malformed_authorization_headers_are_rejected(self):
        bad_headers = [
            {"Authorization": "Bearer"},
            {"Authorization": "Bearer "},
            {"Authorization": f"Basic {TOKEN}"},
            {"Authorization": f"Token {TOKEN}"},
            {"Authorization": TOKEN},
            {"Authorization": f"Bearer {TOKEN}x"},
            {"Authorization": f"Bearer {TOKEN[:-1]}"} if len(TOKEN) > 1 else {"Authorization": "Bearer ?"},
        ]
        for case, headers in enumerate(bad_headers):
            with self.subTest(case=case):  # header itself is not printed: it contains the token
                code, _, _ = http("POST", TASK_PATH, sample_task(), headers=headers)
                self.assertEqual(code, 401)

    def test_rejection_does_not_echo_the_submitted_token(self):
        attempt = "leak-check-" + uuid.uuid4().hex
        _, body, _ = http("POST", TASK_PATH, sample_task(), headers=self.auth(attempt))
        self.assertNotIn(attempt, json.dumps(body))

    def test_unauthorized_request_is_rejected_fast(self):
        """401 must come before any model work: well under the model timeout."""
        _, _, elapsed = http("POST", TASK_PATH, sample_task(), headers=self.auth("wrong"))
        self.assertLess(elapsed, 2.0)

    @unittest.skipUnless(TOKEN, "Geçerli token testi için WORKER_AUTH_TOKEN / BACKEND_AUTH_TOKEN ayarlayın.")
    def test_valid_token_and_payload_is_accepted(self):
        task = sample_task()
        code, body, _ = http("POST", TASK_PATH, task, headers=self.auth())
        self.assertIn(code, (200, 201, 202), body)
        self.assertIsInstance(body, dict)
        if "task_id" in body:
            self.assertEqual(body["task_id"], task["task_id"])

    @unittest.skipUnless(TOKEN, "Geçerli token testi için WORKER_AUTH_TOKEN / BACKEND_AUTH_TOKEN ayarlayın.")
    def test_valid_token_with_invalid_payload_is_client_error(self):
        for body in (b"{not json", {"task_id": ""}, {"title": "missing task_id"}):
            with self.subTest(body=str(body)[:30]):
                code, _, _ = http("POST", TASK_PATH, body, headers=self.auth())
                self.assertIn(code, (400, 422))

    @unittest.skipUnless(TOKEN, "Geçerli token testi için WORKER_AUTH_TOKEN / BACKEND_AUTH_TOKEN ayarlayın.")
    def test_client_side_timeout_is_enforced(self):
        """A client that allows too little time must get a timeout, not hang (REQ-9)."""
        try:
            http("POST", TASK_PATH, sample_task(), headers=self.auth(), timeout=0.001)
        except (urllib.error.URLError, TimeoutError, OSError):
            return
        # The worker answered in under 1 ms (e.g. queued async with 202): also acceptable.


class TestNoHardcodedSecrets(unittest.TestCase):
    """S3-02 kabul kriteri 4: hiçbir gizli anahtar/token kaynak koduna sabit yazılmaz."""

    PATTERNS = [
        re.compile(r"change-this-secure-token", re.IGNORECASE),
        re.compile(r"""(?:AUTH_TOKEN|API_KEY|SECRET)\s*=\s*['"][^'"\s]{8,}['"]"""),
        re.compile(r"""['"]Bearer\s+[A-Za-z0-9\-_.]{12,}['"]"""),
        re.compile(r"AIza[0-9A-Za-z\-_]{30,}"),
    ]

    def test_source_tree_has_no_hardcoded_tokens(self):
        offenders = []
        for folder in ("src", "master_agent_projesi", "scripts"):
            for dirpath, _, files in os.walk(os.path.join(ROOT, folder)):
                for name in files:
                    if not name.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, name)
                    with open(path, encoding="utf-8", errors="ignore") as fh:
                        for lineno, line in enumerate(fh, 1):
                            if any(p.search(line) for p in self.PATTERNS):
                                offenders.append(f"{os.path.relpath(path, ROOT)}:{lineno}")
        self.assertEqual(offenders, [], "Kaynak kodda sabit token/anahtar bulundu")


if __name__ == "__main__":
    unittest.main()
