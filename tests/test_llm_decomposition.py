"""
S4-07 (Eren Görkem Çolak): the Master model plans the tasks and a shared contract.

The model is replaced by a scripted client (llm_client=...), so nothing here calls Ollama.
Only the "unreachable model" test opens a socket, to a closed local port.
"""

import json
import os
import socket
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.frontend_agent import FrontendAgent
from src.agents.integration_agent import IntegrationAgent
from src.agents.testing_agent import TestingAgent
from src.master.analyzer import MAX_LLM_TASKS, RequirementsAnalyzer
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator

PLAN = {
    "contract": {
        "entities": [
            {"name": "Member", "table": "members", "fields": [{"name": "id", "type": "integer"},
                                                               {"name": "Full Name", "type": "TEXT"}]},
            {"name": "Book", "table": "books", "fields": ["id", "title", "author"]},
        ],
        "endpoints": [
            {"method": "post", "path": "/members", "description": "register a member"},
            {"method": "GET", "path": "/books/search", "description": "search books by title"},
            {"method": "FETCH", "path": "/bad", "description": "unknown method is dropped"},
            {"method": "GET", "path": "no-slash", "description": "bad path is dropped"},
        ],
    },
    "tasks": [
        {"id": "t1", "category": "DATABASE", "title": "Library schema",
         "description": "Tables members and books", "depends_on": []},
        {"id": "t2", "category": "API", "title": "Member and book API",
         "description": "POST /members and GET /books/search", "depends_on": ["t1", "t9", "t2"]},
        {"id": "t3", "category": "UI", "title": "Search page",
         "description": "Register form and book search", "depends_on": []},
        {"id": "t4", "category": "QA", "title": "API tests",
         "description": "Tests for the endpoints", "dependson": []},
    ],
}


def client(answer):
    calls = []

    def _client(prompt):
        calls.append(prompt)
        return answer if isinstance(answer, str) else json.dumps(answer)
    _client.calls = calls
    return _client


def by_id(tasks):
    return {t["task_id"]: t for t in tasks}


class TestDefaultsAndSwitch(unittest.TestCase):

    def test_default_is_the_template_and_never_calls_a_model(self):
        fake = client(PLAN)
        with patch.dict(os.environ, {"MASTER_ANALYZER_USE_OLLAMA": ""}):
            result = RequirementsAnalyzer(llm_client=fake).decompose("Library", "Library")
        self.assertEqual(result["decomposition_mode"], "template")
        self.assertEqual(result["fallback_reason"], "DISABLED")
        self.assertEqual(len(result["tasks"]), 6)
        self.assertIsNone(result["shared_contract"])
        self.assertEqual(fake.calls, [])

    def test_env_switch(self):
        with patch.dict(os.environ, {"MASTER_ANALYZER_USE_OLLAMA": "true"}):
            self.assertTrue(RequirementsAnalyzer().use_llm)
        with patch.dict(os.environ, {"MASTER_ANALYZER_USE_OLLAMA": "false"}):
            self.assertFalse(RequirementsAnalyzer().use_llm)


class TestModelPlan(unittest.TestCase):

    def setUp(self):
        self.fake = client(PLAN)
        self.result = RequirementsAnalyzer(use_llm=True, llm_client=self.fake).decompose(
            "Members register and search books", "Library")
        self.tasks = by_id(self.result["tasks"])

    def test_mode_and_label(self):
        self.assertEqual(self.result["decomposition_mode"], "llm")
        self.assertIsNone(self.result["fallback_reason"])
        self.assertIn("qwen2.5:7b", self.result["decomposition_label"])
        self.assertEqual(len(self.fake.calls), 1)
        self.assertIn("Members register and search books", self.fake.calls[0])

    def test_ids_categories_and_specialties(self):
        self.assertEqual(list(self.tasks), ["task-db-1", "task-be-1", "task-fe-1", "task-qa-1", "task-int-1"])
        self.assertEqual([t["category"] for t in self.result["tasks"]],
                         ["DATABASE", "BACKEND", "FRONTEND", "TESTING", "INTEGRATION"])
        self.assertEqual(self.tasks["task-be-1"]["required_specialty"], "backend")
        self.assertEqual(self.result["total_tasks"], 5)

    def test_dependencies_are_mapped_and_cleaned(self):
        self.assertEqual(self.tasks["task-db-1"]["dependencies"], [])
        self.assertEqual(self.tasks["task-be-1"]["dependencies"], [])  # S5: the contract is enough, runs in parallel
        self.assertEqual(self.tasks["task-fe-1"]["dependencies"], [])  # frontend only needs the contract
        self.assertEqual(self.tasks["task-qa-1"]["dependencies"], ["task-be-1"])  # testing always waits for backend
        self.assertEqual(self.tasks["task-int-1"]["dependencies"],
                         ["task-db-1", "task-be-1", "task-fe-1", "task-qa-1"])

    def test_small_model_rules_are_appended(self):
        self.assertIn("Tables members and books", self.tasks["task-db-1"]["description"])
        self.assertIn("no CHECK constraints", self.tasks["task-db-1"]["description"])
        self.assertIn("shared contract", self.tasks["task-fe-1"]["description"])

    def test_contract_is_normalised(self):
        contract = self.result["shared_contract"]
        self.assertEqual([e["table"] for e in contract["entities"]], ["members", "books"])
        self.assertEqual(contract["entities"][0]["fields"][1], {"name": "full_name", "type": "text"})
        self.assertEqual([f["name"] for f in contract["entities"][1]["fields"]], ["id", "title", "author"])
        self.assertEqual([(e["method"], e["path"]) for e in contract["endpoints"]],
                         [("POST", "/members"), ("GET", "/books/search"),
                          ("POST", "/register"), ("POST", "/login")])  # S5: members -> sign up / log in


class TestOneTaskPerRole(unittest.TestCase):
    """Real qwen2.5:7b answer (19.11.2026): 2 DATABASE + 3 BACKEND + 1 TESTING tasks and no FRONTEND."""

    SPLIT = {"tasks": [
        {"id": "1", "category": "DATABASE", "title": "Create Users Table", "description": "users: id, username", "depends_on": []},
        {"id": "2", "category": "DATABASE", "title": "Create Books Table", "description": "books: id, title", "depends_on": []},
        {"id": "3", "category": "BACKEND", "title": "User Registration", "description": "POST /users", "depends_on": ["1"]},
        {"id": "4", "category": "BACKEND", "title": "Book Search", "description": "GET /books", "depends_on": ["2"]},
        {"id": "5", "category": "BACKEND", "title": "Borrowing", "description": "POST /books/{id}/borrow", "depends_on": ["2"]},
        {"id": "6", "category": "TESTING", "title": "Test Borrowing", "description": "borrow tests", "depends_on": ["5"]},
    ]}

    def setUp(self):
        result = RequirementsAnalyzer(use_llm=True, llm_client=client(self.SPLIT)).decompose("Library", "Library")
        self.assertEqual(result["decomposition_mode"], "llm")
        self.tasks = by_id(result["tasks"])

    def test_same_category_tasks_are_merged(self):
        self.assertEqual(list(self.tasks), ["task-db-1", "task-be-1", "task-fe-1", "task-qa-1", "task-int-1"])
        backend = self.tasks["task-be-1"]
        self.assertEqual(backend["title"], "User Registration + Book Search + Borrowing")
        for part in ("POST /users", "GET /books", "POST /books/{id}/borrow"):
            self.assertIn(part, backend["description"])
        self.assertEqual(backend["dependencies"], [])
        self.assertIn("books: id, title", self.tasks["task-db-1"]["description"])

    def test_missing_role_gets_a_contract_based_task(self):
        frontend = self.tasks["task-fe-1"]
        self.assertEqual(frontend["category"], "FRONTEND")
        self.assertIn("shared contract", frontend["description"])
        self.assertEqual(frontend["dependencies"], [])

    def test_testing_waits_for_the_merged_backend(self):
        self.assertEqual(self.tasks["task-qa-1"]["dependencies"], ["task-be-1"])

    def test_requirements_task_is_dropped_and_its_dependencies_too(self):
        plan = {"tasks": [
            {"id": "r", "category": "REQUIREMENTS", "title": "Define contract", "description": "entities"},
            {"id": "d", "category": "DATABASE", "title": "Schema", "description": "tables", "depends_on": ["r"]},
            {"id": "f", "category": "FRONTEND", "title": "Page", "description": "page", "depends_on": ["r"]},
        ]}
        tasks = by_id(RequirementsAnalyzer(use_llm=True, llm_client=client(plan)).decompose("x", "X")["tasks"])
        self.assertNotIn("task-req-1", tasks)
        self.assertEqual(tasks["task-db-1"]["dependencies"], [])
        self.assertEqual(tasks["task-fe-1"]["dependencies"], [])


class TestUnusableAnswersFallBackToTemplate(unittest.TestCase):

    def _reason(self, answer):
        result = RequirementsAnalyzer(use_llm=True, llm_client=client(answer)).decompose("x", "X")
        self.assertEqual(result["decomposition_mode"], "template")
        self.assertEqual(len(result["tasks"]), 6)
        self.assertIn(result["fallback_reason"], result["decomposition_label"])
        return result["fallback_reason"]

    def test_empty_and_invalid_json(self):
        self.assertEqual(self._reason(""), "EMPTY_RESPONSE")
        self.assertEqual(self._reason("not json at all"), "INVALID_JSON")
        self.assertEqual(self._reason("[1, 2]"), "INVALID_JSON")

    def test_missing_too_few_or_too_many_tasks(self):
        self.assertEqual(self._reason({"contract": {}}), "INVALID_TASKS")
        self.assertEqual(self._reason({"tasks": [{"category": "BACKEND", "title": "Only one"}]}), "INVALID_TASKS")
        many = [{"id": f"t{i}", "category": "BACKEND", "title": f"T{i}", "description": "d"}
                for i in range(MAX_LLM_TASKS + 1)]
        self.assertEqual(self._reason({"tasks": many}), "INVALID_TASKS")

    def test_unknown_categories_are_skipped(self):
        tasks = [{"id": "a", "category": "MARKETING", "title": "Ads"},
                 {"id": "b", "category": "BACKEND", "title": "API"}]
        self.assertEqual(self._reason({"tasks": tasks}), "INVALID_TASKS")

    def test_cycle_between_contract_tasks_is_dissolved(self):
        # S5: DATABASE / BACKEND / FRONTEND drop their dependencies, so a model cycle among them cannot survive
        tasks = [{"id": "a", "category": "DATABASE", "title": "Schema", "depends_on": ["b"]},
                 {"id": "b", "category": "BACKEND", "title": "API", "depends_on": ["a"]}]
        result = RequirementsAnalyzer(use_llm=True, llm_client=client({"tasks": tasks})).decompose("x", "X")
        self.assertEqual(result["decomposition_mode"], "llm")
        deps = {t["task_id"]: t["dependencies"] for t in result["tasks"]}
        self.assertEqual(deps["task-db-1"], [])
        self.assertEqual(deps["task-be-1"], [])

    def test_unreachable_model(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        result = RequirementsAnalyzer(use_llm=True, host=f"http://127.0.0.1:{port}", timeout=3).decompose("x", "X")
        self.assertEqual(result["decomposition_mode"], "template")
        self.assertIn(result["fallback_reason"], ("CONNECTION_REFUSED", "TIMEOUT"))

    def test_contract_without_entities_or_endpoints_is_none(self):
        self.assertIsNone(RequirementsAnalyzer.normalize_contract({"entities": [], "endpoints": []}))
        self.assertIsNone(RequirementsAnalyzer.normalize_contract("nope"))


class TestEngineUsesThePlan(unittest.TestCase):

    def setUp(self):
        agents = [IntegrationAgent(use_llm=False), FrontendAgent(use_ollama=False), BackendAgent(use_ollama=False),
                  DatabaseAgent(use_ollama=False), TestingAgent(use_ollama=False)]
        analyzer = RequirementsAnalyzer(use_llm=True, llm_client=client(PLAN))
        self.orch = MasterOrchestrator(evaluator=CapabilityEvaluator(agents), persist=False, analyzer=analyzer)
        self.report = self.orch.process_requirement("Members register and search books", "Library")

    def test_report_carries_the_plan_the_engine_ran(self):
        plan = self.report["decomposition"]
        self.assertEqual(plan["mode"], "llm")
        planned = [t["task_id"] for t in plan["tasks"]]
        self.assertEqual(planned, ["task-db-1", "task-be-1", "task-fe-1", "task-qa-1", "task-int-1"])
        self.assertEqual(sorted(t["task_id"] for t in self.report["task_assignments"]), sorted(planned))
        self.assertEqual(self.report["status_counts"]["COMPLETED"], 5)

    def test_every_agent_gets_the_same_contract(self):
        sent = {e["task_id"]: e["context_artifacts"].get("shared_contract") for e in self.orch.dispatched_envelopes}
        self.assertEqual(set(sent), {"task-db-1", "task-be-1", "task-fe-1", "task-qa-1", "task-int-1"})
        contracts = list(sent.values())
        self.assertTrue(all(c == contracts[0] for c in contracts))
        self.assertEqual(contracts[0]["entities"][1]["table"], "books")

    def test_template_run_reports_template(self):
        orch = MasterOrchestrator(evaluator=CapabilityEvaluator([BackendAgent(use_ollama=False)]), persist=False)
        plan = orch.process_requirement("x", "X")["decomposition"]
        self.assertEqual((plan["mode"], plan["fallback_reason"], plan["shared_contract"]), ("template", "DISABLED", None))


if __name__ == "__main__":
    unittest.main()
