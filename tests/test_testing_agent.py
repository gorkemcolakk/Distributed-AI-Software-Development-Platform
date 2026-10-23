"""
Unit Tests for S3-06: TestingAgent local Ollama test generation.
Sorumlu: Berat İnan (Testing & QA Agent — deepseek-coder:6.7b)

Covers: valid model output, broken model output, path traversal protection,
Ollama timeout / connection errors (with and without fallback) and an optional
live smoke test against a real local Ollama (RUN_OLLAMA_SMOKE=1).
"""

import sys
import os
import json
import shutil
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.testing_agent import (
    TestingAgent,
    ModelOutputError,
    OllamaCallError,
    UnsafePathError,
    extract_python_code,
    validate_test_code,
    resolve_safe_output_path,
)
from src.contracts import TaskPayloadContract_v1


VALID_REPLY = """Here are the tests:

```python
import pytest

def add(a, b):
    return a + b

def test_add_positive():
    assert add(2, 3) == 5

def test_add_negative():
    assert add(-1, -1) == -2

def test_add_type_error():
    with pytest.raises(TypeError):
        add(1, None)
```
"""

QA_TASK = {
    "task_id": "task-qa-1",
    "title": "Automated Testing & Quality Assurance",
    "category": "TESTING",
    "description": "Write unit tests for the book search API.",
    "dependencies": ["task-fe-1"],
    "required_specialty": "testing",
    "context_artifacts": {"endpoints_created": ["/api/v1/books"]},
}


def fixed_reply(text):
    """LLM client double that records the prompt and returns a fixed reply."""
    calls = []

    def client(prompt):
        calls.append(prompt)
        return text
    client.calls = calls
    return client


def raising_client(error_type):
    def client(prompt):
        raise OllamaCallError(f"simulated {error_type}", error_type=error_type)
    return client


class TestModelOutputParsing(unittest.TestCase):

    def test_code_block_is_extracted_and_validated(self):
        code = extract_python_code(VALID_REPLY)
        self.assertTrue(code.startswith("import pytest"))
        self.assertNotIn("```", code)
        # 2 plain asserts; pytest.raises is a context manager, not an assertion call
        self.assertEqual(validate_test_code(code), (3, 2))

    def test_unittest_style_assertions_are_counted(self):
        code = ("import unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        self.assertEqual(1, 1)\n"
                "        self.assertTrue(True)\n")
        self.assertEqual(validate_test_code(code), (1, 2))

    def test_reply_without_fence_is_used_as_is(self):
        self.assertEqual(extract_python_code("def test_x():\n    assert 1\n"), "def test_x():\n    assert 1")

    def test_empty_reply_is_rejected(self):
        for reply in ("", "   \n  ", None):
            with self.assertRaises(ModelOutputError):
                extract_python_code(reply)

    def test_syntax_error_is_rejected(self):
        with self.assertRaises(ModelOutputError) as ctx:
            validate_test_code("def test_broken(:\n    assert True\n")
        self.assertIn("geçerli Python değil", str(ctx.exception))

    def test_prose_only_reply_is_rejected(self):
        code = extract_python_code("Sure! I would write tests that check the API returns 200.")
        with self.assertRaises(ModelOutputError):
            validate_test_code(code)

    def test_code_without_test_functions_is_rejected(self):
        with self.assertRaises(ModelOutputError) as ctx:
            validate_test_code("def add(a, b):\n    return a + b\n")
        self.assertIn("test_", str(ctx.exception))

    def test_truncated_reply_is_rejected(self):
        truncated = "```python\ndef test_a():\n    assert foo(\n"
        with self.assertRaises(ModelOutputError):
            validate_test_code(extract_python_code(truncated))


class TestSafeOutputPath(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="qa_out_")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_plain_and_nested_names_stay_inside_base(self):
        base = os.path.realpath(self.base)
        self.assertEqual(str(resolve_safe_output_path(self.base, "test_api.py")),
                         os.path.join(base, "test_api.py"))
        self.assertEqual(str(resolve_safe_output_path(self.base, "tests/unit/test_api.py")),
                         os.path.join(base, "tests", "unit", "test_api.py"))

    def test_traversal_and_absolute_paths_are_rejected(self):
        attacks = [
            "../evil.py",
            "../../etc/passwd.py",
            "tests/../../evil.py",
            "..\\..\\Windows\\evil.py",
            "tests\\..\\..\\evil.py",
            "/etc/cron.d/evil.py",
            "C:\\Windows\\System32\\evil.py",
            "C:evil.py",
            "\\\\server\\share\\evil.py",
            "test_\x00.py",
            "",
            "   ",
        ]
        for name in attacks:
            with self.subTest(name=name):
                with self.assertRaises(UnsafePathError):
                    resolve_safe_output_path(self.base, name)

    def test_non_python_files_are_rejected(self):
        for name in ("run.sh", "test_api.py.exe", ".bashrc", "conftest"):
            with self.subTest(name=name):
                with self.assertRaises(UnsafePathError):
                    resolve_safe_output_path(self.base, name)

    def test_agent_refuses_traversal_from_task_payload_before_calling_model(self):
        client = fixed_reply(VALID_REPLY)
        agent = TestingAgent(use_ollama=True, llm_client=client, output_dir=self.base)
        task = dict(QA_TASK, context_artifacts={"output_filename": "../../outside_test.py"})

        result = agent.execute_task(task)

        self.assertEqual(result.status, "FAILED")
        self.assertIn("Yol geçişi", result.error_message)
        self.assertEqual(client.calls, [], "model must not be called for an unsafe payload")
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.base), "outside_test.py")))

    def test_agent_writes_valid_file_inside_output_dir(self):
        agent = TestingAgent(use_ollama=True, llm_client=fixed_reply(VALID_REPLY), output_dir=self.base)
        result = agent.execute_task(QA_TASK)

        self.assertEqual(result.status, "SUCCESS")
        written = result.output_artifacts["written_path"]
        self.assertEqual(os.path.dirname(written), os.path.realpath(self.base))
        self.assertTrue(os.path.basename(written).startswith("test_task_qa_1"))
        with open(written, encoding="utf-8") as fh:
            self.assertIn("def test_add_positive", fh.read())


class TestTestingAgentGeneration(unittest.TestCase):

    def test_valid_model_reply_produces_test_suite(self):
        client = fixed_reply(VALID_REPLY)
        agent = TestingAgent(use_ollama=True, llm_client=client)
        result = agent.execute_task(QA_TASK)

        self.assertEqual(result.status, "SUCCESS")
        art = result.output_artifacts
        self.assertEqual(art["status"], "TEST_SUITE_GENERATED")
        self.assertEqual(art["generation_mode"], "ollama")
        self.assertEqual(art["model_used"], "deepseek-coder:6.7b")
        self.assertEqual(art["test_function_count"], 3)
        self.assertEqual(art["files"][0]["filename"], "test_task_qa_1.py")
        self.assertIsNone(art["written_path"])

        prompt = client.calls[0]
        self.assertIn(QA_TASK["description"], prompt)
        self.assertIn("/api/v1/books", prompt)

    def test_broken_model_reply_fails_task_without_fallback(self):
        for reply, expected in (("I cannot help with that.", "geçerli Python değil"),
                                ("```python\ndef add(a, b):\n    return a + b\n```", "test_")):
            with self.subTest(reply=reply):
                agent = TestingAgent(use_ollama=True, llm_client=fixed_reply(reply), fallback_enabled=True)
                result = agent.execute_task(QA_TASK)

                self.assertEqual(result.status, "FAILED")
                self.assertIn(expected, result.error_message)
                self.assertEqual(result.output_artifacts, {})

    def test_ollama_down_with_fallback_returns_labelled_template(self):
        agent = TestingAgent(use_ollama=True, llm_client=raising_client("CONNECTION_REFUSED"),
                             fallback_enabled=True)
        result = agent.execute_task(QA_TASK)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["status"], "TEST_SUITE_FALLBACK")
        self.assertEqual(result.output_artifacts["fallback_reason"], "CONNECTION_REFUSED")
        self.assertIsNone(result.output_artifacts["model_used"])

    def test_ollama_timeout_without_fallback_fails_task(self):
        agent = TestingAgent(use_ollama=True, llm_client=raising_client("TIMEOUT"), fallback_enabled=False)
        result = agent.execute_task(QA_TASK)

        self.assertEqual(result.status, "FAILED")
        self.assertIn("TIMEOUT", result.error_message)

    def test_disabled_ollama_never_calls_model(self):
        client = fixed_reply(VALID_REPLY)
        result = TestingAgent(use_ollama=False, llm_client=client).execute_task(QA_TASK)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["status"], "TEST_SUITE_TEMPLATE")
        self.assertEqual(client.calls, [])

    def test_env_flag_disables_ollama(self):
        old = os.environ.get("TESTING_AGENT_USE_OLLAMA")
        os.environ["TESTING_AGENT_USE_OLLAMA"] = "false"
        try:
            self.assertFalse(TestingAgent().use_ollama)
        finally:
            if old is None:
                del os.environ["TESTING_AGENT_USE_OLLAMA"]
            else:
                os.environ["TESTING_AGENT_USE_OLLAMA"] = old

    def test_accepts_versioned_task_payload_contract(self):
        payload = TaskPayloadContract_v1(run_id="run-1234", **QA_TASK).model_dump()
        result = TestingAgent(use_ollama=True, llm_client=fixed_reply(VALID_REPLY)).execute_task(payload)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.task_id, "task-qa-1")


# ---------------------------------------------------------------------------
# Real HTTP: a local stub server plays Ollama, so the real _call_ollama code path
# (urllib, JSON parsing, timeout and error classification) is exercised.
# ---------------------------------------------------------------------------

class _StubOllama(BaseHTTPRequestHandler):
    mode = "ok"
    delay = 0.0
    last_body = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        type(self).last_body = json.loads(self.rfile.read(length) or b"{}")
        if self.mode == "slow":
            time.sleep(self.delay)
        if self.mode == "404":
            self.send_response(404)
            self.end_headers()
            return
        payload = b"<html>not json</html>" if self.mode == "garbage" else json.dumps(
            {"model": "deepseek-coder:6.7b", "response": VALID_REPLY, "done": True}).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # client already gave up (timeout test)

    def log_message(self, *args):
        pass


class TestOllamaHttpClient(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _StubOllama)
        cls.host = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _StubOllama.mode, _StubOllama.delay = "ok", 0.0

    def _agent(self, **kw):
        kw.setdefault("timeout", 5)
        return TestingAgent(use_ollama=True, ollama_host=self.host, **kw)

    def test_request_is_sent_to_generate_with_selected_model(self):
        result = self._agent().execute_task(QA_TASK)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(_StubOllama.last_body["model"], "deepseek-coder:6.7b")
        self.assertFalse(_StubOllama.last_body["stream"])
        self.assertIn("Write unit tests", _StubOllama.last_body["prompt"])

    def test_slow_server_times_out_within_limit(self):
        _StubOllama.mode, _StubOllama.delay = "slow", 3.0
        agent = self._agent(timeout=0.5)

        started = time.monotonic()
        with self.assertRaises(OllamaCallError) as ctx:
            agent._call_ollama("prompt")
        elapsed = time.monotonic() - started

        self.assertEqual(ctx.exception.error_type, "TIMEOUT")
        self.assertLess(elapsed, 2.5, "client must not wait for the slow server")

    def test_slow_server_with_fallback_does_not_crash_task(self):
        _StubOllama.mode, _StubOllama.delay = "slow", 3.0
        result = self._agent(timeout=0.5, fallback_enabled=True).execute_task(QA_TASK)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["fallback_reason"], "TIMEOUT")

    def test_missing_model_is_classified_not_found(self):
        _StubOllama.mode = "404"
        with self.assertRaises(OllamaCallError) as ctx:
            self._agent()._call_ollama("prompt")
        self.assertEqual(ctx.exception.error_type, "NOT_FOUND")

    def test_non_json_response_is_classified_invalid(self):
        _StubOllama.mode = "garbage"
        with self.assertRaises(OllamaCallError) as ctx:
            self._agent()._call_ollama("prompt")
        self.assertEqual(ctx.exception.error_type, "INVALID_RESPONSE")

    def test_closed_port_is_classified_connection_refused(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        agent = TestingAgent(use_ollama=True, ollama_host=f"http://127.0.0.1:{free_port}", timeout=10)
        with self.assertRaises(OllamaCallError) as ctx:
            agent._call_ollama("prompt")
        self.assertEqual(ctx.exception.error_type, "CONNECTION_REFUSED")


@unittest.skipUnless(os.getenv("RUN_OLLAMA_SMOKE") == "1",
                     "Canlı Ollama testi için RUN_OLLAMA_SMOKE=1 ayarlayın (deepseek-coder:6.7b yüklü olmalı).")
class TestLiveOllamaSmoke(unittest.TestCase):
    """Optional: real deepseek-coder:6.7b run. Not executed in CI."""

    def test_deepseek_generates_valid_test_file(self):
        agent = TestingAgent(use_ollama=True, fallback_enabled=False)
        result = agent.execute_task(QA_TASK)

        self.assertEqual(result.status, "SUCCESS", result.error_message)
        self.assertEqual(result.output_artifacts["generation_mode"], "ollama")
        self.assertGreaterEqual(result.output_artifacts["test_function_count"], 1)
        print("\n--- deepseek-coder:6.7b output ---\n" + result.output_artifacts["files"][0]["content"])


if __name__ == "__main__":
    unittest.main()
