import unittest
from src.contracts import (
    validate_master_tasks,
    WorkerTaskResultContract_v1,
    OrchestratorTaskRecordContract_v1,
)
from src.agents.integration_agent import IntegrationAgent


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


if __name__ == "__main__":
    unittest.main()