"""
Unit Tests for SQLite Persistence Layer (S2-07).
"""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.base_agent import BaseAgent, AgentCapabilityProfile
from src.agents.frontend_agent import FrontendAgent
from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.testing_agent import TestingAgent
from src.agents.integration_agent import IntegrationAgent
from src.master import db_manager
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator


class AlwaysFailingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="agent-fail-1",
            name="Failing Agent",
            model_name="qwen2.5-coder:7b",
            capability_profile=AgentCapabilityProfile(90, 90, 90, ["architecture"]),
        )

    def _process(self, task, logs):
        raise RuntimeError("simulated LLM failure")


class TestDbManager(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "state_test.db")

    def tearDown(self):
        self.tmp.cleanup()

    # --- (3) First-run table creation -------------------------------------
    def test_init_db_creates_all_tables_on_fresh_file(self):
        self.assertFalse(os.path.exists(self.db_path))
        db_manager.init_db(self.db_path, verbose=False)
        self.assertTrue(os.path.exists(self.db_path))
        self.assertEqual(db_manager.verify_schema(self.db_path),
                         {t: True for t in db_manager.EXPECTED_TABLES})

    def test_init_db_is_idempotent(self):
        db_manager.init_db(self.db_path, verbose=False)
        db_manager.init_db(self.db_path, verbose=False)
        self.assertTrue(all(db_manager.verify_schema(self.db_path).values()))

    def test_legacy_sprint1_schema_is_migrated(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, description TEXT NOT NULL, status TEXT)")
        conn.execute("CREATE TABLE agents (name TEXT PRIMARY KEY, status TEXT)")
        conn.commit()
        conn.close()

        db_manager.init_db(self.db_path, verbose=False)
        conn = sqlite3.connect(self.db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        task_cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)")]
        conn.close()
        self.assertIn("tasks_legacy_v1", tables)
        self.assertIn("agents_legacy_v1", tables)
        self.assertIn("run_id", task_cols)

    # --- (1) Schema: agent profiles + run_id + new statuses ----------------
    def test_schema_columns(self):
        db_manager.init_db(self.db_path, verbose=False)
        conn = sqlite3.connect(self.db_path)
        agent_cols = {r[1] for r in conn.execute("PRAGMA table_info(agents)")}
        task_cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        conn.close()
        self.assertTrue({"coding_score", "reasoning_score", "context_capacity",
                         "specialties", "provenance", "model_name"} <= agent_cols)
        self.assertTrue({"run_id", "status", "agent_result_status", "reason"} <= task_cols)

    # --- (2) COMPLETED guard ----------------------------------------------
    def _seed_run(self, run_id="run-test"):
        db_manager.init_db(self.db_path, verbose=False)
        db_manager.create_run(run_id, "Test", db_path=self.db_path)
        return run_id

    def test_python_guard_rejects_failed_result_as_completed(self):
        run_id = self._seed_run()
        bad = {"task_id": "t1", "status": "COMPLETED", "agent_result_status": "FAILED",
               "assigned_agent": "X"}
        with self.assertRaises(ValueError):
            db_manager.save_task_result(run_id, {}, bad, db_path=self.db_path)

    def test_python_guard_rejects_unassigned_completed(self):
        run_id = self._seed_run()
        bad = {"task_id": "t1", "status": "COMPLETED", "agent_result_status": None,
               "assigned_agent": None}
        with self.assertRaises(ValueError):
            db_manager.save_task_result(run_id, {}, bad, db_path=self.db_path)

    def test_db_check_rejects_raw_completed_insert(self):
        run_id = self._seed_run()
        conn = db_manager.get_connection(self.db_path)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO tasks (run_id, task_id, status, agent_result_status) "
                         "VALUES (?, 't1', 'COMPLETED', 'FAILED')", (run_id,))
        conn.close()

    def test_trigger_blocks_failed_to_completed_transition(self):
        run_id = self._seed_run()
        db_manager.save_task_result(
            run_id, {}, {"task_id": "t1", "status": "BLOCKED", "assigned_agent": None},
            db_path=self.db_path)
        conn = db_manager.get_connection(self.db_path)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE tasks SET status='COMPLETED', agent_result_status='SUCCESS', "
                         "assigned_agent_name='X' WHERE run_id=? AND task_id='t1'", (run_id,))
        conn.close()

    # --- End-to-end orchestrator persistence ------------------------------
    def test_orchestrator_persists_successful_run(self):
        evaluator = CapabilityEvaluator([FrontendAgent(), BackendAgent(), DatabaseAgent(),
                                         TestingAgent(use_ollama=False), IntegrationAgent()])
        orch = MasterOrchestrator(evaluator=evaluator, db_path=self.db_path)
        result = orch.process_requirement("Library system", "Library")

        run = db_manager.get_run(result["run_id"], self.db_path)
        self.assertEqual(run["system_status"], result["system_status"])
        tasks = db_manager.get_tasks_for_run(result["run_id"], self.db_path)
        self.assertEqual(len(tasks), result["total_tasks_processed"])
        for t in tasks:
            if t["status"] == "COMPLETED":
                self.assertEqual(t["agent_result_status"], "SUCCESS")

        conn = db_manager.get_connection(self.db_path)
        n_agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        conn.close()
        self.assertEqual(n_agents, 5)

    def test_orchestrator_never_persists_failed_or_blocked_as_completed(self):
        evaluator = CapabilityEvaluator([AlwaysFailingAgent()])
        orch = MasterOrchestrator(evaluator=evaluator, db_path=self.db_path)
        result = orch.process_requirement("Anything", "Failing Project")

        tasks = {t["task_id"]: t for t in db_manager.get_tasks_for_run(result["run_id"], self.db_path)}
        self.assertNotIn("COMPLETED", {t["status"] for t in tasks.values()})
        self.assertEqual(tasks["task-req-1"]["status"], "FAILED")
        self.assertTrue(any(t["status"] == "BLOCKED" for t in tasks.values()))

        attempts = db_manager.get_attempts_for_task(result["run_id"], "task-req-1", self.db_path)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["is_successful"], 0)
        self.assertIn("simulated LLM failure", attempts[0]["error_message"])

        run = db_manager.get_run(result["run_id"], self.db_path)
        self.assertEqual(run["system_status"], "FAILED")
        self.assertEqual(run["completed_count"], 0)

    def test_consecutive_runs_are_isolated(self):
        evaluator = CapabilityEvaluator([FrontendAgent(), BackendAgent(), DatabaseAgent(),
                                         TestingAgent(use_ollama=False), IntegrationAgent()])
        orch = MasterOrchestrator(evaluator=evaluator, db_path=self.db_path)
        r1 = orch.process_requirement("A", "A")
        r2 = orch.process_requirement("B", "B")
        self.assertNotEqual(r1["run_id"], r2["run_id"])
        self.assertEqual(len(db_manager.get_tasks_for_run(r1["run_id"], self.db_path)), 6)
        self.assertEqual(len(db_manager.get_tasks_for_run(r2["run_id"], self.db_path)), 6)


if __name__ == "__main__":
    unittest.main()
