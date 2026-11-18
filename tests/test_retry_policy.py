"""
S4-01 (Eren Görkem Çolak): bounded retry on the same agent for TRANSIENT failures
(remote TIMEOUT / UNREACHABLE), straight failover for PERMANENT ones.

Agents here are scripted doubles; no network, no Ollama, no real state.db.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.base_agent import AgentCapabilityProfile, AgentStatus, BaseAgent, TaskResult
from src.master import db_manager
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator
from src.master.retry_policy import (
    PERMANENT,
    TRANSIENT,
    RetryPolicy,
    classify_failure,
    failure_code,
)


def remote_failure(code, message="worker problem"):
    """A failed TaskResult shaped like RemoteAgentProxy's (error contract + "[CODE]" prefix)."""
    return TaskResult(
        task_id="t", agent_id="remote", status="FAILED",
        output_artifacts={"error_contract": {"error_code": code, "message": message}},
        logs=[], execution_time_seconds=0.0, error_message=f"[{code}] {message}",
    )


class ScriptedAgent(BaseAgent):
    """Answers each call with the next item of `script`: an error code (str) fails, None succeeds."""

    def __init__(self, agent_id, name, score, script=(), specialties=("backend",)):
        profile = AgentCapabilityProfile(coding_score=score, reasoning_score=score,
                                         context_capacity=score, specialties=list(specialties))
        super().__init__(agent_id=agent_id, name=name, model_name=f"{agent_id}:1b",
                         capability_profile=profile)
        self.script = list(script)
        self.calls = []

    def execute_task(self, task):
        self.calls.append(task["task_id"])
        outcome = self.script.pop(0) if self.script else None
        if outcome is None:
            self.status = AgentStatus.IDLE
            return TaskResult(task_id=task["task_id"], agent_id=self.agent_id, status="SUCCESS",
                              output_artifacts={"files": []}, logs=[], execution_time_seconds=0.0)
        self.status = AgentStatus.ERROR
        if outcome == "CRASH":  # local agent exception (BaseAgent turns it into a plain message)
            return TaskResult(task_id=task["task_id"], agent_id=self.agent_id, status="FAILED",
                              output_artifacts={}, logs=[], execution_time_seconds=0.0,
                              error_message="ollama timeout while generating")
        return remote_failure(outcome)


def task(task_id, deps=()):
    return {"task_id": task_id, "title": f"Task {task_id}", "category": "BACKEND",
            "description": f"Retry test task {task_id}",
            "dependencies": list(deps), "required_specialty": "backend"}


def orchestrator(agents, tasks, policy=RetryPolicy(max_retries=1, backoff_seconds=3.0), **kwargs):
    evaluator = CapabilityEvaluator()
    for agent in agents:
        evaluator.register_agent(agent)
    sleeps = []
    kwargs.setdefault("persist", False)
    orch = MasterOrchestrator(evaluator=evaluator, retry_policy=policy, sleep=sleeps.append, **kwargs)
    orch.analyzer.decompose = lambda text, title: {
        "requirement_id": "req-s4-01", "project_title": title, "raw_requirement": text,
        "total_tasks": len(tasks), "tasks": [dict(t) for t in tasks]}
    return orch, sleeps


def run(orch):
    report = orch.process_requirement("retry test", "Retry")
    return report, {t["task_id"]: t for t in report["task_assignments"]}


class TestClassification(unittest.TestCase):

    def test_remote_timeout_and_unreachable_are_transient(self):
        for code in ("TIMEOUT", "UNREACHABLE"):
            with self.subTest(code=code):
                self.assertEqual(classify_failure(remote_failure(code)), TRANSIENT)
                self.assertEqual(failure_code(remote_failure(code)), code)

    def test_other_worker_errors_are_permanent(self):
        for code in ("UNAUTHORIZED", "INVALID_PAYLOAD", "EXECUTION_ERROR", "DUPLICATE_TASK",
                     "UNSAFE_PATH", "CONTRACT_VIOLATION"):
            with self.subTest(code=code):
                self.assertEqual(classify_failure(remote_failure(code)), PERMANENT)

    def test_code_prefix_alone_is_enough(self):
        result = TaskResult(task_id="t", agent_id="a", status="FAILED", output_artifacts={},
                            logs=[], execution_time_seconds=0.0, error_message="[UNREACHABLE] no route")
        self.assertEqual(classify_failure(result), TRANSIENT)

    def test_local_exception_text_is_not_guessed_as_transient(self):
        result = TaskResult(task_id="t", agent_id="a", status="FAILED", output_artifacts={},
                            logs=[], execution_time_seconds=0.0, error_message="ollama timeout (local)")
        self.assertIsNone(failure_code(result))
        self.assertEqual(classify_failure(result), PERMANENT)

    def test_unknown_code_and_missing_message_are_permanent(self):
        self.assertEqual(classify_failure(None, "[SOMETHING_NEW] x"), PERMANENT)
        self.assertEqual(classify_failure(None, None), PERMANENT)


class TestRetryPolicySettings(unittest.TestCase):

    def test_env_settings_and_defaults(self):
        with patch.dict(os.environ, {"MASTER_MAX_RETRIES": "3", "MASTER_RETRY_BACKOFF": "0.5"}):
            self.assertEqual(RetryPolicy.from_env(), RetryPolicy(3, 0.5))
        with patch.dict(os.environ, {"MASTER_MAX_RETRIES": "abc", "MASTER_RETRY_BACKOFF": ""}):
            self.assertEqual(RetryPolicy.from_env(), RetryPolicy(1, 2.0))

    def test_negative_values_are_clamped_and_backoff_is_linear(self):
        policy = RetryPolicy(max_retries=-2, backoff_seconds=-1)
        self.assertEqual((policy.max_retries, policy.backoff_seconds), (0, 0.0))
        self.assertEqual([RetryPolicy(2, 1.5).delay_for(n) for n in (1, 2)], [1.5, 3.0])


class TestBoundedRetry(unittest.TestCase):

    def test_transient_failure_is_retried_on_the_same_agent(self):
        primary = ScriptedAgent("primary", "Primary", 90, script=["TIMEOUT", None])
        backup = ScriptedAgent("backup", "Backup", 60)
        orch, sleeps = orchestrator([primary, backup], [task("t1")])

        report, by_id = run(orch)

        self.assertEqual(by_id["t1"]["status"], "COMPLETED")
        self.assertEqual(by_id["t1"]["assigned_agent"], "Primary")
        self.assertEqual(by_id["t1"]["attempted_agents"], ["Primary", "Primary"])
        self.assertEqual(backup.calls, [])
        self.assertEqual(sleeps, [3.0])
        self.assertEqual(report["system_status"], "COMPLETED")

    def test_permanent_failure_goes_straight_to_the_next_agent(self):
        primary = ScriptedAgent("primary", "Primary", 90, script=["UNAUTHORIZED"])
        backup = ScriptedAgent("backup", "Backup", 60)
        orch, sleeps = orchestrator([primary, backup], [task("t1")])

        _, by_id = run(orch)

        self.assertEqual(by_id["t1"]["attempted_agents"], ["Primary", "Backup"])
        self.assertEqual(by_id["t1"]["assigned_agent"], "Backup")
        self.assertEqual(sleeps, [])

    def test_local_agent_exception_is_not_retried(self):
        primary = ScriptedAgent("primary", "Primary", 90, script=["CRASH"])
        backup = ScriptedAgent("backup", "Backup", 60)
        orch, sleeps = orchestrator([primary, backup], [task("t1")])

        _, by_id = run(orch)

        self.assertEqual(by_id["t1"]["attempted_agents"], ["Primary", "Backup"])
        self.assertEqual(sleeps, [])

    def test_retries_are_bounded_then_the_task_fails_over(self):
        primary = ScriptedAgent("primary", "Primary", 90, script=["TIMEOUT", "TIMEOUT", "TIMEOUT"])
        backup = ScriptedAgent("backup", "Backup", 60)
        orch, sleeps = orchestrator([primary, backup], [task("t1")],
                                    policy=RetryPolicy(max_retries=2, backoff_seconds=1.0))

        _, by_id = run(orch)

        self.assertEqual(by_id["t1"]["attempted_agents"], ["Primary", "Primary", "Primary", "Backup"])
        self.assertEqual(by_id["t1"]["assigned_agent"], "Backup")
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_zero_retries_means_plain_failover(self):
        primary = ScriptedAgent("primary", "Primary", 90, script=["TIMEOUT"])
        backup = ScriptedAgent("backup", "Backup", 60)
        orch, sleeps = orchestrator([primary, backup], [task("t1")],
                                    policy=RetryPolicy(max_retries=0, backoff_seconds=1.0))

        _, by_id = run(orch)

        self.assertEqual(by_id["t1"]["attempted_agents"], ["Primary", "Backup"])
        self.assertEqual(sleeps, [])

    def test_worker_that_only_timed_out_still_gets_later_tasks(self):
        primary = ScriptedAgent("primary", "Primary", 90, script=["TIMEOUT", "TIMEOUT", None])
        backup = ScriptedAgent("backup", "Backup", 60)
        orch, _ = orchestrator([primary, backup], [task("t1"), task("t2")])

        _, by_id = run(orch)

        self.assertEqual(by_id["t1"]["assigned_agent"], "Backup")
        self.assertEqual(by_id["t2"]["attempted_agents"], ["Primary"])
        self.assertEqual(by_id["t2"]["assigned_agent"], "Primary")

    def test_unreachable_worker_is_not_used_again_in_the_same_run(self):
        primary = ScriptedAgent("primary", "Primary", 90, script=["UNREACHABLE", "UNREACHABLE"])
        backup = ScriptedAgent("backup", "Backup", 60)
        orch, _ = orchestrator([primary, backup], [task("t1"), task("t2")])

        _, by_id = run(orch)

        self.assertEqual(by_id["t1"]["attempted_agents"], ["Primary", "Primary", "Backup"])
        self.assertEqual(by_id["t2"]["attempted_agents"], ["Backup"])
        self.assertEqual(primary.status, AgentStatus.ERROR)

    def test_every_retry_is_stored_as_its_own_attempt_row(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = os.path.join(tmp.name, "state.db")
        primary = ScriptedAgent("primary", "Primary", 90, script=["TIMEOUT", "TIMEOUT"])
        backup = ScriptedAgent("backup", "Backup", 60)
        orch, _ = orchestrator([primary, backup], [task("t1")], persist=True, db_path=db_path,
                               workspace_root=os.path.join(tmp.name, "workspaces"))

        report, _ = run(orch)
        attempts = db_manager.get_attempts_for_task(report["run_id"], "t1", db_path=db_path)

        self.assertEqual([a["attempt_no"] for a in attempts], [1, 2, 3])
        self.assertEqual([a["agent_name"] for a in attempts], ["Primary", "Primary", "Backup"])
        self.assertEqual([a["is_successful"] for a in attempts], [0, 0, 1])
        self.assertTrue(attempts[0]["error_message"].startswith("[TIMEOUT]"))


if __name__ == "__main__":
    unittest.main()
