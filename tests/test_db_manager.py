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
        evaluator = CapabilityEvaluator([FrontendAgent(use_ollama=False), BackendAgent(use_ollama=False), DatabaseAgent(use_ollama=False),
                                         TestingAgent(use_ollama=False), IntegrationAgent(use_llm=False)])
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
        evaluator = CapabilityEvaluator([FrontendAgent(use_ollama=False), BackendAgent(use_ollama=False), DatabaseAgent(use_ollama=False),
                                         TestingAgent(use_ollama=False), IntegrationAgent(use_llm=False)])
        orch = MasterOrchestrator(evaluator=evaluator, db_path=self.db_path)
        r1 = orch.process_requirement("A", "A")
        r2 = orch.process_requirement("B", "B")
        self.assertNotEqual(r1["run_id"], r2["run_id"])
        self.assertEqual(len(db_manager.get_tasks_for_run(r1["run_id"], self.db_path)), 6)
        self.assertEqual(len(db_manager.get_tasks_for_run(r2["run_id"], self.db_path)), 6)

    # --- S4-04: output_files, file_conflicts, attempts.model_used ---------
    def test_output_files_and_attempts_model_used_persisted_across_run(self):
        evaluator = CapabilityEvaluator([
            FrontendAgent(use_ollama=False), BackendAgent(use_ollama=False),
            DatabaseAgent(use_ollama=False), TestingAgent(use_ollama=False),
            IntegrationAgent(use_llm=False),
        ])
        orch = MasterOrchestrator(evaluator=evaluator, db_path=self.db_path)
        result = orch.process_requirement("Kütüphane yönetim sistemi", "Library")
        run_id = result["run_id"]

        files = db_manager.get_output_files_for_run(run_id, self.db_path)
        self.assertTrue(len(files) >= 1)
        for f in files:
            self.assertEqual(len(f["sha256"]), 64)
            self.assertGreater(f["size_bytes"], 0)
            self.assertIn(f["review_status"], db_manager.REVIEW_STATUSES)

        # IntegrationAgent worked on the generated files so at least one should be APPROVED
        self.assertTrue(any(f["review_status"] == "APPROVED" for f in files))

        attempts = db_manager.get_attempts_for_task(run_id, "task-db-1", self.db_path)
        if attempts:
            self.assertEqual(attempts[0]["model_used"], "llama3.2:3b")

    def test_file_conflicts_table_persisted_and_review_updated(self):
        db_manager.init_db(self.db_path, verbose=False)
        db_manager.create_run("run-s4-1", "Test Project", total_tasks=1, db_path=self.db_path)
        task = {"task_id": "t-2", "title": "DB", "category": "DATABASE", "dependencies": []}
        record = {
            "task_id": "t-2", "title": "DB", "assigned_agent": "Database Schema Agent",
            "model_used": "llama3.2:3b", "fit_score": 90.0, "execution_time_seconds": 1.2,
            "status": "COMPLETED", "agent_result_status": "SUCCESS",
            "reason": "ok", "attempted_agents": ["Database Schema Agent"],
            "output_files": ["database/schema.t-2.sql"],
        }
        conflict = {
            "conflict_type": "PATH", "file_path": "database/schema.sql",
            "resolved_path": "database/schema.t-2.sql", "task_id": "t-2",
            "other_task_id": "t-1", "resolution": "RENAMED",
            "detail": "renamed to avoid overwrite",
        }
        file_rec = {
            "relative_path": "database/schema.t-2.sql",
            "requested_path": "database/schema.sql",
            "size_bytes": 42,
            "sha256": "a" * 64,
            "conflict": conflict,
        }
        db_manager.save_task_result(
            "run-s4-1", task, record,
            attempts=[{"agent_id": "agent-db", "agent_name": "Database Schema Agent",
                       "model_used": "llama3.2:3b", "is_successful": True, "execution_time_seconds": 1.2}],
            file_records=[file_rec],
            db_path=self.db_path,
        )

        files = db_manager.get_output_files_for_run("run-s4-1", self.db_path)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["conflict_resolution"], "RENAMED")
        self.assertEqual(files[0]["review_status"], "PENDING")

        conflicts = db_manager.get_conflicts_for_run("run-s4-1", self.db_path)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["conflict_type"], "PATH")
        self.assertEqual(conflicts[0]["other_task_id"], "t-1")

        db_manager.update_output_file_reviews("run-s4-1", {"database/schema.t-2.sql": "REVIEW_REQUIRED"}, db_path=self.db_path)
        updated = db_manager.get_output_files_for_run("run-s4-1", self.db_path)
        self.assertEqual(updated[0]["review_status"], "REVIEW_REQUIRED")

    def test_v3_database_migrates_cleanly_to_v4(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, project_title TEXT, system_status TEXT)")
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, run_id TEXT, task_id TEXT, status TEXT)")
        conn.execute("CREATE TABLE attempts (attempt_id INTEGER PRIMARY KEY, run_id TEXT, task_id TEXT, attempt_no INTEGER, is_successful INTEGER)")
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
        conn.close()

        db_manager.init_db(self.db_path, verbose=False)
        conn = sqlite3.connect(self.db_path)
        run_cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
        attempt_cols = {r[1] for r in conn.execute("PRAGMA table_info(attempts)")}
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()

        self.assertIn("owner_pid", run_cols)
        self.assertIn("model_used", attempt_cols)
        self.assertIn("output_files", tables)
        self.assertIn("file_conflicts", tables)
        self.assertEqual(version, db_manager.SCHEMA_VERSION)

    # --- Stale / Interrupted RUNNING recovery -----------------------------
    def test_recover_stale_runs_closes_dead_pid_and_keeps_live_run(self):
        db_manager.init_db(self.db_path, verbose=False)
        db_manager.create_run("run-dead", "Crashed Run", total_tasks=5, owner_pid=99999999, db_path=self.db_path)
        db_manager.create_run("run-live", "Active Run", total_tasks=5, owner_pid=os.getpid(), db_path=self.db_path)

        # Calling init_db again automatically recovers the dead-PID run without touching the live one
        db_manager.init_db(self.db_path, verbose=False)

        dead = db_manager.get_run("run-dead", self.db_path)
        live = db_manager.get_run("run-live", self.db_path)
        self.assertEqual(dead["system_status"], "ABORTED")
        self.assertIsNotNone(dead["finished_at"])
        self.assertEqual(live["system_status"], "RUNNING")
        self.assertIsNone(live["finished_at"])

    def test_recover_stale_runs_closes_timed_out_legacy_run_and_in_progress_tasks(self):
        db_manager.init_db(self.db_path, verbose=False)
        conn = db_manager.get_connection(self.db_path)
        conn.execute(
            "INSERT INTO runs (run_id, project_title, total_tasks, owner_pid, system_status, started_at) "
            "VALUES ('run-old', 'Legacy Stuck', 3, NULL, 'RUNNING', datetime('now', '-2 hours'))"
        )
        conn.execute(
            "INSERT INTO tasks (run_id, task_id, title, status, agent_result_status, assigned_agent_name) "
            "VALUES ('run-old', 't1', 'DB', 'COMPLETED', 'SUCCESS', 'Database Agent')"
        )
        conn.execute(
            "INSERT INTO tasks (run_id, task_id, title, status) "
            "VALUES ('run-old', 't2', 'API', 'IN_PROGRESS')"
        )
        conn.commit()
        conn.close()

        recovered = db_manager.recover_stale_runs(db_path=self.db_path, max_age_seconds=1800)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["run_id"], "run-old")
        self.assertEqual(recovered[0]["new_status"], "ABORTED")

        run = db_manager.get_run("run-old", self.db_path)
        self.assertEqual(run["system_status"], "ABORTED")
        self.assertEqual(run["completed_count"], 1)
        self.assertEqual(run["failed_count"], 1)
        self.assertIsNotNone(run["finished_at"])

        tasks = {t["task_id"]: t for t in db_manager.get_tasks_for_run("run-old", self.db_path)}
        self.assertEqual(tasks["t1"]["status"], "COMPLETED")
        self.assertEqual(tasks["t2"]["status"], "FAILED")
        self.assertIn("yarıda kesildi", tasks["t2"]["reason"])

    def test_v4_database_migrates_check_constraint_to_allow_aborted_without_losing_tasks(self):
        # Simulate an existing v4 DB whose runs CHECK constraint did not include ABORTED
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("""
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                project_title TEXT,
                requirement_id TEXT,
                system_status TEXT NOT NULL DEFAULT 'RUNNING'
                    CHECK (system_status IN ('RUNNING', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED')),
                total_tasks INTEGER DEFAULT 0,
                completed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                unassigned_count INTEGER DEFAULT 0,
                blocked_count INTEGER DEFAULT 0,
                workspace_path TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                title TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                agent_result_status TEXT,
                reason TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (run_id, task_id),
                FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
            )
        """)
        conn.execute(
            "INSERT INTO runs (run_id, project_title, total_tasks, system_status, started_at) "
            "VALUES ('run-v4-stuck', 'Old v4 Run', 1, 'RUNNING', datetime('now', '-3 hours'))"
        )
        conn.execute(
            "INSERT INTO tasks (run_id, task_id, title, status, agent_result_status) "
            "VALUES ('run-v4-stuck', 't1', 'DB', 'COMPLETED', 'SUCCESS')"
        )
        conn.execute("PRAGMA user_version = 4")
        conn.commit()
        conn.close()

        db_manager.init_db(self.db_path, verbose=False)

        run = db_manager.get_run("run-v4-stuck", self.db_path)
        self.assertEqual(run["system_status"], "ABORTED")
        self.assertEqual(run["completed_count"], 1)
        self.assertIsNotNone(run["finished_at"])
        tasks = db_manager.get_tasks_for_run("run-v4-stuck", self.db_path)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], "t1")

    def test_mark_run_aborted_is_noop_for_finished_run(self):
        db_manager.init_db(self.db_path, verbose=False)
        db_manager.create_run("run-done", "Done", total_tasks=1, db_path=self.db_path)
        db_manager.finish_run("run-done", "COMPLETED", {"COMPLETED": 1}, db_path=self.db_path)

        status = db_manager.mark_run_aborted("run-done", db_path=self.db_path)
        self.assertEqual(status, "COMPLETED")
        self.assertEqual(db_manager.get_run("run-done", self.db_path)["system_status"], "COMPLETED")

    def test_orchestrator_aborted_mid_run_never_leaves_running_record(self):
        class InterruptingAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    agent_id="agent-interrupt",
                    name="Interrupting Agent",
                    model_name="qwen2.5-coder:7b",
                    capability_profile=AgentCapabilityProfile(95, 95, 95, ["architecture"]),
                )

            def _process(self, task, logs):
                raise KeyboardInterrupt("user stopped execution")

        evaluator = CapabilityEvaluator([InterruptingAgent()])
        orch = MasterOrchestrator(evaluator=evaluator, db_path=self.db_path)

        with self.assertRaises(KeyboardInterrupt):
            orch.process_requirement("Interrupted requirement", "Interrupted Project")

        self.assertEqual(db_manager.get_running_runs(self.db_path), [])
        conn = db_manager.get_connection(self.db_path)
        rows = conn.execute("SELECT run_id, system_status, finished_at FROM runs").fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["system_status"], "ABORTED")
        self.assertIsNotNone(rows[0]["finished_at"])


if __name__ == "__main__":
    unittest.main()
