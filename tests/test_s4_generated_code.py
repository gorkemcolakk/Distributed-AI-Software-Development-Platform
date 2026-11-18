"""
S4-06 (Testing & QA): tests that run the code the worker agents generate.

Sorumlu: Berat İnan (Testing & QA Agent - deepseek-coder:6.7b)

Checking that an agent "returned SUCCESS" is not enough; these tests take the files
the agents actually produce and exercise them:
- generated FastAPI backend: imported and called through TestClient,
- generated SQLite schema: executed in an in-memory database (tables, FK, CHECK),
- generated HTML page: parsed for balanced tags and a title,
- a TestingAgent suite returned by a (mocked) model: executed and must pass,
- a full pipeline run: every file written to workspaces/{run_id}/ must be valid.

All agents run with use_ollama=False or with an injected fake LLM client,
so no local model, API key or network connection is required.
"""

import ast
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.frontend_agent import FrontendAgent
from src.agents.integration_agent import IntegrationAgent
from src.agents.testing_agent import TestingAgent
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator

try:
    from fastapi.testclient import TestClient
except ImportError:  # httpx missing
    TestClient = None

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "source", "track", "wbr"}


def generated_files(agent, category, task_id="t-gen-1", title="Library API"):
    result = agent.execute_task({"task_id": task_id, "title": title, "category": category,
                                 "description": "S4-06 generated code check"})
    assert result.status == "SUCCESS", result.error_message
    return {f.get("filename") or f.get("path"): f["content"]
            for f in (result.output_artifacts or {}).get("files", [])}


def load_module(name, source):
    """Imports generated source as a throwaway module (registered so pydantic can resolve it)."""
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(source, f"<generated {name}>", "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


class TagBalanceChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.title = [], [], ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_TAGS:
            self.stack.append(tag)
        self._in_title = tag == "title"

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack})")
        else:
            self.stack.pop()
        self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def check_html(source):
    checker = TagBalanceChecker()
    checker.feed(source)
    checker.close()
    return checker


def assert_schema_runs(test, sql):
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(sql)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        test.assertGreater(len(tables), 0, "generated schema created no tables")
        test.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        return tables
    finally:
        conn.close()


@unittest.skipIf(TestClient is None, "fastapi.testclient için httpx gerekli (requirements.txt)")
class TestGeneratedBackendService(unittest.TestCase):
    """The BackendAgent output is a working FastAPI app, not just parsable text."""

    def setUp(self):
        files = generated_files(BackendAgent(use_ollama=False), "BACKEND")
        self.assertEqual(len(files), 1)
        (self.path, source), = files.items()
        self.assertTrue(self.path.endswith(".py"))
        self.module_name = "s4_generated_backend"
        self.module = load_module(self.module_name, source)
        self.client = TestClient(self.module.app)

    def tearDown(self):
        sys.modules.pop(self.module_name, None)

    def test_health_endpoint_reports_healthy(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "HEALTHY")

    def test_item_lifecycle_create_read_delete(self):
        created = self.client.post("/api/v1/items", json={"name": "Dune"})
        self.assertEqual(created.status_code, 201)
        item_id = created.json()["id"]

        fetched = self.client.get(f"/api/v1/items/{item_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["name"], "Dune")
        self.assertIn(item_id, [i["id"] for i in self.client.get("/api/v1/items").json()])

        self.assertEqual(self.client.delete(f"/api/v1/items/{item_id}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/items/{item_id}").status_code, 404)

    def test_invalid_input_is_rejected_with_422(self):
        self.assertEqual(self.client.post("/api/v1/items", json={"name": ""}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/items", json={}).status_code, 422)

    def test_unknown_item_returns_404_not_500(self):
        response = self.client.get("/api/v1/items/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("does-not-exist", response.json()["detail"])


class TestGeneratedDatabaseSchema(unittest.TestCase):
    """The DatabaseAgent output executes in SQLite and its constraints hold."""

    def setUp(self):
        files = generated_files(DatabaseAgent(use_ollama=False), "DATABASE")
        self.sql = next(content for path, content in files.items() if path.endswith(".sql"))

    def test_schema_executes_and_is_idempotent(self):
        tables = assert_schema_runs(self, self.sql)
        self.assertGreaterEqual(len(tables), 1)
        # CREATE ... IF NOT EXISTS: running the migration twice must not fail
        assert_schema_runs(self, self.sql + "\n" + self.sql)

    def test_foreign_keys_and_check_constraints_are_enforced(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(self.sql)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"users", "projects"} <= tables:
                self.skipTest("Şema users/projects tablolarını içermiyor; yalnızca çalıştırma testi geçerli.")

            conn.execute("INSERT INTO users (id, email, display_name) VALUES (1, 'a@example.com', 'A')")
            conn.execute("INSERT INTO projects (id, owner_id, title) VALUES (1, 1, 'P')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO projects (owner_id, title) VALUES (999, 'orphan')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO users (email, display_name) VALUES ('a@example.com', 'dup')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO projects (owner_id, title, status) VALUES (1, 'x', 'BOGUS')")

            conn.execute("DELETE FROM users WHERE id = 1")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 0)
        finally:
            conn.close()


class TestGeneratedFrontendPage(unittest.TestCase):

    def test_html_is_well_formed_and_has_a_title(self):
        files = generated_files(FrontendAgent(use_ollama=False), "FRONTEND", title="Library UI")
        html_files = {p: c for p, c in files.items() if p.endswith(".html")}
        self.assertTrue(html_files)
        for path, source in html_files.items():
            checker = check_html(source)
            self.assertEqual(checker.errors, [], path)
            self.assertEqual(checker.stack, [], f"{path}: unclosed tags")
            self.assertEqual(checker.title.strip(), "Library UI")
            self.assertTrue(source.lstrip().lower().startswith("<!doctype html>"))

    def test_checker_catches_broken_markup(self):
        checker = check_html("<html><body><main><p>x</main></body></html>")
        self.assertTrue(checker.errors)


class TestGeneratedTestSuiteRuns(unittest.TestCase):
    """A suite returned by the Testing Agent's model is executed, not only parsed."""

    MODEL_REPLY = '''Here is the suite:
```python
def slugify(text):
    return "-".join(text.lower().split())

def test_normal():
    assert slugify("Hello World") == "hello-world"

def test_invalid():
    try:
        slugify(None)
    except AttributeError:
        pass
    else:
        assert False, "None must raise"

def test_edge():
    assert slugify("") == ""
```'''

    def test_generated_suite_is_valid_and_every_test_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = TestingAgent(use_ollama=True, output_dir=tmp, llm_client=lambda prompt: self.MODEL_REPLY)
            result = agent.execute_task({"task_id": "task-qa-1", "title": "QA", "category": "TESTING",
                                         "description": "Write tests"})

            self.assertEqual(result.status, "SUCCESS", result.error_message)
            self.assertEqual(result.output_artifacts["generation_mode"], "ollama")
            self.assertEqual(result.output_artifacts["test_function_count"], 3)
            written = Path(result.output_artifacts["written_path"])
            self.assertTrue(written.is_file())
            self.assertTrue(written.resolve().is_relative_to(Path(tmp).resolve()))

            module = load_module("s4_generated_suite", written.read_text(encoding="utf-8"))
            try:
                tests = [getattr(module, n) for n in dir(module) if n.startswith("test_")]
                self.assertEqual(len(tests), 3)
                for test_fn in tests:
                    with self.subTest(test=test_fn.__name__):
                        test_fn()
            finally:
                sys.modules.pop("s4_generated_suite", None)

    def test_unparsable_model_suite_fails_the_task_instead_of_being_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = TestingAgent(use_ollama=True, output_dir=tmp,
                                 llm_client=lambda prompt: "```python\ndef test_x(:\n    assert True\n```")
            result = agent.execute_task({"task_id": "task-qa-1", "title": "QA", "category": "TESTING"})

            self.assertEqual(result.status, "FAILED")
            self.assertIn("satır", result.error_message)
            self.assertEqual(list(Path(tmp).rglob("*.py")), [])


class TestPipelineOutputsAreValid(unittest.TestCase):
    """End to end: every file the pipeline writes to workspaces/{run_id}/ passes its checker."""

    def test_all_written_files_pass_syntax_schema_and_markup_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = CapabilityEvaluator()
            for agent in (FrontendAgent(use_ollama=False), BackendAgent(use_ollama=False),
                          DatabaseAgent(use_ollama=False), TestingAgent(use_ollama=False),
                          IntegrationAgent(workspace_root=tmp)):
                evaluator.register_agent(agent)
            orchestrator = MasterOrchestrator(evaluator=evaluator, persist=False,
                                              workspace_root=os.path.join(tmp, "workspaces"))

            report = orchestrator.process_requirement("Library system with books and loans", "Library")

            self.assertEqual(report["system_status"], "COMPLETED")
            run_dir = Path(report["workspace_path"])
            written = sorted(p for p in run_dir.rglob("*") if p.is_file())
            self.assertTrue(written, "pipeline wrote no files")
            suffixes = {p.suffix for p in written}
            self.assertTrue({".py", ".sql", ".html"} <= suffixes, suffixes)

            for path in written:
                source = path.read_text(encoding="utf-8")
                rel = path.relative_to(run_dir).as_posix()
                with self.subTest(file=rel):
                    self.assertTrue(path.resolve().is_relative_to(run_dir.resolve()))
                    self.assertTrue(source.strip(), "empty generated file")
                    if path.suffix == ".py":
                        ast.parse(source, filename=rel)
                        compile(source, rel, "exec")
                    elif path.suffix == ".sql":
                        assert_schema_runs(self, source)
                    elif path.suffix in (".html", ".htm"):
                        checker = check_html(source)
                        self.assertEqual((checker.errors, checker.stack), ([], []))

            # Every file the agents reported is on disk, and the integration review approved them
            reported = {f for r in report["task_assignments"] for f in r["output_files"]}
            self.assertEqual(reported, {p.relative_to(run_dir).as_posix() for p in written})
            integration = next(r for r in report["task_assignments"] if r["task_id"] == "task-int-1")
            self.assertEqual(integration["status"], "COMPLETED")
            review = next(r.output_artifacts for r in orchestrator.execution_history
                          if r.task_id == "task-int-1")
            self.assertEqual(review["status"], "APPROVED")
            self.assertEqual(review["conflicts_detected"], [])


if __name__ == "__main__":
    unittest.main()
