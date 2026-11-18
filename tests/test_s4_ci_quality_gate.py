"""
S4-06 (Testing & QA): guards for the CI quality gate and the manual API check script.

Sorumlu: Berat İnan (Testing & QA Agent - deepseek-coder:6.7b)

- The workflow file must keep running the whole suite on every PR and must not
  contain anything that lets a failing test pass (continue-on-error, `|| true`).
- master_agent_projesi/test_api.py must not carry placeholder-key assumptions,
  must never print the key, and must not touch the network unless asked to.
"""

import importlib.util
import io
import json
import os
import re
import sys
import types
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
API_SCRIPT = ROOT / "master_agent_projesi" / "test_api.py"
FAKE_KEY = "AIzaSy-S4-06-not-a-real-key-123456"


def load_api_script():
    spec = importlib.util.spec_from_file_location("s4_manual_api_check", API_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestWorkflowQualityGate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        # Comments may mention forbidden words; only check the actual YAML
        cls.code = "\n".join(line.split("#", 1)[0] for line in cls.text.splitlines())

    def test_runs_on_every_pull_request_and_on_main(self):
        self.assertRegex(self.code, r"(?m)^on:\s*$")
        self.assertRegex(self.code, r"(?m)^\s+pull_request:")
        self.assertRegex(self.code, r"(?m)^\s+push:\s*\n\s+branches:\s*\[\s*main\s*\]")

    def test_runs_the_full_unittest_suite(self):
        self.assertIn("python -m pip install -r requirements.txt", self.code)
        self.assertRegex(self.code, r"python -m unittest discover -s tests")

    def test_failures_cannot_be_ignored(self):
        self.assertNotRegex(self.code, r"continue-on-error:\s*true")
        self.assertNotRegex(self.code, r"\|\|\s*(true|exit 0|:)\b")
        self.assertNotIn("--exit-zero", self.code)

    def test_single_required_gate_job_fails_when_tests_fail(self):
        self.assertIn("name: CI Gate", self.code)
        self.assertRegex(self.code, r"needs:\s*unittest")
        self.assertRegex(self.code, r"if:\s*always\(\)")
        self.assertIn('test "${{ needs.unittest.result }}" = "success"', self.code)

    def test_ci_never_needs_a_live_model_or_secret(self):
        self.assertNotIn("secrets.", self.code)
        self.assertRegex(self.code, r'GEMINI_API_KEY:\s*""')
        self.assertRegex(self.code, r'RUN_OLLAMA_SMOKE:\s*"0"')
        self.assertRegex(self.code, r'OLLAMA_HOST:\s*"http://127\.0\.0\.1:9"')

    def test_workflow_has_least_privilege_and_a_timeout(self):
        self.assertRegex(self.code, r"(?m)^permissions:\s*\n\s+contents:\s*read")
        self.assertRegex(self.code, r"timeout-minutes:\s*\d+")


class TestManualApiCheckScript(unittest.TestCase):

    def setUp(self):
        self.script = load_api_script()

    def test_no_placeholder_key_assumptions_left(self):
        source = API_SCRIPT.read_text(encoding="utf-8")
        for placeholder in ("api.key", "YOUR_API_KEY_HERE", "AIza"):
            self.assertNotIn(placeholder, source)
        self.assertIsNone(re.search(r"api_key\s*=\s*['\"][^'\"]+['\"]", source))

    def test_is_not_collected_as_a_test_and_importing_it_has_no_side_effects(self):
        self.assertIs(self.script.__test__, False)
        with patch("urllib.request.urlopen") as urlopen, redirect_stdout(io.StringIO()) as out:
            load_api_script()
        urlopen.assert_not_called()
        self.assertEqual(out.getvalue(), "")

    def test_cloud_check_is_skipped_without_a_key_and_imports_nothing(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "  "}), \
                patch.dict(sys.modules, {"google": None, "google.generativeai": None}):
            result = self.script.check_cloud_api()
        self.assertTrue(result["skipped"])
        self.assertFalse(result["ok"])

    def test_cloud_error_message_never_contains_the_key(self):
        fake_genai = types.ModuleType("google.generativeai")
        fake_genai.configure = MagicMock()
        fake_genai.list_models = MagicMock(side_effect=RuntimeError(f"401 invalid key {FAKE_KEY}"))
        fake_google = types.ModuleType("google")
        fake_google.generativeai = fake_genai
        with patch.dict(sys.modules, {"google": fake_google, "google.generativeai": fake_genai}):
            result = self.script.check_cloud_api(api_key=FAKE_KEY)
        self.assertFalse(result["ok"])
        self.assertFalse(result["skipped"])
        self.assertNotIn(FAKE_KEY, result["error"])
        self.assertIn("***", result["error"])

    def test_ollama_check_lists_models(self):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"models": [{"name": "qwen2.5:7b"}, {"name": "deepseek-coder:6.7b"}]}).encode("utf-8")
        response.__enter__.return_value = response
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            result = self.script.check_ollama(host="http://ollama.test:11434/")
        self.assertTrue(result["ok"])
        self.assertEqual(result["models"], ["deepseek-coder:6.7b", "qwen2.5:7b"])
        self.assertEqual(urlopen.call_args[0][0], "http://ollama.test:11434/api/tags")

    def test_ollama_offline_is_reported_not_raised(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            result = self.script.check_ollama(host="http://127.0.0.1:9")
        self.assertFalse(result["ok"])
        self.assertIn("Connection refused", result["error"])

    def test_main_exit_code_follows_the_local_backend_and_hides_the_key(self):
        offline = {"ok": False, "host": "h", "models": [], "error": "down"}
        online = {"ok": True, "host": "h", "models": ["m"], "error": None}
        cloud = {"ok": False, "skipped": False, "models": [], "error": "masked ***"}
        with patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}), \
                patch.object(self.script, "_load_dotenv"), \
                patch.object(self.script, "check_cloud_api", return_value=cloud):
            for ollama, expected in ((offline, 1), (online, 0)):
                with patch.object(self.script, "check_ollama", return_value=ollama), \
                        redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(self.script.main(), expected)
                self.assertNotIn(FAKE_KEY, out.getvalue())


if __name__ == "__main__":
    unittest.main()
