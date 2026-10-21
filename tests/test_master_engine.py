"""
Unit Tests for Master Orchestrator and Capability Evaluator.
"""

import sys
import os
import unittest

# Add project root directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.base_agent import TaskCategory
from src.agents.frontend_agent import FrontendAgent
from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.testing_agent import TestingAgent
from src.agents.integration_agent import IntegrationAgent
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator


class TestMasterEngine(unittest.TestCase):

    def setUp(self):
        self.evaluator = CapabilityEvaluator()
        self.frontend_agent = FrontendAgent()
        self.backend_agent = BackendAgent()
        self.db_agent = DatabaseAgent()
        self.test_agent = TestingAgent()
        self.int_agent = IntegrationAgent()

        self.evaluator.register_agent(self.frontend_agent)
        self.evaluator.register_agent(self.backend_agent)
        self.evaluator.register_agent(self.db_agent)
        self.evaluator.register_agent(self.test_agent)
        self.evaluator.register_agent(self.int_agent)

    def test_capability_fit_score(self):
        """Test fit score calculation for specific task categories."""
        fe_score = self.frontend_agent.capabilities.calculate_fit_score(TaskCategory.FRONTEND)
        be_score = self.backend_agent.capabilities.calculate_fit_score(TaskCategory.BACKEND)
        
        self.assertGreater(fe_score, 80.0)
        self.assertGreater(be_score, 80.0)

    def test_agent_selection(self):
        """Test that the best agent is selected based on capabilities."""
        best_fe = self.evaluator.select_best_agent(TaskCategory.FRONTEND, required_specialty="frontend")
        self.assertIsNotNone(best_fe)
        self.assertEqual(best_fe.agent_id, self.frontend_agent.agent_id)

    def test_full_orchestration_pipeline(self):
        """Test end-to-end execution of requirements decomposition and task scheduling."""
        orchestrator = MasterOrchestrator(evaluator=self.evaluator)
        sample_requirement = "Develop an online library management system with book catalog, user authentication, and loan tracking."
        
        result = orchestrator.process_requirement(sample_requirement, project_title="Library System")
        
        self.assertEqual(result["system_status"], "COMPLETED")
        self.assertEqual(result["total_tasks_processed"], 6)
        self.assertGreater(len(result["task_assignments"]), 0)


if __name__ == "__main__":
    unittest.main()
