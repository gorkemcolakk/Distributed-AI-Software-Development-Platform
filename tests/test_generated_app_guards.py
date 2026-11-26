"""
Sprint 5 (Eren Görkem Çolak): guards from the 26-27 Nov distributed tests.

- A remote worker whose model failed answers SUCCESS with its canned template (backend /api/v1/items);
  that is a failure, retried once on the same worker, then failed over.
- A remote FRONTEND result without an .html page (the backend worker wrote a .py) is a failure.
- The planner may write "User" as the /login response; the contract always says "token", and the
  backend rule asks for a Bearer token, plain-dict responses and an imported FileResponse.
- Integration gets a longer HTTP timeout than the other workers.
In-process doubles only; no network, no Ollama, no real state.db.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.base_agent import AgentCapabilityProfile, AgentStatus, BaseAgent, TaskResult
from src.agents.remote_agent import RemoteAgentProxy
from src.master.analyzer import CATEGORY_RULES, RequirementsAnalyzer
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator
from src.master.retry_policy import RetryPolicy


class Worker(BaseAgent):
    """Plays a worker; `answers` is the list of (mode, filename) it returns call after call."""

    def __init__(self, agent_id, specialties, answers, score=80, remote=True):
        profile = AgentCapabilityProfile(coding_score=score, reasoning_score=score, context_capacity=score,
                                         specialties=list(specialties))
        super().__init__(agent_id=agent_id, name=agent_id.title(), model_name=f"{agent_id}:1b",
                         capability_profile=profile)
        if remote:
            self.endpoint_url = f"http://100.64.0.1/{agent_id}"
        self.answers = list(answers)
        self.calls = 0

    def execute_task(self, task):
        mode, filename = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        self.status = AgentStatus.IDLE
        artifacts = {"files": [{"filename": filename, "content": "x = 1"}], "generation_mode": mode}
        if mode != "ollama":
            artifacts["fallback_reason"] = "MODEL_OUTPUT_ERROR"
        return TaskResult(task_id=task["task_id"], agent_id=self.agent_id, status="SUCCESS",
                          output_artifacts=artifacts, logs=[], execution_time_seconds=0.0)


def task(task_id, category):
    return {"task_id": task_id, "title": f"Task {task_id}", "category": category,
            "description": f"Guard test task {task_id}", "dependencies": [],
            "required_specialty": category.lower()}


def run(agents, tasks, max_retries=1):
    evaluator = CapabilityEvaluator()
    for agent in agents:
        evaluator.register_agent(agent)
    orch = MasterOrchestrator(evaluator=evaluator, persist=False,
                              retry_policy=RetryPolicy(max_retries=max_retries, backoff_seconds=0.0),
                              sleep=lambda s: None)
    orch.analyzer.decompose = lambda text, title: {
        "requirement_id": "req-guard", "project_title": title, "raw_requirement": text,
        "total_tasks": len(tasks), "tasks": [dict(t) for t in tasks]}
    report = orch.process_requirement("guard test", "Guard")
    return report, {r["task_id"]: r for r in report["task_assignments"]}


class TestFallbackTemplateGuard(unittest.TestCase):

    def test_template_answer_is_retried_on_the_same_worker(self):
        be = Worker("be", ["backend"], [("safe_fallback", "backend.py"), ("ollama", "backend.py")])
        _, by_id = run([be], [task("t-be", "BACKEND")])
        self.assertEqual(by_id["t-be"]["status"], "COMPLETED")
        self.assertEqual(be.calls, 2)
        self.assertEqual(by_id["t-be"]["attempted_agents"], ["Be", "Be"])

    def test_template_every_time_fails_over_then_fails(self):
        be = Worker("be", ["backend"], [("safe_fallback", "backend.py")], score=95)
        spare = Worker("spare", ["backend"], [("ollama", "backend.py")], score=50)
        _, by_id = run([be, spare], [task("t-be", "BACKEND")])
        self.assertEqual(by_id["t-be"]["status"], "COMPLETED")
        self.assertEqual(by_id["t-be"]["assigned_agent"], "Spare")

        only = Worker("only", ["backend"], [("fallback", "backend.py")])
        report, by_id = run([only], [task("t-be", "BACKEND")])
        self.assertEqual(by_id["t-be"]["status"], "FAILED")
        self.assertIn("yedek şablon", str(by_id["t-be"]))
        self.assertNotEqual(report["system_status"], "COMPLETED")

    def test_local_agent_in_fallback_mode_is_still_accepted(self):
        # Without workers (CI, Ollama off) the local agents' labelled fallback keeps the demo running
        local = Worker("local", ["backend"], [("safe_fallback", "backend.py")], remote=False)
        _, by_id = run([local], [task("t-be", "BACKEND")])
        self.assertEqual(by_id["t-be"]["status"], "COMPLETED")


class TestFrontendPageGuard(unittest.TestCase):

    def test_remote_frontend_result_without_html_fails_over(self):
        wrong = Worker("be", ["frontend"], [("ollama", "backend_task_fe_1.py")], score=95)
        right = Worker("fe", ["frontend"], [("ollama", "ui_task_fe_1.html")], score=50)
        _, by_id = run([wrong, right], [task("t-fe", "FRONTEND")])
        self.assertEqual(by_id["t-fe"]["status"], "COMPLETED")
        self.assertEqual(by_id["t-fe"]["assigned_agent"], "Fe")
        self.assertEqual(by_id["t-fe"]["attempted_agents"], ["Be", "Fe"])

        only = Worker("be", ["frontend"], [("ollama", "backend_task_fe_1.py")])
        _, by_id = run([only], [task("t-fe", "FRONTEND")])
        self.assertEqual(by_id["t-fe"]["status"], "FAILED")
        self.assertIn("HTML sayfası üretmedi", str(by_id["t-fe"]))

    def test_html_page_is_accepted(self):
        fe = Worker("fe", ["frontend"], [("ollama", "pages/index.HTML")])
        _, by_id = run([fe], [task("t-fe", "FRONTEND")])
        self.assertEqual(by_id["t-fe"]["status"], "COMPLETED")


class TestBackendContractRules(unittest.TestCase):

    def test_login_response_is_always_a_token(self):
        contract = RequirementsAnalyzer.normalize_contract({
            "entities": [{"name": "User", "table": "users", "fields": ["username", "password"]}],
            "endpoints": [{"method": "POST", "path": "/login", "request": ["username", "password"],
                           "response": "User"},
                          {"method": "POST", "path": "/api/auth/login", "response": "User"}]})
        responses = {ep["path"]: ep.get("response") for ep in contract["endpoints"]}
        self.assertEqual(responses["/login"], "token")
        self.assertEqual(responses["/api/auth/login"], "token")
        self.assertEqual(responses["/register"], "User")

    def test_backend_rule_covers_the_26_nov_bugs(self):
        rule = CATEGORY_RULES["BACKEND"]
        self.assertIn("Authorization: Bearer", rule)       # no fixed fake user on protected endpoints
        self.assertIn("never Model(id=..., **item.dict())", rule)  # /register 500
        self.assertIn("import FileResponse from fastapi.responses", rule)
        self.assertIn('/login returns {"token": ...}', rule)


class TestIntegrationTimeout(unittest.TestCase):

    def _proxy(self, agent_id, **kw):
        return RemoteAgentProxy(endpoint_url="http://100.64.0.1:8005", agent_id=agent_id, auth_token="t", **kw)

    def test_integration_waits_longer_than_other_workers(self):
        with patch.dict(os.environ, {"WORKER_HTTP_TIMEOUT": "180"}, clear=False):
            os.environ.pop("WORKER_HTTP_TIMEOUT_INTEGRATION", None)
            self.assertEqual(self._proxy("agent-integration").timeout, 300.0)
            self.assertEqual(self._proxy("agent-backend").timeout, 180.0)
        with patch.dict(os.environ, {"WORKER_HTTP_TIMEOUT": "180", "WORKER_HTTP_TIMEOUT_INTEGRATION": "240"}):
            self.assertEqual(self._proxy("agent-integration").timeout, 240.0)
        self.assertEqual(self._proxy("agent-integration", timeout=50).timeout, 50.0)  # explicit value wins


if __name__ == "__main__":
    unittest.main()
