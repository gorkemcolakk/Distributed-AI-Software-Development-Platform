"""
Sprint 5 (Eren Görkem Çolak): a code task (DATABASE / BACKEND / FRONTEND / TESTING) that answers
SUCCESS without a single file delivered nothing. It must fail over to the next candidate, and if
nobody produces files the task is FAILED instead of COMPLETED. Found in the 24 Nov distributed test:
every worker rejected the token, all tasks fell to Integration, and the run still said 5/5 COMPLETED.
In-process doubles only; no network, no Ollama, no real state.db.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.base_agent import AgentCapabilityProfile, AgentStatus, BaseAgent, TaskResult
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator


class Answering(BaseAgent):
    """Answers SUCCESS; with_files decides whether it actually delivers a file."""

    def __init__(self, agent_id, specialties, with_files, score=80, only_for=None):
        profile = AgentCapabilityProfile(coding_score=score, reasoning_score=score, context_capacity=score,
                                         specialties=list(specialties))
        super().__init__(agent_id=agent_id, name=agent_id.title(), model_name=f"{agent_id}:1b",
                         capability_profile=profile)
        self.with_files = with_files
        self.only_for = only_for  # deliver files only for this category
        self.calls = []

    def execute_task(self, task):
        self.calls.append(task["task_id"])
        self.status = AgentStatus.IDLE
        delivers = self.with_files and (self.only_for is None or task.get("category") == self.only_for)
        files = [{"filename": f"{task['task_id']}.py", "content": "x = 1"}] if delivers else []
        return TaskResult(task_id=task["task_id"], agent_id=self.agent_id, status="SUCCESS",
                          output_artifacts={"files": files}, logs=[], execution_time_seconds=0.0)


def task(task_id, category, deps=()):
    return {"task_id": task_id, "title": f"Task {task_id}", "category": category,
            "description": f"Guard test task {task_id}", "dependencies": list(deps),
            "required_specialty": category.lower()}


def run(agents, tasks):
    evaluator = CapabilityEvaluator()
    for agent in agents:
        evaluator.register_agent(agent)
    orch = MasterOrchestrator(evaluator=evaluator, persist=False)
    orch.analyzer.decompose = lambda text, title: {
        "requirement_id": "req-guard", "project_title": title, "raw_requirement": text,
        "total_tasks": len(tasks), "tasks": [dict(t) for t in tasks]}
    report = orch.process_requirement("guard test", "Guard")
    return report, {r["task_id"]: r for r in report["task_assignments"]}


class TestEmptyOutputGuard(unittest.TestCase):

    def test_empty_success_fails_over_to_an_agent_that_delivers(self):
        empty = Answering("be", ["backend"], with_files=False, score=95)
        real = Answering("spare", ["backend"], with_files=True, score=50)
        report, by_id = run([empty, real], [task("t-be", "BACKEND")])
        self.assertEqual(by_id["t-be"]["status"], "COMPLETED")
        self.assertEqual(by_id["t-be"]["attempted_agents"], ["Be", "Spare"])
        self.assertEqual(by_id["t-be"]["assigned_agent"], "Spare")

    def test_nobody_delivers_files_so_the_task_is_failed_not_completed(self):
        for category in ("DATABASE", "BACKEND", "FRONTEND", "TESTING"):
            with self.subTest(category=category):
                only = Answering("only", [category.lower()], with_files=False)
                report, by_id = run([only], [task("t1", category)])
                self.assertEqual(by_id["t1"]["status"], "FAILED")
                self.assertNotEqual(report["system_status"], "COMPLETED")
                self.assertEqual(report["status_counts"]["COMPLETED"], 0)

    def test_the_failure_says_why(self):
        only = Answering("only", ["backend"], with_files=False)
        _, by_id = run([only], [task("t1", "BACKEND")])
        self.assertIn("CONTRACT_VIOLATION", str(by_id["t1"]))
        self.assertIn("dosya üretmedi", str(by_id["t1"]))

    def test_downstream_of_an_empty_task_is_blocked(self):
        be = Answering("be", ["backend"], with_files=False)
        qa = Answering("qa", ["testing"], with_files=True, only_for="TESTING")
        _, by_id = run([be, qa], [task("t-be", "BACKEND"), task("t-qa", "TESTING", deps=["t-be"])])
        self.assertEqual(by_id["t-be"]["status"], "FAILED")
        self.assertEqual(by_id["t-qa"]["status"], "BLOCKED")
        self.assertNotIn("t-qa", qa.calls)

    def test_integration_without_files_is_still_fine(self):
        be = Answering("be", ["backend"], with_files=True)
        integ = Answering("integ", ["integration"], with_files=False)
        _, by_id = run([be, integ], [task("t-be", "BACKEND"), task("t-int", "INTEGRATION", deps=["t-be"])])
        self.assertEqual(by_id["t-be"]["status"], "COMPLETED")
        self.assertEqual(by_id["t-int"]["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
