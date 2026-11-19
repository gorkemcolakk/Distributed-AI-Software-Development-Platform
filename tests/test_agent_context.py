"""
What the Master sends to each worker: short context (small models stay inside their timeout),
but the Testing task still sees the code it tests, and the Requirements task is done by a real agent.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.frontend_agent import FrontendAgent
from src.agents.integration_agent import IntegrationAgent
from src.agents.testing_agent import TestingAgent
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import (
    MasterOrchestrator,
    TEST_CONTEXT_MAX_CHARS,
    TEST_CONTEXT_MAX_FILES,
    code_excerpts_for_testing,
)


class TestCodeExcerpts(unittest.TestCase):

    def test_only_python_modules_and_not_test_files(self):
        files = {
            "backend_task_be_1.py": "def add(a, b):\n    return a + b\n",
            "test_task_qa_1.py": "def test_x():\n    assert True\n",
            "database/schema.sql": "CREATE TABLE t (id INTEGER);",
            "ui.html": "<html></html>",
        }
        self.assertEqual(list(code_excerpts_for_testing(files)), ["backend_task_be_1.py"])

    def test_long_files_are_cut_and_file_count_is_limited(self):
        files = {f"mod_{i}.py": "x = 1\n" * 1000 for i in range(5)}
        excerpts = code_excerpts_for_testing(files)
        self.assertEqual(len(excerpts), TEST_CONTEXT_MAX_FILES)
        for text in excerpts.values():
            self.assertTrue(text.endswith("# ... (truncated)"))
            self.assertLessEqual(len(text), TEST_CONTEXT_MAX_CHARS + len("\n# ... (truncated)"))

    def test_empty_input(self):
        self.assertEqual(code_excerpts_for_testing({}), {})


class TestDispatchedContext(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_ws = os.environ.get("WORKSPACE_ROOT")
        os.environ["WORKSPACE_ROOT"] = self._tmp.name
        agents = [
            IntegrationAgent(use_llm=False),
            FrontendAgent(use_ollama=False),
            BackendAgent(use_ollama=False),
            DatabaseAgent(use_ollama=False),
            TestingAgent(use_ollama=False),
        ]
        self.orch = MasterOrchestrator(evaluator=CapabilityEvaluator(agents), persist=False)
        self.report = self.orch.process_requirement("Library system: members borrow books", "Library")
        self.sent = {e["task_id"]: e for e in self.orch.dispatched_envelopes}

    def tearDown(self):
        if self._old_ws is None:
            os.environ.pop("WORKSPACE_ROOT", None)
        else:
            os.environ["WORKSPACE_ROOT"] = self._old_ws
        self._tmp.cleanup()

    def test_run_completes(self):
        self.assertEqual(self.report["status_counts"]["COMPLETED"], 6)

    def test_requirements_task_gets_no_fake_artifacts(self):
        req = self.sent["task-req-1"]
        self.assertNotIn("output_artifacts", req)
        self.assertNotIn("requirements_spec.md", json.dumps(req, default=str))

    def test_testing_task_sees_backend_code_excerpt(self):
        ctx = self.sent["task-qa-1"]["context_artifacts"]
        self.assertIn("code_under_test", ctx)
        self.assertTrue(any(p.endswith(".py") for p in ctx["code_under_test"]))
        self.assertFalse(any(p.rsplit("/", 1)[-1].startswith("test_") for p in ctx["code_under_test"]))

    def test_upstream_context_carries_file_names_not_full_code(self):
        ctx = self.sent["task-fe-1"]["context_artifacts"]
        self.assertIsInstance(ctx.get("generated_files"), list)
        for art in (ctx.get("upstream_artifacts") or {}).values():
            self.assertNotIn("files", art)

    def test_integration_task_still_gets_full_files(self):
        art = self.sent["task-int-1"].get("output_artifacts") or {}
        self.assertTrue(art)
        self.assertTrue(all(isinstance(v, str) and v for v in art.values()))


class TestConfigArchitectureOwner(unittest.TestCase):

    def test_backend_owns_architecture_and_keeps_its_specialties(self):
        path = os.path.join(os.path.dirname(__file__), "..", "config", "agents_config.json")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        agents = raw["agents"] if isinstance(raw, dict) and "agents" in raw else raw
        backend = next(a for a in agents if a.get("agent_id", a.get("id")) == "agent-backend")
        for s in ("backend", "api", "fastapi", "rest_services", "architecture"):
            self.assertIn(s, backend["specialties"])


if __name__ == "__main__":
    unittest.main()
