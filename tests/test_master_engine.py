"""
Unit Tests for Master Orchestrator and Capability Evaluator.
"""

import sys
import os
import json
import unittest

# Add project root directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.base_agent import (
    AgentCapabilityProfile,
    AgentStatus,
    BaseAgent,
    TaskCategory,
)
from src.agents.frontend_agent import FrontendAgent
from src.agents.backend_agent import BackendAgent
from src.agents.database_agent import DatabaseAgent
from src.agents.testing_agent import TestingAgent
from src.agents.integration_agent import IntegrationAgent
from src.master.analyzer import RequirementsAnalyzer
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator


class TestMasterEngine(unittest.TestCase):

    def setUp(self):
        self.evaluator = CapabilityEvaluator()
        self.frontend_agent = FrontendAgent()
        self.backend_agent = BackendAgent(use_ollama=False)
        self.db_agent = DatabaseAgent()
        self.test_agent = TestingAgent(use_ollama=False)
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


# ---------------------------------------------------------------------------
# Test doubles (S2-06)
#
# The real worker agents in src/agents always return SUCCESS, so the failover,
# FAILED, UNASSIGNED and BLOCKED branches of the orchestrator cannot be reached
# with them. FakeAgent is built exactly like a real agent (a BaseAgent subclass
# with an AgentCapabilityProfile), but its scores, status and failure behaviour
# are configurable.
# ---------------------------------------------------------------------------

ALL_SPECIALTIES = [
    "architecture", "database", "backend", "frontend", "testing", "integration"
]


class FakeAgent(BaseAgent):
    """Configurable worker agent double used by the negative test scenarios."""

    def __init__(self, agent_id, name, coding=60.0, reasoning=60.0, context=60.0,
                 specialties=None, status=AgentStatus.IDLE, fail_on=None,
                 model_name="fake-model:1b"):
        profile = AgentCapabilityProfile(
            coding_score=coding,
            reasoning_score=reasoning,
            context_capacity=context,
            specialties=list(ALL_SPECIALTIES if specialties is None else specialties)
        )
        super().__init__(agent_id=agent_id, name=name, model_name=model_name,
                         capability_profile=profile)
        self.status = status
        # "ALL" -> fail on every task; otherwise only on the listed task_ids
        self.fail_on = "ALL" if fail_on == "ALL" else set(fail_on or [])
        self.executed_task_ids = []

    def _process(self, task, logs):
        task_id = task.get("task_id")
        self.executed_task_ids.append(task_id)
        if self.fail_on == "ALL" or task_id in self.fail_on:
            raise RuntimeError(f"Simulated failure of {self.name} on '{task_id}'")
        logs.append(f"[{self.name}] fake execution finished for '{task_id}'")
        return {"status": "FAKE_SUCCESS", "task_id": task_id}


def build_fake_evaluator(*agents):
    """Registers only the given doubles, so no real agent can rescue a task."""
    evaluator = CapabilityEvaluator()
    for agent in agents:
        evaluator.register_agent(agent)
    return evaluator


class TestCapabilityScoring(unittest.TestCase):
    """S2-03: weighted fit score and specialty bonus arithmetic."""

    def test_weighted_fit_score_uses_category_weights(self):
        """A single non-zero metric must be scaled by that category weight only."""
        coding_only = AgentCapabilityProfile(coding_score=100.0, reasoning_score=0.0,
                                             context_capacity=0.0)
        # FRONTEND weights: coding 0.50 / context 0.30 / reasoning 0.20
        self.assertEqual(coding_only.calculate_fit_score(TaskCategory.FRONTEND), 50.0)
        # REQUIREMENTS weights: reasoning 0.60 / context 0.30 / coding 0.10
        self.assertEqual(coding_only.calculate_fit_score(TaskCategory.REQUIREMENTS), 10.0)

        reasoning_only = AgentCapabilityProfile(coding_score=0.0, reasoning_score=100.0,
                                                context_capacity=0.0)
        self.assertEqual(reasoning_only.calculate_fit_score(TaskCategory.REQUIREMENTS), 60.0)
        self.assertEqual(reasoning_only.calculate_fit_score(TaskCategory.INTEGRATION), 50.0)

    def test_weighted_fit_score_mixed_metrics(self):
        """Mixed metrics must equal the hand-computed weighted sum, rounded to 2 digits."""
        profile = AgentCapabilityProfile(coding_score=90.0, reasoning_score=80.0,
                                         context_capacity=70.0)
        # BACKEND: coding 0.45 + reasoning 0.35 + context 0.20
        expected_be = round(90.0 * 0.45 + 80.0 * 0.35 + 70.0 * 0.20, 2)
        self.assertEqual(profile.calculate_fit_score(TaskCategory.BACKEND), expected_be)
        # DATABASE: reasoning 0.45 + coding 0.40 + context 0.15
        expected_db = round(80.0 * 0.45 + 90.0 * 0.40 + 70.0 * 0.15, 2)
        self.assertEqual(profile.calculate_fit_score(TaskCategory.DATABASE), expected_db)

    def test_specialty_bonus_adds_five_points_and_caps_at_100(self):
        """A matching specialty adds +5, but the total can never exceed 100."""
        agent = FakeAgent("fake-spec", "Specialty Double", coding=60.0, reasoning=60.0,
                          context=60.0, specialties=["frontend"])
        evaluator = build_fake_evaluator(agent)

        base = evaluator.evaluate_and_rank(TaskCategory.FRONTEND)[0]["fit_score"]
        bonus = evaluator.evaluate_and_rank(
            TaskCategory.FRONTEND, required_specialty="frontend")[0]["fit_score"]
        self.assertEqual(bonus, base + 5.0)

        # An unrelated specialty requirement must not change the score
        no_match = evaluator.evaluate_and_rank(
            TaskCategory.FRONTEND, required_specialty="database")[0]["fit_score"]
        self.assertEqual(no_match, base)

        near_max = FakeAgent("fake-max", "Near Max Double", coding=99.0, reasoning=99.0,
                             context=99.0, specialties=["frontend"])
        capped = build_fake_evaluator(near_max).evaluate_and_rank(
            TaskCategory.FRONTEND, required_specialty="frontend")[0]["fit_score"]
        self.assertEqual(capped, 100.0)


class TestAgentAvailabilityFiltering(unittest.TestCase):
    """S2-03: BUSY, OFFLINE and ERROR agents are excluded from candidate selection."""

    def setUp(self):
        self.busy_strong = FakeAgent("fake-busy", "Busy Strong Frontend", coding=99.0,
                                     reasoning=99.0, context=99.0,
                                     specialties=["frontend"], status=AgentStatus.BUSY)
        self.idle_weak = FakeAgent("fake-idle", "Idle Weak Frontend", coding=40.0,
                                   reasoning=40.0, context=40.0,
                                   specialties=["frontend"], status=AgentStatus.IDLE)
        self.evaluator = build_fake_evaluator(self.busy_strong, self.idle_weak)

    def test_busy_agent_is_skipped_even_with_higher_score(self):
        """Scenario 1: the BUSY top scorer must lose to the weaker available agent."""
        selected = self.evaluator.select_best_agent(TaskCategory.FRONTEND, available_only=True)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.agent_id, self.idle_weak.agent_id)

        ranked_ids = [c["agent_id"] for c in self.evaluator.evaluate_and_rank(
            TaskCategory.FRONTEND, available_only=True)]
        self.assertNotIn(self.busy_strong.agent_id, ranked_ids)

    def test_unavailable_statuses_are_filtered_but_visible_without_the_filter(self):
        """BUSY, OFFLINE and ERROR are filtered out; available_only=False keeps them."""
        for status in (AgentStatus.BUSY, AgentStatus.OFFLINE, AgentStatus.ERROR):
            with self.subTest(status=status.value):
                self.busy_strong.status = status

                filtered = self.evaluator.evaluate_and_rank(TaskCategory.FRONTEND,
                                                            available_only=True)
                self.assertEqual([c["agent_id"] for c in filtered], [self.idle_weak.agent_id])

                unfiltered = self.evaluator.evaluate_and_rank(TaskCategory.FRONTEND,
                                                              available_only=False)
                self.assertEqual(len(unfiltered), 2)
                # Without the availability filter the strong agent ranks first again
                self.assertEqual(unfiltered[0]["agent_id"], self.busy_strong.agent_id)

    def test_no_available_agent_returns_none(self):
        """With every agent OFFLINE, selection returns None instead of raising."""
        self.busy_strong.status = AgentStatus.OFFLINE
        self.idle_weak.status = AgentStatus.OFFLINE

        self.assertIsNone(self.evaluator.select_best_agent(TaskCategory.FRONTEND,
                                                           available_only=True))
        self.assertEqual(self.evaluator.evaluate_and_rank(TaskCategory.FRONTEND,
                                                          available_only=True), [])


class TestTaskSchemaValidation(unittest.TestCase):
    """S2-04: decomposition JSON schema, empty requirements and malformed JSON."""

    REQUIRED_KEYS = {"task_id", "title", "category", "description",
                     "dependencies", "required_specialty"}

    def setUp(self):
        self.analyzer = RequirementsAnalyzer()

    def _assert_valid_schema(self, decomposition):
        self.assertIn("requirement_id", decomposition)
        self.assertEqual(decomposition["total_tasks"], len(decomposition["tasks"]))

        task_ids = [t["task_id"] for t in decomposition["tasks"]]
        self.assertEqual(len(task_ids), len(set(task_ids)), "task_id values must be unique")

        for task in decomposition["tasks"]:
            self.assertTrue(self.REQUIRED_KEYS.issubset(task.keys()),
                            f"missing schema keys in {task.get('task_id')}")
            self.assertIsInstance(task["dependencies"], list)
            # The category value must map onto a known TaskCategory
            TaskCategory(task["category"])
            for dep in task["dependencies"]:
                self.assertIn(dep, task_ids, "a dependency must point to an existing task")

    def test_decomposition_matches_task_schema(self):
        """Normal decomposition output must satisfy the task JSON schema."""
        decomposition = self.analyzer.decompose(
            "Build an inventory tracking system with reporting.", "Inventory")
        self._assert_valid_schema(decomposition)
        # The output must survive a JSON round trip for the UI / persistence layers
        self.assertEqual(json.loads(json.dumps(decomposition)), decomposition)

    def test_empty_requirement_still_produces_valid_schema(self):
        """Negative input: empty and whitespace-only requirements must not crash."""
        for raw in ("", "   ", "\n\t"):
            with self.subTest(requirement=repr(raw)):
                decomposition = self.analyzer.decompose(raw, "Empty Requirement")
                self._assert_valid_schema(decomposition)
                self.assertGreater(len(decomposition["tasks"]), 0)
                self.assertEqual(decomposition["raw_requirement"], raw)

    def test_malformed_json_requirement_is_rejected(self):
        """A broken JSON requirement document must raise, not be silently accepted."""
        malformed = '{"requirement": "Build a portal", "tasks": [ {"id": 1, ]}'
        with self.assertRaises(json.JSONDecodeError):
            json.loads(malformed)

    def test_unknown_category_is_rejected(self):
        """An out-of-schema category value must raise ValueError on conversion."""
        with self.assertRaises(ValueError):
            TaskCategory("MACHINE_LEARNING")


class TestOrchestratorNegativeScenarios(unittest.TestCase):
    """S2-05 / S2-03: failover, FAILED, UNASSIGNED, BLOCKED and run isolation.

    Every orchestrator here uses persist=False, so the suite never writes state.db.
    """

    def setUp(self):
        self.real_evaluator = CapabilityEvaluator()
        for agent in (FrontendAgent(), BackendAgent(use_ollama=False), DatabaseAgent(),
                      TestingAgent(use_ollama=False), IntegrationAgent()):
            self.real_evaluator.register_agent(agent)

    @staticmethod
    def _by_id(result):
        return {t["task_id"]: t for t in result["task_assignments"]}

    def test_all_agents_offline_leaves_tasks_unassigned(self):
        """Scenario 2: no available agent -> UNASSIGNED/BLOCKED tasks, FAILED system."""
        for agent in self.real_evaluator.registered_agents:
            agent.status = AgentStatus.OFFLINE

        orchestrator = MasterOrchestrator(evaluator=self.real_evaluator, persist=False)
        result = orchestrator.process_requirement("Build a CRM system.", "Offline Fleet")

        self.assertEqual(result["system_status"], "FAILED")
        self.assertEqual(result["status_counts"]["COMPLETED"], 0)
        self.assertGreaterEqual(result["status_counts"]["UNASSIGNED"], 1)

        for record in result["task_assignments"]:
            self.assertIn(record["status"], ("UNASSIGNED", "BLOCKED"))
            self.assertIsNone(record["assigned_agent"])
            self.assertIsNone(record["model_used"])
            self.assertEqual(record["attempted_agents"], [])

        root = self._by_id(result)["task-req-1"]
        self.assertEqual(root["status"], "UNASSIGNED")
        self.assertIn("No available agent", root["reason"])

    def test_failover_to_next_candidate_after_first_agent_errors(self):
        """Scenario 3: the top-ranked agent raises, the next candidate finishes the task."""
        failing = FakeAgent("fake-fail-first", "Failing Top Agent", coding=95.0,
                            reasoning=95.0, context=95.0, fail_on=["task-req-1"])
        backup = FakeAgent("fake-backup", "Backup Agent", coding=55.0,
                           reasoning=55.0, context=55.0)
        evaluator = build_fake_evaluator(failing, backup)

        orchestrator = MasterOrchestrator(evaluator=evaluator, persist=False)
        result = orchestrator.process_requirement("Build a booking system.", "Failover")

        task = self._by_id(result)["task-req-1"]
        self.assertEqual(task["status"], "COMPLETED")
        self.assertEqual(task["agent_result_status"], "SUCCESS")
        self.assertEqual(task["assigned_agent"], backup.name)
        self.assertEqual(task["attempted_agents"], [failing.name, backup.name])
        # The failing agent really was invoked before the backup took over
        self.assertIn("task-req-1", failing.executed_task_ids)
        self.assertIn("task-req-1", backup.executed_task_ids)

    def test_task_fails_when_every_candidate_errors(self):
        """Scenario 4: all candidates raise -> FAILED task carrying the error message."""
        first = FakeAgent("fake-all-1", "Always Failing A", coding=95.0, reasoning=95.0,
                          context=95.0, fail_on="ALL")
        second = FakeAgent("fake-all-2", "Always Failing B", coding=70.0, reasoning=70.0,
                           context=70.0, fail_on="ALL")
        evaluator = build_fake_evaluator(first, second)

        orchestrator = MasterOrchestrator(evaluator=evaluator, persist=False)
        result = orchestrator.process_requirement("Build a payment gateway.", "All Fail")

        task = self._by_id(result)["task-req-1"]
        self.assertEqual(task["status"], "FAILED")
        self.assertEqual(task["agent_result_status"], "FAILED")
        self.assertEqual(sorted(task["attempted_agents"]), sorted([first.name, second.name]))
        self.assertIn("Simulated failure", task["reason"])
        self.assertIn("task-req-1", task["reason"])
        self.assertEqual(result["status_counts"]["COMPLETED"], 0)
        self.assertEqual(result["system_status"], "FAILED")

    def test_dependent_task_is_blocked_and_never_executed(self):
        """Scenario 5: task-db-1 depends on the failed task-req-1 -> BLOCKED, not executed."""
        failing = FakeAgent("fake-req-fail", "Requirements Breaker", coding=90.0,
                            reasoning=90.0, context=90.0, fail_on=["task-req-1"])
        also_failing = FakeAgent("fake-req-fail-2", "Requirements Breaker Backup",
                                 coding=70.0, reasoning=70.0, context=70.0,
                                 fail_on=["task-req-1"])
        evaluator = build_fake_evaluator(failing, also_failing)

        orchestrator = MasterOrchestrator(evaluator=evaluator, persist=False)
        result = orchestrator.process_requirement("Build a helpdesk system.", "Blocked Chain")

        records = self._by_id(result)
        self.assertEqual(records["task-req-1"]["status"], "FAILED")

        blocked = records["task-db-1"]
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIsNone(blocked["assigned_agent"])
        self.assertEqual(blocked["attempted_agents"], [])
        self.assertIn("task-req-1", blocked["reason"])
        self.assertIn("FAILED", blocked["reason"])

        # The blocked task must never have been handed to any agent
        for agent in (failing, also_failing):
            self.assertNotIn("task-db-1", agent.executed_task_ids)

        self.assertGreaterEqual(result["status_counts"]["BLOCKED"], 1)

    def test_consecutive_runs_are_isolated_by_run_id(self):
        """Scenario 6: two runs get unique run_ids and start from clean state."""
        orchestrator = MasterOrchestrator(evaluator=self.real_evaluator, persist=False)

        first = orchestrator.process_requirement("Build a blog platform.", "Run One")
        second = orchestrator.process_requirement("Build a blog platform.", "Run Two")

        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertTrue(second["run_id"].startswith("run-"))
        self.assertNotEqual(first["requirement_id"], second["requirement_id"])

        # The second run must not inherit the first run's task state
        self.assertEqual(second["total_tasks_processed"], first["total_tasks_processed"])
        self.assertEqual(second["status_counts"], first["status_counts"])
        self.assertEqual(second["system_status"], "COMPLETED")
        self.assertEqual(len(orchestrator.scheduler.get_processed_tasks()),
                         second["total_tasks_processed"])
        # A failed or unassigned task is never reported as COMPLETED
        for record in second["task_assignments"]:
            if record["status"] != "COMPLETED":
                self.assertNotEqual(record["agent_result_status"], "SUCCESS")

    def test_error_agents_are_reset_before_the_next_run(self):
        """A run that pushed agents into ERROR must not poison the following run."""
        failing = FakeAgent("fake-reset", "Resettable Agent", coding=80.0, reasoning=80.0,
                            context=80.0, fail_on=["task-req-1"])
        evaluator = build_fake_evaluator(failing)
        orchestrator = MasterOrchestrator(evaluator=evaluator, persist=False)

        first = orchestrator.process_requirement("Build a wiki.", "Error Run")
        self.assertEqual(first["system_status"], "FAILED")
        self.assertEqual(failing.status, AgentStatus.ERROR)

        failing.fail_on = set()
        second = orchestrator.process_requirement("Build a wiki.", "Recovered Run")

        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(second["system_status"], "COMPLETED")
        self.assertEqual(second["status_counts"]["BLOCKED"], 0)

    def test_mixed_outcome_reports_partially_completed(self):
        """Scenario 7: some tasks complete, others fail/block -> PARTIALLY_COMPLETED."""
        first = FakeAgent("fake-mixed-1", "Mixed Agent A", coding=90.0, reasoning=90.0,
                          context=90.0, fail_on=["task-fe-1"])
        second = FakeAgent("fake-mixed-2", "Mixed Agent B", coding=65.0, reasoning=65.0,
                           context=65.0, fail_on=["task-fe-1"])
        evaluator = build_fake_evaluator(first, second)

        orchestrator = MasterOrchestrator(evaluator=evaluator, persist=False)
        result = orchestrator.process_requirement("Build a storefront.", "Mixed Outcome")

        counts = result["status_counts"]
        self.assertEqual(result["system_status"], "PARTIALLY_COMPLETED")
        self.assertGreater(counts["COMPLETED"], 0)
        self.assertGreater(counts["FAILED"] + counts["UNASSIGNED"] + counts["BLOCKED"], 0)
        self.assertEqual(sum(counts.values()), result["total_tasks_processed"])

        records = self._by_id(result)
        self.assertEqual(records["task-req-1"]["status"], "COMPLETED")
        self.assertEqual(records["task-fe-1"]["status"], "FAILED")
        # Everything downstream of the failed frontend task is blocked
        self.assertEqual(records["task-qa-1"]["status"], "BLOCKED")
        self.assertEqual(records["task-int-1"]["status"], "BLOCKED")


# ---------------------------------------------------------------------------
# S3-06: DAG cycle detection and BLOCKED propagation
#
# The analyzer always returns the same linear DAG, so these tests replace
# orchestrator.analyzer.decompose with a fixed custom task graph.
# ---------------------------------------------------------------------------

def _task(task_id, deps=(), category="BACKEND", specialty="backend"):
    return {
        "task_id": task_id,
        "title": f"Task {task_id}",
        "category": category,
        "description": f"Synthetic task {task_id} for DAG tests",
        "dependencies": list(deps),
        "required_specialty": specialty,
    }


def _run_with_graph(tasks, *agents):
    orchestrator = MasterOrchestrator(evaluator=build_fake_evaluator(*agents), persist=False)
    orchestrator.analyzer.decompose = lambda text, title: {"requirement_id": "req-dag", "tasks": tasks}
    result = orchestrator.process_requirement("graph test", "DAG")
    return result, {t["task_id"]: t for t in result["task_assignments"]}


class TestSchedulerCycleDetection(unittest.TestCase):
    """S3-06: TaskScheduler.find_cycles on hand-built graphs."""

    def setUp(self):
        from src.master.scheduler import TaskScheduler
        self.scheduler = TaskScheduler()

    def test_acyclic_graph_has_no_cycles(self):
        tasks = [_task("a"), _task("b", ["a"]), _task("c", ["a"]), _task("d", ["b", "c"])]
        self.assertEqual(self.scheduler.find_cycles(tasks), [])

    def test_two_node_cycle_is_detected(self):
        tasks = [_task("a", ["b"]), _task("b", ["a"]), _task("c")]
        self.assertEqual(self.scheduler.find_cycles(tasks), [["a", "b"]])

    def test_self_dependency_is_a_cycle(self):
        self.assertEqual(self.scheduler.find_cycles([_task("a", ["a"])]), [["a"]])

    def test_long_cycle_and_separate_cycles_are_reported(self):
        tasks = [_task("a", ["c"]), _task("b", ["a"]), _task("c", ["b"]),
                 _task("x", ["y"]), _task("y", ["x"]), _task("free", ["a"])]
        cycles = sorted(self.scheduler.find_cycles(tasks))
        self.assertEqual(cycles, [["a", "b", "c"], ["x", "y"]])

    def test_undefined_dependency_is_not_a_cycle(self):
        self.assertEqual(self.scheduler.find_cycles([_task("a", ["ghost"])]), [])

    def test_cycle_members_are_never_executable(self):
        tasks = [_task("a", ["b"]), _task("b", ["a"]), _task("c")]
        executable = [t["task_id"] for t in self.scheduler.get_executable_tasks(tasks)]
        self.assertEqual(executable, ["c"])


class TestOrchestratorDagBlocking(unittest.TestCase):
    """S3-06: cyclic / failed / missing prerequisites must end as BLOCKED, never executed."""

    def test_cyclic_tasks_are_blocked_with_cycle_reason(self):
        agent = FakeAgent("fake-dag", "DAG Agent")
        tasks = [_task("a", ["b"]), _task("b", ["a"]), _task("c")]
        result, records = _run_with_graph(tasks, agent)

        self.assertEqual(records["c"]["status"], "COMPLETED")
        for tid in ("a", "b"):
            self.assertEqual(records[tid]["status"], "BLOCKED")
            self.assertIn("döngüsel bağımlılık", records[tid]["reason"])
            self.assertIn("a <-> b", records[tid]["reason"])
            self.assertIsNone(records[tid]["assigned_agent"])
        self.assertEqual(agent.executed_task_ids, ["c"])
        self.assertEqual(result["system_status"], "PARTIALLY_COMPLETED")

    def test_task_downstream_of_cycle_is_blocked_but_not_marked_cyclic(self):
        agent = FakeAgent("fake-dag", "DAG Agent")
        tasks = [_task("a", ["b"]), _task("b", ["a"]), _task("after", ["a"])]
        _, records = _run_with_graph(tasks, agent)

        self.assertEqual(records["after"]["status"], "BLOCKED")
        self.assertNotIn("döngüsel bağımlılık tespit", records["after"]["reason"])
        self.assertIn("'a'", records["after"]["reason"])
        self.assertEqual(agent.executed_task_ids, [])

    def test_failed_task_blocks_whole_downstream_chain_transitively(self):
        agent = FakeAgent("fake-dag", "DAG Agent", fail_on=["root"])
        # "side" is listed first: an agent that errors stays ERROR (unavailable) for the
        # rest of the run, so anything scheduled after "root" would become UNASSIGNED.
        tasks = [_task("side"), _task("root"), _task("mid", ["root"]), _task("leaf", ["mid"])]
        result, records = _run_with_graph(tasks, agent)

        self.assertEqual(records["root"]["status"], "FAILED")
        self.assertEqual(records["mid"]["status"], "BLOCKED")
        self.assertIn("'root', durum FAILED", records["mid"]["reason"])
        self.assertEqual(records["leaf"]["status"], "BLOCKED")
        self.assertIn("'mid', durum BLOCKED", records["leaf"]["reason"])
        self.assertEqual(records["side"]["status"], "COMPLETED")
        self.assertEqual(sorted(agent.executed_task_ids), ["root", "side"])
        self.assertEqual(result["status_counts"], {"COMPLETED": 1, "FAILED": 1, "UNASSIGNED": 0, "BLOCKED": 2})

    def test_one_failed_parent_in_diamond_blocks_the_join(self):
        agent = FakeAgent("fake-dag", "DAG Agent", fail_on=["right"])
        tasks = [_task("top"), _task("left", ["top"]), _task("right", ["top"]),
                 _task("join", ["left", "right"])]
        _, records = _run_with_graph(tasks, agent)

        self.assertEqual(records["left"]["status"], "COMPLETED")
        self.assertEqual(records["right"]["status"], "FAILED")
        self.assertEqual(records["join"]["status"], "BLOCKED")
        self.assertIn("'right', durum FAILED", records["join"]["reason"])
        self.assertNotIn("join", agent.executed_task_ids)

    def test_undefined_dependency_is_blocked(self):
        agent = FakeAgent("fake-dag", "DAG Agent")
        _, records = _run_with_graph([_task("a", ["ghost"])], agent)

        self.assertEqual(records["a"]["status"], "BLOCKED")
        self.assertIn("'ghost' tanımlı değil", records["a"]["reason"])
        self.assertEqual(agent.executed_task_ids, [])

    def test_unassigned_parent_blocks_child(self):
        offline = FakeAgent("fake-off", "Offline Agent", status=AgentStatus.OFFLINE)
        tasks = [_task("ui", category="FRONTEND", specialty="frontend"), _task("api", ["ui"])]
        _, records = _run_with_graph(tasks, offline)

        self.assertEqual(records["ui"]["status"], "UNASSIGNED")
        self.assertEqual(records["api"]["status"], "BLOCKED")
        self.assertIn("'ui', durum UNASSIGNED", records["api"]["reason"])

    def test_diamond_executes_in_dependency_order(self):
        agent = FakeAgent("fake-dag", "DAG Agent")
        tasks = [_task("join", ["left", "right"]), _task("right", ["top"]),
                 _task("left", ["top"]), _task("top")]
        result, _ = _run_with_graph(tasks, agent)

        order = agent.executed_task_ids
        self.assertEqual(result["system_status"], "COMPLETED")
        self.assertEqual(order[0], "top")
        self.assertEqual(order[-1], "join")


if __name__ == "__main__":
    unittest.main()
