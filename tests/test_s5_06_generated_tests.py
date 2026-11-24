"""
S5-06 (Berat İnan) test findings of 24 November:
1. Generated tests may call only the endpoints of the shared contract.
2. The pass rate of the generated tests is measured and stored as a benchmark metric.

No Ollama and no real state.db: model replies are scripted and the backend is hand-written.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.testing_agent import (
    TestingAgent,
    contract_endpoints,
    find_endpoint_calls,
    find_off_contract_calls,
    path_matches,
)
from src.master import db_manager, generated_tests

CONTRACT = {
    "entities": [{"name": "Book", "table": "books", "fields": ["title", "author"]}],
    "endpoints": [
        {"method": "POST", "path": "/books", "request": ["title", "author"], "response": "Book"},
        {"method": "GET", "path": "/books", "request": [], "response": "list of Book"},
        {"method": "GET", "path": "/books/{book_id}", "request": [], "response": "Book"},
        {"method": "DELETE", "path": "/books/{book_id}", "request": [], "response": "ok"},
    ],
}
TASK = {
    "task_id": "task-qa-s5",
    "title": "API tests",
    "description": "Test the main endpoints of the shared contract.",
    "category": "TESTING",
    "context_artifacts": {"shared_contract": CONTRACT},
}

IN_CONTRACT = '''```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").status_code == 200

def test_create_and_get():
    book_id = client.post("/books", json={"title": "a", "author": "b"}).json()["id"]
    assert client.get(f"/books/{book_id}").status_code == 200

def test_delete():
    assert client.request("DELETE", "/books/1").status_code in (200, 404)
```'''

OFF_CONTRACT = '''```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_list():
    assert client.get("/api/v1/books").status_code == 200

def test_update():
    assert client.put("/books/1", json={"title": "x"}).status_code == 200
```'''


def scripted(*replies):
    calls = []

    def client(prompt):
        calls.append(prompt)
        return replies[min(len(calls), len(replies)) - 1]

    client.calls = calls
    return client


class TestContractEndpointCheck(unittest.TestCase):

    def test_contract_endpoints_are_read_from_context(self):
        self.assertEqual(contract_endpoints({"shared_contract": CONTRACT})[0], ("POST", "/books"))
        self.assertEqual(contract_endpoints({}), [])
        self.assertEqual(contract_endpoints(None), [])

    def test_path_templates(self):
        self.assertTrue(path_matches("/books/{book_id}", "/books/1"))
        self.assertTrue(path_matches("/books/{book_id}", "/books/{}"))
        self.assertTrue(path_matches("/books", "/books?author=x"))
        self.assertFalse(path_matches("/books/{book_id}", "/books"))
        self.assertFalse(path_matches("/books", "/authors"))

    def test_calls_are_found_in_get_post_request_and_fstrings(self):
        calls = find_endpoint_calls(IN_CONTRACT.strip("`").replace("python\n", "", 1))
        self.assertIn(("GET", "/health"), calls)
        self.assertIn(("POST", "/books"), calls)
        self.assertIn(("GET", "/books/{}"), calls)
        self.assertIn(("DELETE", "/books/1"), calls)

    def test_off_contract_paths_and_methods_are_reported(self):
        code = OFF_CONTRACT.strip("`").replace("python\n", "", 1)
        off = find_off_contract_calls(code, contract_endpoints({"shared_contract": CONTRACT}))
        self.assertEqual(off, ["GET /api/v1/books", "PUT /books/1"])  # wrong path, method not in contract

    def test_health_is_always_allowed(self):
        self.assertEqual(find_off_contract_calls('client.get("/health")', []), [])


class TestTestingAgentContract(unittest.TestCase):

    def test_prompt_lists_contract_endpoints(self):
        prompt = TestingAgent(use_ollama=True, llm_client=scripted(IN_CONTRACT)).build_prompt(TASK)
        self.assertIn("ONLY these endpoints", prompt)
        self.assertIn("- GET /books/{book_id}", prompt)
        self.assertIn("- DELETE /books/{book_id}", prompt)

    def test_in_contract_reply_is_accepted(self):
        client = scripted(IN_CONTRACT)
        result = TestingAgent(use_ollama=True, llm_client=client).execute_task(TASK)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(client.calls), 1)
        art = result.output_artifacts
        self.assertTrue(art["contract_checked"])
        self.assertEqual(art["validation_retries"], 0)
        self.assertIn("POST /books", art["endpoints_called"])

    def test_off_contract_reply_is_retried_with_the_reason(self):
        client = scripted(OFF_CONTRACT, IN_CONTRACT)
        result = TestingAgent(use_ollama=True, llm_client=client).execute_task(TASK)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(client.calls), 2)
        self.assertIn("REJECTED", client.calls[1])
        self.assertIn("GET /api/v1/books", client.calls[1])
        self.assertEqual(result.output_artifacts["validation_retries"], 1)

    def test_off_contract_reply_fails_task_after_retries(self):
        client = scripted(OFF_CONTRACT)
        result = TestingAgent(use_ollama=True, llm_client=client).execute_task(TASK)
        self.assertEqual(result.status, "FAILED")
        self.assertIn("sözleşmede olmayan", result.error_message)
        self.assertEqual(len(client.calls), 2)

    def test_without_contract_no_endpoint_check(self):
        task = dict(TASK, context_artifacts={})
        result = TestingAgent(use_ollama=True, llm_client=scripted(OFF_CONTRACT)).execute_task(task)
        self.assertEqual(result.status, "SUCCESS")
        self.assertFalse(result.output_artifacts["contract_checked"])

    def test_retry_count_comes_from_env(self):
        client = scripted(OFF_CONTRACT)
        with patch.dict(os.environ, {"TESTING_AGENT_VALIDATION_RETRIES": "0"}):
            result = TestingAgent(use_ollama=True, llm_client=client).execute_task(TASK)
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(len(client.calls), 1)


BACKEND = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "HEALTHY"}

@app.get("/books")
def books():
    return []
'''

TESTS = '''
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").status_code == 200

def test_books_empty():
    assert client.get("/books").json() == []

def test_wrong_expectation():
    assert client.get("/books").json() == [1]

def test_skipped():
    import pytest
    pytest.skip("not counted")
'''


@unittest.skipUnless(__import__("importlib").util.find_spec("pytest"), "pytest is needed to run generated tests")
class TestGeneratedTestPassRate(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s5-06-")
        self.ws = Path(self.tmp) / "ws"
        (self.ws / "backend").mkdir(parents=True)
        (self.ws / "tests").mkdir()
        (self.ws / "backend" / "main.py").write_text(BACKEND, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pass_rate_counts_passed_over_executed(self):
        (self.ws / "tests" / "test_api.py").write_text(TESTS, encoding="utf-8")
        result = generated_tests.run_generated_tests(self.ws)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual((result["passed"], result["failed"], result["skipped"], result["total"]), (2, 1, 1, 3))
        self.assertAlmostEqual(result["pass_rate"], 0.6667, places=4)
        self.assertIn("2/3", result["reason"])
        self.assertFalse((self.ws / "app.db").exists() or (self.ws / ".pytest_cache").exists())

    def test_all_passing_is_passed(self):
        (self.ws / "tests" / "test_api.py").write_text(
            TESTS.split("def test_wrong_expectation")[0], encoding="utf-8")
        result = generated_tests.run_generated_tests(self.ws)
        self.assertEqual(result["status"], "PASSED")
        self.assertEqual(result["pass_rate"], 1.0)

    def test_import_error_counts_as_failed_test(self):
        (self.ws / "tests" / "test_api.py").write_text("from missing_module import app\n\ndef test_x():\n    assert app\n",
                                                       encoding="utf-8")
        result = generated_tests.run_generated_tests(self.ws)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["pass_rate"], 0.0)
        self.assertGreaterEqual(result["errors"], 1)

    def test_no_tests_is_skipped(self):
        self.assertEqual(generated_tests.run_generated_tests(self.ws)["status"], "SKIPPED")
        self.assertEqual(generated_tests.run_generated_tests(None)["status"], "SKIPPED")


class TestPassRateBenchmarkStorage(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s5-06-db-")
        self.db = os.path.join(self.tmp, "state.db")
        db_manager.init_db(self.db, verbose=False, recover_stale=False)
        for run_id in ("r1", "r2", "r3", "r4"):
            db_manager.create_run(run_id, "p", db_path=self.db)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pass_rates_are_grouped_per_model(self):
        save = db_manager.save_generated_test_result
        save("r1", {"status": "PASSED", "passed": 3, "total": 3, "pass_rate": 1.0}, "deepseek-coder:6.7b", db_path=self.db)
        save("r2", {"status": "FAILED", "passed": 1, "failed": 2, "total": 3, "pass_rate": 0.3333},
             "deepseek-coder:6.7b", db_path=self.db)
        save("r3", {"status": "FAILED", "passed": 0, "errors": 1, "total": 1, "pass_rate": 0.0}, "qwen2.5-coder:3b",
             db_path=self.db)
        save("r4", {"status": "SKIPPED", "total": 0, "pass_rate": None}, "qwen2.5-coder:3b", db_path=self.db)

        rates = {r["model_used"]: r for r in db_manager.get_generated_test_pass_rates(self.db)}
        self.assertEqual(rates["deepseek-coder:6.7b"]["runs"], 2)
        self.assertEqual(rates["deepseek-coder:6.7b"]["fully_passed_runs"], 1)
        self.assertAlmostEqual(rates["deepseek-coder:6.7b"]["pass_rate"], 4 / 6, places=4)
        self.assertAlmostEqual(rates["deepseek-coder:6.7b"]["avg_run_pass_rate"], 0.6667, places=4)
        self.assertEqual(rates["qwen2.5-coder:3b"]["runs"], 1)  # SKIPPED run is not a measurement
        self.assertEqual(rates["qwen2.5-coder:3b"]["pass_rate"], 0.0)
        self.assertEqual(db_manager.get_generated_test_result("r1", self.db)["passed"], 3)

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValueError):
            db_manager.save_generated_test_result("r1", {"status": "MAYBE"}, db_path=self.db)


class TestOrchestratorReportsPassRate(unittest.TestCase):

    def test_off_by_default(self):
        from src.master.orchestrator import MasterOrchestrator
        with patch.dict(os.environ, {"MASTER_SMOKE_TEST": "false"}):
            report = MasterOrchestrator(persist=False).process_requirement("Small app", "Small")
        self.assertIsNone(report["generated_tests"])

    def test_on_result_is_in_report_and_db(self):
        from src.master.orchestrator import MasterOrchestrator
        tmp = tempfile.mkdtemp(prefix="s5-06-orch-")
        try:
            db = os.path.join(tmp, "state.db")
            fake = {"status": "FAILED", "reason": "1/2 test geçti", "passed": 1, "failed": 1, "errors": 0,
                    "skipped": 0, "total": 2, "pass_rate": 0.5, "cases": []}
            with patch.dict(os.environ, {"MASTER_SMOKE_TEST": "true"}), \
                    patch("src.master.smoke_test.run_smoke_test", return_value={"status": "SKIPPED", "checks": []}), \
                    patch("src.master.generated_tests.run_generated_tests", return_value=dict(fake)):
                orch = MasterOrchestrator(db_path=db, workspace_root=os.path.join(tmp, "ws"), write_artifacts=True)
                report = orch.process_requirement("Small app", "Small")
            self.assertEqual(report["generated_tests"]["pass_rate"], 0.5)
            stored = db_manager.get_generated_test_result(report["run_id"], db)
            self.assertEqual((stored["passed"], stored["total"], stored["pass_rate"]), (1, 2, 0.5))
            self.assertEqual(stored["model_used"], report["generated_tests"]["model_used"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
