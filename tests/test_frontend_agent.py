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
    BASE_CSS_ID,
    FrontendAgent,
    apply_base_css,
    check_app_title,
    check_fetch_against_contract,
    find_english_labels,
    find_fetch_calls,
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


class TestOutputBudgetAndBaseCss(unittest.TestCase):
    """S5-03 test findings (Nov 26-27): truncated pages and weak styling from the 3b model."""

    def test_default_output_budget_is_4096_with_room_in_context(self):
        agent = FrontendAgent()
        self.assertEqual(agent.num_predict, 4096)
        self.assertGreater(agent.num_ctx, agent.num_predict)

    def test_output_budget_comes_from_env(self):
        old = os.environ.get("FRONTEND_NUM_PREDICT")
        try:
            os.environ["FRONTEND_NUM_PREDICT"] = "6000"
            self.assertEqual(FrontendAgent().num_predict, 6000)
            os.environ["FRONTEND_NUM_PREDICT"] = "not-a-number"
            self.assertEqual(FrontendAgent().num_predict, 4096)
        finally:
            if old is None:
                os.environ.pop("FRONTEND_NUM_PREDICT", None)
            else:
                os.environ["FRONTEND_NUM_PREDICT"] = old

    def test_base_css_goes_first_into_head_once(self):
        out = apply_base_css(PAGE)
        self.assertIn(f'<style id="{BASE_CSS_ID}">', out)
        # after <meta charset> (must stay in the first 1024 bytes), before </head>
        self.assertLess(out.index('charset="utf-8"'), 1024)
        self.assertLess(out.index('charset="utf-8"'), out.index(BASE_CSS_ID))
        self.assertLess(out.index(BASE_CSS_ID), out.index("</head>"))
        self.assertEqual(apply_base_css(out), out)  # idempotent
        validate_ui_code(out)

    def test_base_css_added_when_page_has_no_head(self):
        page = "<html><body><header><h1>A</h1></header><main><p>x</p></main></body></html>"
        out = apply_base_css(page)
        self.assertIn("<head>", out)
        self.assertIn(BASE_CSS_ID, out)
        validate_ui_code(out)

    def test_generated_and_template_pages_carry_base_css(self):
        for use_ollama in (True, False):
            with self.subTest(use_ollama=use_ollama):
                art = FrontendAgent(use_ollama=use_ollama, llm_client=fixed_reply(VALID_REPLY)).execute_task(
                    FE_TASK).output_artifacts
                content = art["files"][0]["content"]
                self.assertIn(BASE_CSS_ID, content)
                for cls in (".card", ".grid", ".btn-primary", ".form", ".alert"):
                    self.assertIn(cls, content)


CONTRACT_TASK = dict(FE_TASK, title="Frontend UI", context_artifacts={
    "requirement": "Kafe sipariş uygulaması",
    "shared_contract": {"endpoints": [
        {"method": "POST", "path": "/register"}, {"method": "POST", "path": "/login"},
        {"method": "GET", "path": "/products"}, {"method": "POST", "path": "/orders"},
        {"method": "GET", "path": "/orders/{order_id}"},
    ]},
})


def page_with(body, title="Kafe Sipariş", script=""):
    return (f"<!DOCTYPE html><html lang=\"tr\"><head><meta charset=\"utf-8\"><title>{title}</title></head><body>"
            f"<header class=\"app-header\"><h1>{title}</h1></header><main class=\"container\">{body}</main>"
            f"<script>{script}</script></body></html>")


GOOD_BODY = "<section class=\"section\"><h2>Ürünler</h2><div class=\"grid\" id=\"g\"></div></section>"


def sequence_reply(*texts):
    calls = []

    def client(prompt):
        calls.append(prompt)
        return texts[min(len(calls), len(texts)) - 1]
    client.calls = calls
    return client


class TestTagBalance(unittest.TestCase):
    """S5-03: Elif's review found a page whose tags did not match."""

    def test_unclosed_div_is_rejected_with_line(self):
        broken = page_with("<section class=\"section\"><div class=\"grid\"><div class=\"card\">x</div></section>")
        with self.assertRaises(ModelOutputError) as ctx:
            validate_ui_code(broken)
        self.assertIn("<div>", str(ctx.exception))
        self.assertIn("kapatılmamış", str(ctx.exception))

    def test_stray_closing_tag_is_rejected(self):
        with self.assertRaises(ModelOutputError) as ctx:
            validate_ui_code(page_with(GOOD_BODY + "</span>"))
        self.assertIn("</span>", str(ctx.exception))

    def test_optional_end_tags_and_markup_inside_script_are_fine(self):
        body = ("<ul class=\"list\"><li>Bir<li>İki</ul><p>Paragraf<table><tr><td>a<td>b</table>"
                "<br><img src=\"x.png\" alt=\"\"><div/>" + GOOD_BODY)
        script = "g.innerHTML = '<div class=\"card\"><h3>' + name + '</h3>';"
        validate_ui_code(page_with(body, script=script))

    def test_mismatched_page_is_retried_once_then_accepted(self):
        broken = "```html\n" + page_with("<div>" + GOOD_BODY) + "\n```"
        fixed = "```html\n" + page_with(GOOD_BODY) + "\n```"
        client = sequence_reply(broken, fixed)
        result = FrontendAgent(use_ollama=True, llm_client=client).execute_task(FE_TASK)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(client.calls), 2)
        self.assertIn("REJECTED", client.calls[1])
        self.assertIn("kapatılmamış", client.calls[1])
        self.assertEqual(result.output_artifacts["validation_retries"], 1)

    def test_still_mismatched_after_retry_fails(self):
        broken = "```html\n" + page_with("<div>" + GOOD_BODY) + "\n```"
        client = sequence_reply(broken)
        result = FrontendAgent(use_ollama=True, llm_client=client).execute_task(FE_TASK)
        self.assertEqual(result.status, "FAILED")
        self.assertIn("uyumsuz etiket", result.error_message)
        self.assertEqual(len(client.calls), 2)


class TestAppNameAndTurkishPrompt(unittest.TestCase):
    """S5-03: the cafe page was titled 'Frontend Interface', had flat forms and English labels."""

    def test_prompt_asks_for_app_name_turkish_sections_and_css_classes(self):
        prompt = FrontendAgent(use_ollama=True).build_prompt(CONTRACT_TASK)
        for expected in ("lang=\"tr\"", "Frontend Interface", "Giriş Yap", "Siparişlerim", "div.grid",
                         "div.tabs", "Do NOT write a <style>", "Kafe sipariş uygulaması", "POST /orders"):
            self.assertIn(expected, prompt)
        self.assertNotIn("Put all CSS in one <style> block", prompt)

    def test_generic_title_is_rejected(self):
        for title in ("Frontend Interface", "Frontend UI", "Web App", ""):
            with self.subTest(title=title), self.assertRaises(ModelOutputError):
                check_app_title(page_with(GOOD_BODY, title=title), CONTRACT_TASK)
        self.assertEqual(check_app_title(page_with(GOOD_BODY), CONTRACT_TASK), "Kafe Sipariş")

    def test_generic_title_triggers_retry(self):
        generic = "```html\n" + page_with(GOOD_BODY, title="Frontend Interface") + "\n```"
        named = "```html\n" + page_with(GOOD_BODY) + "\n```"
        client = sequence_reply(generic, named)
        art = FrontendAgent(use_ollama=True, llm_client=client).execute_task(CONTRACT_TASK).output_artifacts
        self.assertEqual(art["app_title"], "Kafe Sipariş")
        self.assertIn("uygulamanın adı değil", client.calls[1])

    def test_english_labels_are_reported_as_warning(self):
        body = (GOOD_BODY + "<form class=\"form\"><label>Email</label><input placeholder=\"Password\">"
                "<button class=\"btn\">Login</button><button class=\"btn\">Sepete Ekle</button></form>")
        self.assertEqual(find_english_labels(page_with(body)), ["Email", "Login", "Password"])
        art = FrontendAgent(use_ollama=True, llm_client=fixed_reply(page_with(body))).execute_task(
            FE_TASK).output_artifacts
        self.assertEqual(art["english_labels"], ["Email", "Login", "Password"])


class TestFetchContractCheck(unittest.TestCase):
    """S5-03: frontend version of the Testing agent's contract check (warnings only)."""

    SCRIPT = """
    const API = '';
    fetch('/products').then(r => r.json());
    fetch(`${API}/orders`, {method: 'POST', headers: {'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token}, body: JSON.stringify({items: cart})});
    fetch('/orders/' + id);
    fetch("http://localhost:8000/login", { method: "post", body: JSON.stringify(f(x)) });
    fetch('/api/v1/cart', {method: 'PUT'});
    fetch(url);
    """

    def test_fetch_calls_are_extracted(self):
        calls = find_fetch_calls(self.SCRIPT)
        self.assertEqual(calls, [("GET", "/products"), ("POST", "/orders"), ("GET", "/orders/{}"),
                                 ("POST", "/login"), ("PUT", "/api/v1/cart")])

    def test_off_contract_and_unused_endpoints_are_warnings(self):
        reply = page_with(GOOD_BODY, script=self.SCRIPT)
        result = FrontendAgent(use_ollama=True, llm_client=fixed_reply(reply)).execute_task(CONTRACT_TASK)
        self.assertEqual(result.status, "SUCCESS")
        art = result.output_artifacts
        self.assertTrue(art["contract_checked"])
        self.assertEqual(art["contract_warnings"], ["Sözleşmede olmayan çağrı: PUT /api/v1/cart"])
        self.assertEqual(art["unused_endpoints"], ["POST /register"])
        self.assertTrue(any("[UYARI]" in line and "/api/v1/cart" in line for line in result.logs))

    def test_placeholder_script_is_asked_again_once(self):
        empty = page_with(GOOD_BODY, script="// JavaScript code will be added here")
        working = page_with(GOOD_BODY, script="fetch('/products').then(r => r.json());")
        client = sequence_reply(empty, working)
        art = FrontendAgent(use_ollama=True, llm_client=client).execute_task(CONTRACT_TASK).output_artifacts
        self.assertEqual(len(client.calls), 2)
        self.assertIn("fetch ile çağırmıyor", client.calls[1])
        self.assertEqual(art["fetch_calls"], ["GET /products"])
        self.assertEqual(art["validation_retries"], 1)

    def test_page_without_any_fetch_gets_warning(self):
        art = FrontendAgent(use_ollama=True, llm_client=fixed_reply(page_with(GOOD_BODY))).execute_task(
            CONTRACT_TASK).output_artifacts
        self.assertIn("Sayfa sözleşmedeki hiçbir uç noktayı fetch ile çağırmıyor.", art["contract_warnings"])
        self.assertEqual(check_fetch_against_contract(page_with(GOOD_BODY), [])["contract_warnings"],
                         ["Sayfa sözleşmedeki hiçbir uç noktayı fetch ile çağırmıyor."])

    def test_no_contract_means_no_contract_warnings(self):
        art = FrontendAgent(use_ollama=True, llm_client=fixed_reply(page_with(GOOD_BODY, script=self.SCRIPT))
                            ).execute_task(FE_TASK).output_artifacts
        self.assertFalse(art["contract_checked"])
        self.assertEqual(art["contract_warnings"], [])
        self.assertIn("PUT /api/v1/cart", art["fetch_calls"])


class _StubOllama(BaseHTTPRequestHandler):
    reply = {"response": VALID_REPLY, "done": True}
    status = 200
    raw = None
    last_body = None

    def do_POST(self):
        _StubOllama.last_body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
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
        options = _StubOllama.last_body["options"]
        self.assertEqual(options["num_predict"], 4096)
        self.assertEqual(options["num_ctx"], 8192)

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
