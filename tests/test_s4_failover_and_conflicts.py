"""
S4-06 (Testing & QA): deterministic, mock-based tests for task reassignment,
honest FAILED/BLOCKED reporting, SQLite attempt history and file path conflicts.

Sorumlu: Berat İnan (Testing & QA Agent - deepseek-coder:6.7b)

No test here needs Ollama, a cloud API key or the network:
- worker agents are WorkerDouble test doubles (real BaseAgent subclasses),
- the requirement analyzer is replaced by a fixed task list per test,
- SQLite and workspaces live in a temporary directory.

These tests lock in the failover behaviour that S4-01 (retry / reassignment),
S4-04 (conflicts / attempt history) and S4-05 (integration review) build on,
so a change that breaks it fails the CI quality gate before merge.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.base_agent import AgentCapabilityProfile, AgentStatus, BaseAgent, TaskCategory
from src.agents.integration_agent import IntegrationAgent
from src.master import db_manager
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator


class WorkerDouble(BaseAgent):
    """Configurable worker: fixed score, status, failures and output files per task."""

    def __init__(self, agent_id, name, score=60.0, specialties=("backend",),
                 status=AgentStatus.IDLE, fail_on=(), files=None,
                 error="simulated worker failure"):
        profile = AgentCapabilityProfile(
            coding_score=score, reasoning_score=score, context_capacity=score,
            specialties=list(specialties),
        )
        super().__init__(agent_id=agent_id, name=name, model_name=f"{agent_id}:1b",
                         capability_profile=profile)
        self.status = status
        # "ALL" fails every task; a category name (e.g. "INTEGRATION") fails that category
        self.fail_on = set(fail_on) if fail_on != "ALL" else "ALL"
        self.files = files or {}
        self.error = error
        self.executed = []

    def _process(self, task, logs):
        task_id = task.get("task_id")
        self.executed.append(task_id)
        if self.fail_on == "ALL" or task_id in self.fail_on or task.get("category") in self.fail_on:
            raise RuntimeError(f"{self.error} ({self.name} / {task_id})")
        return {"status": "DONE", "files": [dict(f) for f in self.files.get(task_id, [])]}


def make_task(task_id, category="BACKEND", deps=(), specialty="backend"):
    return {
        "task_id": task_id,
        "title": f"Task {task_id}",
        "category": category,
        "description": f"Deterministic test task {task_id}",
        "dependencies": list(deps),
        "required_specialty": specialty,
    }


def build_orchestrator(agents, tasks, **kwargs):
    """Orchestrator whose analyzer always returns `tasks` (no LLM, no randomness)."""
    evaluator = CapabilityEvaluator()
    for agent in agents:
        evaluator.register_agent(agent)
    kwargs.setdefault("persist", False)
    orchestrator = MasterOrchestrator(evaluator=evaluator, **kwargs)
    orchestrator.analyzer.decompose = lambda text, title: {
        "requirement_id": "req-s4-06",
        "project_title": title,
        "raw_requirement": text,
        "total_tasks": len(tasks),
        "tasks": [dict(t) for t in tasks],
    }
    return orchestrator


def run(orchestrator):
    report = orchestrator.process_requirement("S4-06 deterministic requirement", "S4-06 Test")
    return report, {r["task_id"]: r for r in report["task_assignments"]}


class TestReassignmentToAlternativeAgent(unittest.TestCase):
    """S4-01 checklist 1-2: a failed task moves to the best *available* alternative agent."""

    def test_failed_task_goes_to_next_best_idle_agent_and_skips_unavailable_ones(self):
        primary = WorkerDouble("primary", "Primary", score=90, fail_on="ALL")
        busy = WorkerDouble("busy", "Busy", score=95, status=AgentStatus.BUSY)
        offline = WorkerDouble("offline", "Offline", score=99, status=AgentStatus.OFFLINE)
        backup_low = WorkerDouble("backup-low", "Backup Low", score=60)
        backup_high = WorkerDouble("backup-high", "Backup High", score=70)
        orch = build_orchestrator([primary, busy, offline, backup_low, backup_high], [make_task("t1")])

        report, by_id = run(orch)

        record = by_id["t1"]
        self.assertEqual(record["status"], "COMPLETED")
        self.assertEqual(record["attempted_agents"], ["Primary", "Backup High"])
        self.assertEqual(record["assigned_agent"], "Backup High")
        self.assertEqual(record["fit_score"],
                         backup_high.capabilities.calculate_fit_score(TaskCategory.BACKEND))
        # Unavailable agents are never handed the task, whatever their score
        self.assertEqual(busy.executed, [])
        self.assertEqual(offline.executed, [])
        # Failover stops at the first success
        self.assertEqual(backup_low.executed, [])
        self.assertEqual(report["system_status"], "COMPLETED")

    def test_agent_that_errored_is_not_tried_again_for_later_tasks_in_the_same_run(self):
        primary = WorkerDouble("primary", "Primary", score=90, fail_on="ALL")
        backup = WorkerDouble("backup", "Backup", score=60)
        orch = build_orchestrator([primary, backup], [make_task("t1"), make_task("t2")])

        _, by_id = run(orch)

        self.assertEqual(by_id["t1"]["attempted_agents"], ["Primary", "Backup"])
        self.assertEqual(by_id["t2"]["attempted_agents"], ["Backup"])
        self.assertEqual(primary.executed, ["t1"])
        self.assertEqual(primary.status, AgentStatus.ERROR)

    def test_unsafe_output_path_counts_as_failed_attempt_and_task_is_reassigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspaces"
            escaping = WorkerDouble("escaper", "Escaper", score=90,
                                    files={"t1": [{"filename": "../../escape.py", "content": "x = 1\n"}]})
            safe = WorkerDouble("safe", "Safe", score=60,
                                files={"t1": [{"filename": "app/service.py", "content": "x = 2\n"}]})
            orch = build_orchestrator([escaping, safe], [make_task("t1")], workspace_root=str(root))

            report, by_id = run(orch)

            record = by_id["t1"]
            self.assertEqual(record["status"], "COMPLETED")
            self.assertEqual(record["attempted_agents"], ["Escaper", "Safe"])
            self.assertEqual(record["output_files"], ["app/service.py"])
            run_dir = Path(report["workspace_path"])
            self.assertEqual((run_dir / "app" / "service.py").read_text(encoding="utf-8"), "x = 2\n")
            # Nothing was written outside the run workspace
            self.assertFalse((Path(tmp) / "escape.py").exists())
            self.assertFalse((root / "escape.py").exists())

    def test_failover_order_is_deterministic_across_runs(self):
        primary = WorkerDouble("primary", "Primary", score=90, fail_on="ALL")
        second = WorkerDouble("second", "Second", score=80, fail_on="ALL")
        third = WorkerDouble("third", "Third", score=70)
        orch = build_orchestrator([primary, second, third], [make_task("t1")])

        first_report, first = run(orch)
        second_report, again = run(orch)  # ERROR agents are reset to IDLE before each run

        self.assertNotEqual(first_report["run_id"], second_report["run_id"])
        self.assertEqual(first["t1"]["attempted_agents"], ["Primary", "Second", "Third"])
        self.assertEqual(again["t1"]["attempted_agents"], first["t1"]["attempted_agents"])
        self.assertEqual(again["t1"]["assigned_agent"], "Third")


class TestHonestFailureReporting(unittest.TestCase):
    """S4-01 checklist 3-4: no hidden failures, dependants stay BLOCKED."""

    def test_task_is_reported_failed_when_no_eligible_alternative_exists(self):
        only = WorkerDouble("only", "Only Worker", score=80, fail_on="ALL", error="model returned garbage")
        offline = WorkerDouble("offline", "Offline", score=99, status=AgentStatus.OFFLINE)
        orch = build_orchestrator([only, offline], [make_task("t1")])

        report, by_id = run(orch)

        record = by_id["t1"]
        self.assertEqual(record["status"], "FAILED")
        self.assertEqual(record["agent_result_status"], "FAILED")
        self.assertEqual(record["attempted_agents"], ["Only Worker"])
        self.assertIn("model returned garbage", record["reason"])
        self.assertEqual(record["output_files"], [])
        self.assertEqual(report["system_status"], "FAILED")
        self.assertEqual(report["status_counts"]["FAILED"], 1)
        self.assertEqual(report["status_counts"]["COMPLETED"], 0)

    def test_failed_task_blocks_its_whole_downstream_chain_without_executing_it(self):
        worker = WorkerDouble("worker", "Worker", score=80, fail_on={"t1"})
        tasks = [
            # Independent task listed first: once the worker fails t1 it is in ERROR
            # status for the rest of the run, so t4 must be dispatched before t1.
            make_task("t4"),
            make_task("t1"),
            make_task("t2", deps=["t1"]),
            make_task("t3", deps=["t2"]),
        ]
        orch = build_orchestrator([worker], tasks)

        report, by_id = run(orch)

        self.assertEqual(by_id["t1"]["status"], "FAILED")
        self.assertEqual(by_id["t2"]["status"], "BLOCKED")
        self.assertEqual(by_id["t3"]["status"], "BLOCKED")
        self.assertEqual(by_id["t4"]["status"], "COMPLETED")
        self.assertIn("'t1', durum FAILED", by_id["t2"]["reason"])
        self.assertIn("'t2', durum BLOCKED", by_id["t3"]["reason"])
        self.assertEqual(sorted(worker.executed), ["t1", "t4"])
        dispatched = {e["task_id"] for e in orch.dispatched_envelopes}
        self.assertNotIn("t2", dispatched)
        self.assertNotIn("t3", dispatched)
        self.assertEqual(report["system_status"], "PARTIALLY_COMPLETED")
        self.assertEqual(report["status_counts"],
                         {"COMPLETED": 1, "FAILED": 1, "UNASSIGNED": 0, "BLOCKED": 2})

    def test_every_task_ends_in_exactly_one_terminal_status(self):
        worker = WorkerDouble("worker", "Worker", score=80, fail_on={"t2"})
        tasks = [make_task("t1"), make_task("t2", deps=["t1"]), make_task("t3", deps=["t2"]),
                 make_task("t4", category="FRONTEND", specialty="frontend", deps=["t1"])]
        orch = build_orchestrator([worker], tasks)

        report, by_id = run(orch)

        self.assertEqual(sorted(by_id), ["t1", "t2", "t3", "t4"])
        self.assertEqual(report["total_tasks_processed"], len(tasks))
        self.assertEqual(sum(report["status_counts"].values()), len(tasks))


class TestAttemptHistoryPersistence(unittest.TestCase):
    """S4-04 checklist 2: every attempt (number, agent, error) is stored in SQLite."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "state.db")
        self.workspace_root = os.path.join(self.tmp.name, "workspaces")

    def tearDown(self):
        self.tmp.cleanup()

    def _orchestrator(self, agents, tasks):
        return build_orchestrator(agents, tasks, persist=True, db_path=self.db_path,
                                  workspace_root=self.workspace_root)

    def test_reassigned_task_stores_one_row_per_attempt_in_order(self):
        primary = WorkerDouble("primary", "Primary", score=90, fail_on="ALL", error="ollama timeout")
        backup = WorkerDouble("backup", "Backup", score=60)
        report, _ = run(self._orchestrator([primary, backup], [make_task("t1")]))

        attempts = db_manager.get_attempts_for_task(report["run_id"], "t1", db_path=self.db_path)

        self.assertEqual([a["attempt_no"] for a in attempts], [1, 2])
        self.assertEqual([a["agent_name"] for a in attempts], ["Primary", "Backup"])
        self.assertEqual([a["agent_id"] for a in attempts], ["primary", "backup"])
        self.assertEqual([a["is_successful"] for a in attempts], [0, 1])
        self.assertIn("ollama timeout", attempts[0]["error_message"])
        self.assertIsNone(attempts[1]["error_message"])

        task_row = db_manager.get_tasks_for_run(report["run_id"], db_path=self.db_path)[0]
        self.assertEqual(task_row["status"], "COMPLETED")
        self.assertEqual(task_row["assigned_agent_name"], "Backup")
        self.assertEqual(json.loads(task_row["attempted_agents"]), ["Primary", "Backup"])

    def test_failed_task_is_persisted_as_failed_with_all_unsuccessful_attempts(self):
        first = WorkerDouble("first", "First", score=90, fail_on="ALL")
        second = WorkerDouble("second", "Second", score=60, fail_on="ALL")
        report, _ = run(self._orchestrator([first, second], [make_task("t1"), make_task("t2", deps=["t1"])]))

        attempts = db_manager.get_attempts_for_task(report["run_id"], "t1", db_path=self.db_path)
        rows = {r["task_id"]: r for r in db_manager.get_tasks_for_run(report["run_id"], db_path=self.db_path)}

        self.assertEqual([a["is_successful"] for a in attempts], [0, 0])
        self.assertTrue(all(a["error_message"] for a in attempts))
        self.assertEqual(rows["t1"]["status"], "FAILED")
        self.assertEqual(rows["t2"]["status"], "BLOCKED")
        # A BLOCKED task never reached an agent, so it has no attempt rows
        self.assertEqual(db_manager.get_attempts_for_task(report["run_id"], "t2", db_path=self.db_path), [])
        self.assertEqual(db_manager.get_run(report["run_id"], db_path=self.db_path)["system_status"], "FAILED")

    def test_attempt_history_of_separate_runs_does_not_mix(self):
        primary = WorkerDouble("primary", "Primary", score=90, fail_on="ALL")
        backup = WorkerDouble("backup", "Backup", score=60)
        orch = self._orchestrator([primary, backup], [make_task("t1")])

        first, _ = run(orch)
        second, _ = run(orch)

        for report in (first, second):
            attempts = db_manager.get_attempts_for_task(report["run_id"], "t1", db_path=self.db_path)
            self.assertEqual([a["attempt_no"] for a in attempts], [1, 2])


class TestFilePathConflictDetection(unittest.TestCase):
    """S4-04 checklist 1 / S4-05: the same target path from two agents is a reported conflict."""

    def _pipeline(self, backend_files, frontend_files):
        # Workers fail INTEGRATION tasks so that only the real IntegrationAgent can review them
        backend = WorkerDouble("be", "Backend Double", score=80, specialties=["backend"],
                               fail_on={"INTEGRATION"}, files={"t-be": backend_files})
        frontend = WorkerDouble("fe", "Frontend Double", score=80, specialties=["frontend"],
                                fail_on={"INTEGRATION"}, files={"t-fe": frontend_files})
        integration = IntegrationAgent(workspace_root=tempfile.gettempdir())
        tasks = [
            make_task("t-be"),
            make_task("t-fe", category="FRONTEND", specialty="frontend"),
            make_task("t-int", category="INTEGRATION", specialty="integration", deps=["t-be", "t-fe"]),
        ]
        orch = build_orchestrator([backend, frontend, integration], tasks)
        report, by_id = run(orch)
        envelope = next(e for e in orch.dispatched_envelopes if e["task_id"] == "t-int")
        review = next(r.output_artifacts for r in orch.execution_history
                      if r.agent_id == integration.agent_id)
        return report, by_id, envelope, review

    def test_two_agents_writing_the_same_path_are_reported_as_conflict(self):
        _, by_id, envelope, review = self._pipeline(
            backend_files=[{"filename": "app/main.py", "content": "API = 1\n"}],
            frontend_files=[{"filename": "app/main.py", "content": "UI = 1\n"}],
        )

        self.assertEqual(envelope["artifact_sources"]["app/main.py"],
                         ["Backend Double", "Frontend Double"])
        self.assertEqual(review["status"], "REJECTED")
        self.assertEqual(review["conflicts_detected"], ["app/main.py"])
        conflict = next(f for f in review["findings"] if f["file_path"] == "app/main.py")
        self.assertEqual(conflict["severity"], "CRITICAL")
        self.assertIn("Backend Double", conflict["issue"])
        self.assertIn("Frontend Double", conflict["issue"])
        # The conflicting package is not approved behind the user's back
        self.assertEqual(by_id["t-int"]["status"], "FAILED")
        self.assertEqual(by_id["t-int"]["attempted_agents"][0], "Integration Agent")
        self.assertIsNone(review["package_path"])

    def test_windows_and_posix_spellings_of_one_path_still_collide(self):
        _, _, envelope, review = self._pipeline(
            backend_files=[{"filename": "app\\main.py", "content": "API = 1\n"}],
            frontend_files=[{"filename": "./app/main.py", "content": "UI = 1\n"}],
        )

        self.assertEqual(list(envelope["output_artifacts"]), ["app/main.py"])
        self.assertEqual(review["conflicts_detected"], ["app/main.py"])
        self.assertEqual(review["status"], "REJECTED")

    def test_distinct_paths_are_not_conflicts_and_review_approves(self):
        _, by_id, envelope, review = self._pipeline(
            backend_files=[{"filename": "app/api.py", "content": "def health():\n    return 'ok'\n"}],
            frontend_files=[{"filename": "ui/index.html", "content": "<html><body>ok</body></html>"}],
        )

        self.assertEqual(sorted(envelope["output_artifacts"]), ["app/api.py", "ui/index.html"])
        self.assertEqual(review["conflicts_detected"], [])
        self.assertEqual(review["status"], "APPROVED")
        self.assertEqual(by_id["t-int"]["status"], "COMPLETED")
        self.assertEqual(by_id["t-int"]["assigned_agent"], "Integration Agent")

    def test_syntax_error_in_generated_code_is_rejected_with_file_and_line(self):
        _, by_id, _, review = self._pipeline(
            backend_files=[{"filename": "app/api.py", "content": "def broken(:\n    pass\n"}],
            frontend_files=[{"filename": "ui/index.html", "content": "<html></html>"}],
        )

        self.assertEqual(review["status"], "REJECTED")
        finding = next(f for f in review["findings"] if f["file_path"] == "app/api.py")
        self.assertEqual(finding["severity"], "CRITICAL")
        self.assertIn("Satır 1", finding["issue"])
        self.assertEqual(by_id["t-int"]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
