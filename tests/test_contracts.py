"""
Unit Tests for Inter-Agent Contracts, Task Envelopes, Duplicate Protection,
and RemoteAgentProxy Distributed Dispatch (S2-04 & S3-01).
"""

import os
import socket
import unittest
import urllib.error

from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.frontend_agent import FrontendAgent
from src.agents.integration_agent import IntegrationAgent
from src.agents.remote_agent import (
    RemoteAgentProxy,
    get_agent_endpoint_url,
    wrap_agent_if_remote,
)
from src.agents.testing_agent import TestingAgent
from src.api.worker_server import create_agent_by_role
from src.contracts import (
    CONTRACT_VERSION,
    DuplicateTaskTracker,
    OrchestratorTaskRecordContract_v1,
    TaskPayloadContract_v1,
    WorkerErrorCode,
    WorkerErrorContract_v1,
    WorkerTaskResultContract_v1,
    build_task_envelope,
    normalize_worker_status,
    validate_master_tasks,
)
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator


class TestContracts(unittest.TestCase):

    def test_validate_master_tasks_valid(self):
        raw_tasks = [
            {
                "task_id": "t1",
                "title": "Database Schema",
                "category": "database",
                "description": "Create SQLite user tables",
                "dependencies": [],
                "required_specialty": "database",
            }
        ]
        is_valid, err, validated = validate_master_tasks(raw_tasks)
        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["task_id"], "t1")

    def test_validate_master_tasks_invalid(self):
        # Zorunlu alanları (title, category, required_specialty) eksik görev
        bad_tasks = [{"task_id": "t1", "description": "kısa"}]
        is_valid, err, _ = validate_master_tasks(bad_tasks)
        self.assertFalse(is_valid)
        self.assertIsNotNone(err)

    def test_worker_and_orchestrator_contracts_alignment(self):
        worker_res = WorkerTaskResultContract_v1(
            task_id="t1",
            agent_id="backend_1",
            status="COMPLETED",
            output_artifacts={"main.py": "print('ok')"},
            logs=["done"],
            execution_time_seconds=0.5,
        )
        self.assertIn("main.py", worker_res.output_artifacts)
        self.assertTrue(worker_res.is_success())
        self.assertEqual(worker_res.normalized_status(), "SUCCESS")
        self.assertEqual(worker_res.contract_version, CONTRACT_VERSION)

        orch_rec = OrchestratorTaskRecordContract_v1(
            run_id="run_1",
            task_id="t2",
            status="UNASSIGNED",
            agent_result_status="FAILED",
            attempted_agents=["backend_1", "backend_2"],
        )
        self.assertEqual(orch_rec.status, "UNASSIGNED")
        self.assertEqual(len(orch_rec.attempted_agents), 2)

    def test_integration_agent_syntax_and_conflict_checks(self):
        agent = IntegrationAgent()

        # 1. Geçerli Python kodu -> APPROVED
        ok_report = agent.inspect_artifacts({"app.py": "def hello():\n    return 42\n"})
        self.assertEqual(ok_report.status, "APPROVED")
        self.assertIsNone(ok_report.package_path)

        # 2. Bozuk Python kodu (SyntaxError) ve Çakışma -> REJECTED
        bad_report = agent.inspect_artifacts(
            artifacts={"broken.py": "def hello(:\n    pass"},
            artifact_sources={"broken.py": ["agent_a", "agent_b"]},
        )
        self.assertEqual(bad_report.status, "REJECTED")
        self.assertIn("broken.py", bad_report.conflicts_detected)
        self.assertTrue(any(f.severity == "CRITICAL" for f in bad_report.findings))

    def test_build_task_envelope_includes_run_id_task_id_and_timeout(self):
        """S3-01 Item 1 & 2: Task envelope carries version, run_id, task_id, timeout, and merged context."""
        raw_task = {
            "task_id": "task-be-1",
            "title": "Backend API",
            "category": "BACKEND",
            "description": "Create endpoints",
            "dependencies": ["task-db-1"],
            "required_specialty": "backend",
            "context_artifacts": {"initial": "v1"},
        }
        envelope = build_task_envelope(
            raw_task,
            run_id="run-12345678",
            context_artifacts={"schema": "CREATE TABLE users (id INT);"},
            timeout_seconds=45.0,
        )
        self.assertEqual(envelope.contract_version, "1.0")
        self.assertEqual(envelope.run_id, "run-12345678")
        self.assertEqual(envelope.task_id, "task-be-1")
        self.assertEqual(envelope.category, "BACKEND")
        self.assertEqual(envelope.dependencies, ["task-db-1"])
        self.assertTrue(envelope.envelope_id.startswith("env-"))
        self.assertEqual(envelope.timeout_seconds, 45.0)
        self.assertIn("description", envelope.payload)
        self.assertIn("created_at", envelope.timestamps)
        self.assertIn("dispatched_at", envelope.timestamps)
        self.assertEqual(envelope.context_artifacts["initial"], "v1")
        self.assertEqual(envelope.context_artifacts["schema"], "CREATE TABLE users (id INT);")

    def test_worker_error_contract_schema(self):
        """S3-01 Item 1: Versioned error schema validates error codes and retryable flags."""
        err = WorkerErrorContract_v1(
            run_id="run-001",
            task_id="task-db-1",
            agent_id="agent-database",
            error_code=WorkerErrorCode.TIMEOUT,
            message="Worker timed out after 45s",
            retryable=True,
        )
        dumped = err.model_dump()
        self.assertEqual(dumped["contract_version"], "1.0")
        self.assertEqual(dumped["error_code"], "TIMEOUT")
        self.assertTrue(dumped["retryable"])
        self.assertEqual(dumped["run_id"], "run-001")
        self.assertEqual(dumped["task_id"], "task-db-1")

    def test_normalize_worker_status(self):
        self.assertEqual(normalize_worker_status("SUCCESS"), "SUCCESS")
        self.assertEqual(normalize_worker_status("COMPLETED"), "SUCCESS")
        self.assertEqual(normalize_worker_status("FAILED"), "FAILED")
        self.assertEqual(normalize_worker_status("REJECTED"), "FAILED")


class TestDuplicateTaskTracker(unittest.TestCase):
    """S3-01 Item 3: Duplicate message detection and idempotent result caching."""

    def test_duplicate_in_progress_and_completed_caching(self):
        tracker = DuplicateTaskTracker()

        # 1. First arrival -> NEW
        state1, cached1 = tracker.begin("run-1", "task-be-1")
        self.assertEqual(state1, "NEW")
        self.assertIsNone(cached1)

        # 2. Second arrival while still running -> IN_PROGRESS
        state2, cached2 = tracker.begin("run-1", "task-be-1")
        self.assertEqual(state2, "IN_PROGRESS")
        self.assertIsNone(cached2)

        # 3. Complete the task and verify subsequent duplicate returns cached result
        payload = {"task_id": "task-be-1", "status": "SUCCESS", "output_artifacts": {"ok": True}}
        tracker.complete("run-1", "task-be-1", payload)

        state3, cached3 = tracker.begin("run-1", "task-be-1")
        self.assertEqual(state3, "COMPLETED")
        self.assertEqual(cached3["status"], "SUCCESS")
        self.assertTrue(cached3["output_artifacts"]["ok"])

        # 4. Different run_id is isolated -> NEW
        state4, _ = tracker.begin("run-2", "task-be-1")
        self.assertEqual(state4, "NEW")

    def test_release_on_failure_allows_retry_or_failover(self):
        tracker = DuplicateTaskTracker()
        state1, _ = tracker.begin("run-1", "task-db-1")
        self.assertEqual(state1, "NEW")

        # Failed attempt releases the lock
        tracker.release("run-1", "task-db-1")

        state2, _ = tracker.begin("run-1", "task-db-1")
        self.assertEqual(state2, "NEW")


class TestRemoteAgentProxyAndDistributedDispatch(unittest.TestCase):
    """S3-01: RemoteAgentProxy HTTP/Tailscale dispatch, timeouts, auth errors, and orchestrator integration."""

    def test_remote_proxy_sends_versioned_envelope_and_normalizes_completed(self):
        captured = {}

        def fake_transport(method, url, payload, headers, timeout):
            captured["method"] = method
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            captured["timeout"] = timeout
            return {
                "contract_version": "1.0",
                "run_id": payload["run_id"],
                "task_id": payload["task_id"],
                "agent_id": "agent-backend",
                "status": "COMPLETED",
                "output_artifacts": {
                    "files": [{"filename": "api.py", "content": "x = 1\n"}]
                },
                "logs": ["Remote backend finished"],
                "execution_time_seconds": 0.42,
            }

        proxy = RemoteAgentProxy(
            endpoint_url="http://100.64.0.10:8001",
            local_agent=BackendAgent(use_ollama=False),
            auth_token="tailscale-secret-token",
            timeout=30.0,
            transport=fake_transport,
        )
        res = proxy.execute_task({
            "run_id": "run-ts-01",
            "task_id": "task-be-1",
            "title": "Backend REST Service",
            "category": "BACKEND",
            "description": "Build endpoints",
            "required_specialty": "backend",
        })

        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "http://100.64.0.10:8001/task")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer tailscale-secret-token")
        self.assertEqual(captured["payload"]["contract_version"], "1.0")
        self.assertEqual(captured["payload"]["run_id"], "run-ts-01")
        self.assertEqual(captured["payload"]["task_id"], "task-be-1")
        self.assertEqual(captured["timeout"], 30.0)

    def test_remote_proxy_timeout_and_http_error_classification(self):
        def timeout_transport(method, url, payload, headers, timeout):
            raise socket.timeout("Read timed out")

        proxy = RemoteAgentProxy(
            endpoint_url="http://100.64.0.11:8002",
            local_agent=DatabaseAgent(use_ollama=False),
            auth_token="token",
            timeout=5.0,
            transport=timeout_transport,
        )
        res = proxy.execute_task({
            "run_id": "run-ts-02",
            "task_id": "task-db-1",
            "title": "DB Schema",
            "category": "DATABASE",
            "description": "Design tables",
            "required_specialty": "database",
        })
        self.assertEqual(res.status, "FAILED")
        self.assertIn("TIMEOUT", res.error_message)
        self.assertEqual(proxy.last_error_contract.error_code, WorkerErrorCode.TIMEOUT)
        self.assertTrue(proxy.last_error_contract.retryable)

        # 401 Unauthorized classification
        def unauth_transport(method, url, payload, headers, timeout):
            raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

        proxy_401 = RemoteAgentProxy(
            endpoint_url="http://100.64.0.11:8002",
            local_agent=DatabaseAgent(use_ollama=False),
            auth_token="bad-token",
            transport=unauth_transport,
        )
        res_401 = proxy_401.execute_task({
            "run_id": "run-ts-02",
            "task_id": "task-db-1",
            "title": "DB Schema",
            "category": "DATABASE",
            "description": "Design tables",
            "required_specialty": "database",
        })
        self.assertEqual(res_401.status, "FAILED")
        self.assertEqual(proxy_401.last_error_contract.error_code, WorkerErrorCode.UNAUTHORIZED)
        self.assertFalse(proxy_401.last_error_contract.retryable)

    def test_remote_proxy_fallback_to_local_when_enabled(self):
        def offline_transport(method, url, payload, headers, timeout):
            raise urllib.error.URLError(ConnectionRefusedError("Connection refused"))

        proxy = RemoteAgentProxy(
            endpoint_url="http://100.64.0.12:8001",
            local_agent=BackendAgent(use_ollama=False),
            fallback_to_local=True,
            transport=offline_transport,
        )
        res = proxy.execute_task({
            "run_id": "run-ts-03",
            "task_id": "task-be-1",
            "title": "Backend API",
            "category": "BACKEND",
            "description": "Build endpoints",
            "required_specialty": "backend",
        })
        self.assertEqual(res.status, "SUCCESS")
        self.assertIn("[REMOTE_FALLBACK]", " ".join(res.logs))

    def test_orchestrator_dispatches_envelopes_with_run_id_and_chains_artifacts_to_integration(self):
        """End-to-end S3-01 verification:
        - Every dispatched task has run_id and task_id in its envelope.
        - Upstream artifacts are chained to downstream tasks.
        - IntegrationAgent receives generated files from DB and Backend agents and succeeds on task-int-1.
        """
        evaluator = CapabilityEvaluator([
            FrontendAgent(),
            BackendAgent(use_ollama=False),
            DatabaseAgent(use_ollama=False),
            TestingAgent(use_ollama=False),
            IntegrationAgent(),
        ])
        orch = MasterOrchestrator(evaluator=evaluator, persist=False)
        report = orch.process_requirement("Library management system", "Library")

        self.assertEqual(report["system_status"], "COMPLETED")
        self.assertEqual(len(orch.dispatched_envelopes), 6)

        run_id = report["run_id"]
        for env in orch.dispatched_envelopes:
            self.assertEqual(env["contract_version"], "1.0")
            self.assertEqual(env["run_id"], run_id)
            self.assertIn("task_id", env)
            self.assertGreater(env["timeout_seconds"], 0)

        by_id = {r["task_id"]: r for r in report["task_assignments"]}
        # Integration task must be completed by Integration Agent itself (not failed over!)
        self.assertEqual(by_id["task-int-1"]["status"], "COMPLETED")
        self.assertEqual(by_id["task-int-1"]["assigned_agent"], "Integration Agent")
        self.assertEqual(by_id["task-int-1"]["attempted_agents"], ["Integration Agent"])

        # Integration envelope received the upstream generated .sql and .py files
        int_env = next(e for e in orch.dispatched_envelopes if e["task_id"] == "task-int-1")
        self.assertIn("output_artifacts", int_env)
        self.assertIn("database/schema_task_db_1.sql", int_env["output_artifacts"])
        self.assertIn("backend_task_be_1.py", int_env["output_artifacts"])

    def test_wrap_agent_if_remote_and_create_agent_by_role(self):
        orig = os.environ.get("DATABASE_AGENT_URL")
        try:
            os.environ["DATABASE_AGENT_URL"] = "http://100.64.0.22:8002"
            db_ag = DatabaseAgent(agent_id="agent-database", use_ollama=False)
            wrapped = wrap_agent_if_remote(db_ag)
            self.assertIsInstance(wrapped, RemoteAgentProxy)
            self.assertEqual(wrapped.endpoint_url, "http://100.64.0.22:8002")
            self.assertEqual(get_agent_endpoint_url("agent-database"), "http://100.64.0.22:8002")
        finally:
            if orig is None:
                os.environ.pop("DATABASE_AGENT_URL", None)
            else:
                os.environ["DATABASE_AGENT_URL"] = orig

        for role, cls in (
            ("backend", BackendAgent),
            ("database", DatabaseAgent),
            ("frontend", FrontendAgent),
            ("testing", TestingAgent),
            ("integration", IntegrationAgent),
        ):
            self.assertIsInstance(create_agent_by_role(role), cls)


if __name__ == "__main__":
    unittest.main()
