"""
S4-07 (Eren Görkem Çolak): tasks that are ready at the same time and do not depend on each
other are sent to their agents in parallel; dependencies, failover and "one task per agent
at a time" still hold. Agents are in-process doubles; no network, no Ollama, no real state.db.
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.base_agent import AgentCapabilityProfile, AgentStatus, BaseAgent, TaskResult
from src.master.capability_eval import CapabilityEvaluator
from src.master.orchestrator import MasterOrchestrator


class Clock:
    """Shared record of who ran what, when, and how many agents ran at once."""

    def __init__(self):
        self.lock = threading.Lock()
        self.running = 0
        self.max_running = 0
        self.spans = {}

    def enter(self, task_id):
        with self.lock:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
            self.spans[task_id] = [time.monotonic(), None]

    def leave(self, task_id):
        with self.lock:
            self.running -= 1
            self.spans[task_id][1] = time.monotonic()


class Worker(BaseAgent):
    def __init__(self, agent_id, specialties, clock, delay=0.15, barrier=None, fail=False, score=80):
        profile = AgentCapabilityProfile(coding_score=score, reasoning_score=score, context_capacity=score,
                                         specialties=list(specialties))
        super().__init__(agent_id=agent_id, name=agent_id.title(), model_name=f"{agent_id}:1b",
                         capability_profile=profile)
        self.clock, self.delay, self.barrier, self.fail = clock, delay, barrier, fail
        self.busy = 0
        self.max_busy = 0
        self._own = threading.Lock()

    def execute_task(self, task):
        task_id = task["task_id"]
        with self._own:
            self.busy += 1
            self.max_busy = max(self.max_busy, self.busy)
        self.clock.enter(task_id)
        try:
            if self.barrier is not None:
                self.barrier.wait(timeout=5)  # only passes if the other task runs at the same time
            time.sleep(self.delay)
        finally:
            self.clock.leave(task_id)
            with self._own:
                self.busy -= 1
        if self.fail:
            self.status = AgentStatus.ERROR
            return TaskResult(task_id=task_id, agent_id=self.agent_id, status="FAILED", output_artifacts={},
                              logs=[], execution_time_seconds=self.delay, error_message="local crash")
        self.status = AgentStatus.IDLE
        return TaskResult(task_id=task_id, agent_id=self.agent_id, status="SUCCESS",
                          output_artifacts={"files": [{"filename": f"{task_id}.py", "content": "x = 1\n"}]},
                          logs=[], execution_time_seconds=self.delay)


def task(task_id, specialty, deps=()):
    category = {"database": "DATABASE", "backend": "BACKEND", "frontend": "FRONTEND",
                "testing": "TESTING"}[specialty]
    return {"task_id": task_id, "title": f"Task {task_id}", "category": category,
            "description": f"Parallel test task {task_id}", "dependencies": list(deps),
            "required_specialty": specialty}


def run(agents, tasks, **kwargs):
    evaluator = CapabilityEvaluator()
    for agent in agents:
        evaluator.register_agent(agent)
    kwargs.setdefault("persist", False)
    orch = MasterOrchestrator(evaluator=evaluator, **kwargs)
    orch.analyzer.decompose = lambda text, title: {
        "requirement_id": "req-par", "project_title": title, "raw_requirement": text,
        "total_tasks": len(tasks), "tasks": [dict(t) for t in tasks]}
    report = orch.process_requirement("parallel test", "Parallel")
    return report, {r["task_id"]: r for r in report["task_assignments"]}


class TestParallelDispatch(unittest.TestCase):

    def test_independent_tasks_run_at_the_same_time(self):
        clock, barrier = Clock(), threading.Barrier(3)
        agents = [Worker("db", ["database"], clock, barrier=barrier),
                  Worker("be", ["backend"], clock, barrier=barrier),
                  Worker("fe", ["frontend"], clock, barrier=barrier)]
        report, by_id = run(agents, [task("t-db", "database"), task("t-be", "backend"), task("t-fe", "frontend")],
                            parallel=True)
        self.assertEqual(report["status_counts"]["COMPLETED"], 3)
        self.assertEqual(clock.max_running, 3)
        self.assertEqual([by_id[t]["assigned_agent"] for t in ("t-db", "t-be", "t-fe")], ["Db", "Be", "Fe"])

    def test_dependencies_still_wait(self):
        clock = Clock()
        agents = [Worker("be", ["backend"], clock), Worker("qa", ["testing"], clock),
                  Worker("fe", ["frontend"], clock)]
        report, _ = run(agents, [task("t-be", "backend"), task("t-fe", "frontend"),
                                 task("t-qa", "testing", deps=["t-be"])], parallel=True)
        self.assertEqual(report["status_counts"]["COMPLETED"], 3)
        self.assertGreaterEqual(clock.spans["t-qa"][0], clock.spans["t-be"][1])
        self.assertEqual(clock.max_running, 2)  # t-be and t-fe together, t-qa afterwards

    def test_one_agent_never_runs_two_tasks_at_once(self):
        clock = Clock()
        only = Worker("be", ["backend"], clock, delay=0.1)
        report, _ = run([only], [task("t1", "backend"), task("t2", "backend"), task("t3", "backend")],
                        parallel=True)
        self.assertEqual(report["status_counts"]["COMPLETED"], 3)
        self.assertEqual(only.max_busy, 1)

    def test_a_failing_branch_fails_over_without_stopping_the_others(self):
        clock = Clock()
        broken = Worker("be", ["backend"], clock, fail=True, score=95)
        spare = Worker("spare", ["backend"], clock, score=50)
        fe = Worker("fe", ["frontend"], clock)
        report, by_id = run([broken, spare, fe], [task("t-be", "backend"), task("t-fe", "frontend")], parallel=True)
        self.assertEqual(by_id["t-be"]["attempted_agents"], ["Be", "Spare"])
        self.assertEqual(by_id["t-be"]["assigned_agent"], "Spare")
        self.assertEqual(by_id["t-fe"]["status"], "COMPLETED")

    def test_records_keep_the_plan_order(self):
        clock = Clock()
        agents = [Worker("db", ["database"], clock, delay=0.3), Worker("fe", ["frontend"], clock, delay=0.01)]
        report, _ = run(agents, [task("t-db", "database"), task("t-fe", "frontend")], parallel=True)
        self.assertEqual([r["task_id"] for r in report["task_assignments"]], ["t-db", "t-fe"])

    def test_switched_off_runs_one_by_one(self):
        clock = Clock()
        agents = [Worker("db", ["database"], clock), Worker("fe", ["frontend"], clock)]
        with patch.dict(os.environ, {"MASTER_PARALLEL_DISPATCH": "false"}):
            report, _ = run(agents, [task("t-db", "database"), task("t-fe", "frontend")])
        self.assertEqual(report["status_counts"]["COMPLETED"], 2)
        self.assertEqual(clock.max_running, 1)

    def test_max_parallel_caps_the_threads(self):
        clock = Clock()
        agents = [Worker(name, [spec], clock) for name, spec in
                  (("db", "database"), ("be", "backend"), ("fe", "frontend"), ("qa", "testing"))]
        tasks = [task("t-db", "database"), task("t-be", "backend"), task("t-fe", "frontend"), task("t-qa", "testing")]
        report, _ = run(agents, tasks, parallel=True, max_parallel=2)
        self.assertEqual(report["status_counts"]["COMPLETED"], 4)
        self.assertLessEqual(clock.max_running, 2)


if __name__ == "__main__":
    unittest.main()
