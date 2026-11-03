"""
S3-03 (Kübra Hepcan): FrontendAgent local Ollama UI generation.

No real Ollama is needed: the model is replaced by small doubles, plus one
stub HTTP server for the real client. Nothing here touches state.db.
"""

import json
import os
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.frontend_agent import (
    FrontendAgent,
    ModelOutputError,
    OllamaCallError,
    extract_html_code,
    validate_ui_code,
)
from src.master.workspace import RunWorkspace, UnsafePathError

PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Notes</title>
<style>body { font-family: sans-serif; }</style></head>
<body>
<header><h1>Notes</h1></header>
<main>
  <form id="f"><input id="t" type="text"><button type="submit">Add</button></form>
  <ul id="list"></ul>
</main>
<script>document.getElementById('f').addEventListener('submit', e => e.preventDefault());</script>
</body>
</html>"""

VALID_REPLY = f"Here is the page:\n\n```html\n{PAGE}\n```\n"

FE_TASK = {
    "task_id": "task-fe-1",
    "title": "Frontend UI/UX Implementation",
    "category": "FRONTEND",
    "description": "A notes page with a form and a list.",
    "required_specialty": "frontend",
    "context_artifacts": {"endpoints_created": ["/api/v1/notes"]},
}


def fixed_reply(text):
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
        code = extract_html_code(VALID_REPLY)
        self.assertTrue(code.startswith("<!DOCTYPE html>"))
        self.assertNotIn("```", code)
        count, components = validate_ui_code(code)
        self.assertGreaterEqual(count, 3)
        for expected in ("header", "main", "form", "button", "input", "ul"):
            self.assertIn(expected, components)

    def test_reply_without_fence_is_used_as_is(self):
        self.assertEqual(extract_html_code(PAGE), PAGE.strip())

    def test_empty_reply_is_rejected(self):
        for reply in ("", "   \n  "):
            with self.assertRaises(ModelOutputError):
                extract_html_code(reply)

    def test_prose_only_reply_is_rejected(self):
        with self.assertRaises(ModelOutputError):
            validate_ui_code(extract_html_code("I cannot help with that."))

    def test_truncated_reply_is_rejected(self):
        truncated = PAGE.split("<script>")[0] + "<script>document.getElementById("
        with self.assertRaises(ModelOutputError) as ctx:
            validate_ui_code(truncated)
        self.assertIn("yarım", str(ctx.exception))

    def test_unclosed_script_is_rejected(self):
        broken = PAGE.replace("</script>", "")
        with self.assertRaises(ModelOutputError):
            validate_ui_code(broken)

    def test_page_without_visible_elements_is_rejected(self):
        empty = "<!DOCTYPE html><html><head><title>x</title></head><body></body></html>"
        with self.assertRaises(ModelOutputError) as ctx:
            validate_ui_code(empty)
        self.assertIn("arayüz öğesi", str(ctx.exception))


class TestFrontendAgentGeneration(unittest.TestCase):

    def test_valid_model_reply_produces_ui_file(self):
        client = fixed_reply(VALID_REPLY)
        result = FrontendAgent(use_ollama=True, llm_client=client).execute_task(FE_TASK)

        self.assertEqual(result.status, "SUCCESS")
        art = result.output_artifacts
        self.assertEqual(art["status"], "FRONTEND_UI_GENERATED")
        self.assertEqual(art["generation_mode"], "ollama")
        self.assertEqual(art["model_used"], "qwen2.5-coder:3b")
        self.assertEqual(art["files"][0]["filename"], "ui_task_fe_1.html")
        self.assertEqual(art["ui_files_generated"], ["ui_task_fe_1.html"])
        self.assertIn("<form", art["files"][0]["content"])
        self.assertIn(FE_TASK["description"], client.calls[0])
        self.assertIn("/api/v1/notes", client.calls[0])

    def test_broken_model_reply_fails_task_even_with_fallback_enabled(self):
        for reply in ("I cannot help with that.", "", "```html\n<div>only a fragment</div>\n```"):
            with self.subTest(reply=reply):
                agent = FrontendAgent(use_ollama=True, llm_client=fixed_reply(reply), fallback_enabled=True)
                result = agent.execute_task(FE_TASK)

                self.assertEqual(result.status, "FAILED")
                self.assertTrue(result.error_message)
                self.assertEqual(result.output_artifacts, {})

    def test_ollama_down_with_fallback_returns_labelled_page(self):
        agent = FrontendAgent(use_ollama=True, llm_client=raising_client("CONNECTION_REFUSED"),
                              fallback_enabled=True)
        result = agent.execute_task(FE_TASK)

        self.assertEqual(result.status, "SUCCESS")
        art = result.output_artifacts
        self.assertEqual(art["status"], "FRONTEND_UI_FALLBACK")
        self.assertEqual(art["generation_mode"], "fallback")
        self.assertEqual(art["fallback_reason"], "CONNECTION_REFUSED")
        self.assertIsNone(art["model_used"])
        self.assertTrue(any("[FALLBACK]" in line for line in result.logs))

    def test_ollama_down_without_fallback_fails_task(self):
        for error_type in ("TIMEOUT", "CONNECTION_REFUSED", "NOT_FOUND"):
            with self.subTest(error_type=error_type):
                agent = FrontendAgent(use_ollama=True, llm_client=raising_client(error_type),
                                      fallback_enabled=False)
                result = agent.execute_task(FE_TASK)

                self.assertEqual(result.status, "FAILED")
                self.assertIn(error_type, result.error_message)

    def test_disabled_ollama_never_calls_model(self):
        client = fixed_reply(VALID_REPLY)
        result = FrontendAgent(use_ollama=False, llm_client=client).execute_task(FE_TASK)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["status"], "FRONTEND_UI_TEMPLATE")
        self.assertEqual(result.output_artifacts["generation_mode"], "template")
        self.assertEqual(client.calls, [])

    def test_template_is_valid_html_and_escapes_title(self):
        task = dict(FE_TASK, title="<script>alert(1)</script>")
        art = FrontendAgent(use_ollama=False).execute_task(task).output_artifacts
        content = art["files"][0]["content"]
        self.assertNotIn("<script>alert(1)</script>", content)
        validate_ui_code(content)

    def test_env_flag_disables_ollama(self):
        old = os.environ.get("FRONTEND_AGENT_USE_OLLAMA")
        os.environ["FRONTEND_AGENT_USE_OLLAMA"] = "false"
        try:
            self.assertFalse(FrontendAgent().use_ollama)
        finally:
            if old is None:
                del os.environ["FRONTEND_AGENT_USE_OLLAMA"]
            else:
                os.environ["FRONTEND_AGENT_USE_OLLAMA"] = old

    def test_unsafe_output_filename_fails_before_model_is_called(self):
        for bad in ("../evil.html", "/etc/x.html", "C:\\x.html", "ui.exe"):
            with self.subTest(bad=bad):
                client = fixed_reply(VALID_REPLY)
                result = FrontendAgent(use_ollama=True, llm_client=client).execute_task(
                    dict(FE_TASK, output_filename=bad))
                self.assertEqual(result.status, "FAILED")
                self.assertEqual(client.calls, [])

    def test_generated_file_is_written_into_run_workspace(self):
        import tempfile
        art = FrontendAgent(use_ollama=True, llm_client=fixed_reply(VALID_REPLY)).execute_task(
            FE_TASK).output_artifacts
        with tempfile.TemporaryDirectory() as root:
            written = RunWorkspace("run-fe-test", root=root).write_files(art["files"])
            self.assertEqual(written[0]["relative_path"], "ui_task_fe_1.html")
            self.assertGreater(written[0]["size_bytes"], 100)
            self.assertTrue(os.path.isfile(written[0]["path"]))


class _StubOllama(BaseHTTPRequestHandler):
    reply = {"response": VALID_REPLY, "done": True}
    status = 200
    raw = None

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        payload = self.raw if self.raw is not None else json.dumps(self.reply).encode("utf-8")
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class TestOllamaHttpClient(unittest.TestCase):

    def setUp(self):
        _StubOllama.reply = {"response": VALID_REPLY, "done": True}
        _StubOllama.status = 200
        _StubOllama.raw = None
        self.server = HTTPServer(("127.0.0.1", 0), _StubOllama)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.host = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_real_client_reads_response_field(self):
        agent = FrontendAgent(use_ollama=True, ollama_host=self.host, timeout=5)
        result = agent.execute_task(FE_TASK)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["generation_mode"], "ollama")

    def test_model_not_found_maps_to_not_found(self):
        _StubOllama.status = 404
        agent = FrontendAgent(use_ollama=True, ollama_host=self.host, timeout=5, fallback_enabled=True)
        result = agent.execute_task(FE_TASK)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output_artifacts["fallback_reason"], "NOT_FOUND")

    def test_non_json_body_is_invalid_response(self):
        _StubOllama.raw = b"not json"
        agent = FrontendAgent(use_ollama=True, ollama_host=self.host, timeout=5, fallback_enabled=False)
        result = agent.execute_task(FE_TASK)
        self.assertEqual(result.status, "FAILED")
        self.assertIn("JSON", result.error_message)

    def test_closed_port_maps_to_connection_refused(self):
        # A port that was just free and is closed again: connecting is refused, not timed out.
        # (Windows needs a few seconds to report a refused connection, so the timeout is generous.)
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        agent = FrontendAgent(use_ollama=True, ollama_host=f"http://127.0.0.1:{port}", timeout=15,
                              fallback_enabled=True)
        result = agent.execute_task(FE_TASK)
        self.assertEqual(result.output_artifacts["fallback_reason"], "CONNECTION_REFUSED")


if __name__ == "__main__":
    unittest.main()
