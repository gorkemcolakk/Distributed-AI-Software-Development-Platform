"""
Master Agent Orchestrator.
Main entrypoint connecting decomposition, capability evaluation, task scheduling, and agent execution.
"""

import logging
import sqlite3
from typing import Dict, Any, List, Optional
from src.master.analyzer import RequirementsAnalyzer
from src.master.capability_eval import CapabilityEvaluator
from src.master.scheduler import TaskScheduler
from src.agents.base_agent import BaseAgent, TaskCategory, TaskResult, AgentStatus
from src.master import db_manager

logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """Master Agent Orchestrator managing distributed multi-agent software development lifecycle."""

    def __init__(self, evaluator: Optional[CapabilityEvaluator] = None,
                 db_path: Optional[str] = None, persist: bool = True):
        self.persist = persist
        self.db_path = db_manager.init_db(db_path, verbose=False) if persist else None
        self.analyzer = RequirementsAnalyzer()
        self.evaluator = evaluator or CapabilityEvaluator()
        self.scheduler = TaskScheduler()
        self.execution_history: List[TaskResult] = []

    def _db(self, fn, *args, **kwargs):
        """Runs a persistence call; SQLite I/O errors are logged, never crash the run.
        ValueError (e.g. wrongly COMPLETED record) is intentionally propagated."""
        if not self.persist:
            return None
        try:
            return fn(*args, db_path=self.db_path, **kwargs)
        except sqlite3.Error as exc:
            logger.warning("SQLite persistence failed in %s: %s", fn.__name__, exc)
            return None

    def _agent_ids(self) -> Dict[str, str]:
        return {a.name: a.agent_id for a in self.evaluator.registered_agents}

    def _reset_error_agents(self):
        """Resets agents in ERROR status back to IDLE before a new run begins."""
        for agent in self.evaluator.registered_agents:
            raw_status = getattr(agent.status, "value", str(agent.status))
            if raw_status == "ERROR":
                agent.status = AgentStatus.IDLE

    def process_requirement(self, requirement_text: str, project_title: str) -> Dict[str, Any]:
        """
        Full orchestration pipeline:
        1. Reset ERROR agents to IDLE and initialize isolated run_id
        2. Decompose requirement into task DAG
        3. Evaluate agent capabilities and match tasks with failover support
        4. Schedule and execute tasks in topological order
        5. Apply deadlock protection for unsatisfied dependencies
        6. Determine dynamic system_status and return comprehensive execution report
        """
        self._reset_error_agents()
        run_id = self.scheduler.reset()

        decomposition = self.analyzer.decompose(requirement_text, project_title)
        tasks = decomposition["tasks"]
        task_map = {t["task_id"]: t for t in tasks}
        assignments = []
        assignment_by_id = {}
        agent_ids = self._agent_ids()

        self._db(db_manager.upsert_agents, self.evaluator.registered_agents)
        self._db(db_manager.create_run, run_id, project_title,
                 requirement_id=decomposition["requirement_id"], total_tasks=len(tasks))

        while not self.scheduler.is_all_finished(tasks):
            executable_tasks = self.scheduler.get_executable_tasks(tasks)
            if not executable_tasks:
                # No more executable tasks ready, break to deadlock resolution
                break

            for task in executable_tasks:
                task_id = task["task_id"]
                category = TaskCategory(task["category"])
                specialty = task.get("required_specialty")

                # Evaluate and rank candidates with availability filtering
                ranked_candidates = self.evaluator.evaluate_and_rank(
                    category, required_specialty=specialty, available_only=True
                )

                if not ranked_candidates:
                    self.scheduler.mark_unassigned(task_id)
                    record = {
                        "task_id": task_id,
                        "title": task["title"],
                        "assigned_agent": None,
                        "model_used": None,
                        "fit_score": 0.0,
                        "execution_time_seconds": 0.0,
                        "status": "UNASSIGNED",
                        "agent_result_status": None,
                        "reason": f"No available agent found for category '{category.value}'",
                        "attempted_agents": []
                    }
                    assignments.append(record)
                    assignment_by_id[task_id] = record
                    self._db(db_manager.save_task_result, run_id, task, record, agent_ids=agent_ids)
                    continue

                # Candidate failover execution
                attempted_agents = []
                attempt_log = []
                task_succeeded = False
                last_result = None
                last_agent = None

                for candidate in ranked_candidates:
                    agent = candidate["agent"]
                    attempted_agents.append(agent.name)
                    last_agent = agent

                    result = agent.execute_task(task)
                    self.execution_history.append(result)
                    last_result = result
                    attempt_log.append({
                        "agent_id": agent.agent_id,
                        "agent_name": agent.name,
                        "is_successful": result.status == "SUCCESS",
                        "error_message": result.error_message,
                        "execution_time_seconds": result.execution_time_seconds,
                    })

                    if result.status == "SUCCESS":
                        task_succeeded = True
                        break

                if task_succeeded:
                    self.scheduler.mark_completed(task_id)
                    record = {
                        "task_id": task_id,
                        "title": task["title"],
                        "assigned_agent": last_agent.name,
                        "model_used": last_agent.model_name,
                        "fit_score": last_agent.capabilities.calculate_fit_score(category),
                        "execution_time_seconds": last_result.execution_time_seconds,
                        "status": "COMPLETED",
                        "agent_result_status": "SUCCESS",
                        "reason": f"Successfully executed by '{last_agent.name}'",
                        "attempted_agents": attempted_agents
                    }
                    assignments.append(record)
                    assignment_by_id[task_id] = record
                else:
                    self.scheduler.mark_failed(task_id)
                    err_msg = last_result.error_message if (last_result and last_result.error_message) else "Execution failed"
                    record = {
                        "task_id": task_id,
                        "title": task["title"],
                        "assigned_agent": last_agent.name if last_agent else None,
                        "model_used": last_agent.model_name if last_agent else None,
                        "fit_score": last_agent.capabilities.calculate_fit_score(category) if last_agent else 0.0,
                        "execution_time_seconds": last_result.execution_time_seconds if last_result else 0.0,
                        "status": "FAILED",
                        "agent_result_status": "FAILED",
                        "reason": f"All eligible candidate agents failed: {err_msg}",
                        "attempted_agents": attempted_agents
                    }
                    assignments.append(record)
                    assignment_by_id[task_id] = record

                self._db(db_manager.save_task_result, run_id, task, record,
                         attempts=attempt_log, agent_ids=agent_ids)

        # Deadlock protection for remaining unfinished tasks
        processed = self.scheduler.get_processed_tasks()
        remaining_tasks = [t for t in tasks if t["task_id"] not in processed]

        for task in remaining_tasks:
            task_id = task["task_id"]
            deps = task.get("dependencies", [])
            block_reasons = []

            for dep in deps:
                if dep not in task_map:
                    block_reasons.append(f"bağımlı olduğu görev '{dep}' tanımlı değil")
                elif dep in self.scheduler.failed_tasks:
                    block_reasons.append(f"bağımlı olduğu görev '{dep}', durum FAILED")
                elif dep in self.scheduler.unassigned_tasks:
                    block_reasons.append(f"bağımlı olduğu görev '{dep}', durum UNASSIGNED")
                elif dep in self.scheduler.blocked_tasks:
                    block_reasons.append(f"bağımlı olduğu görev '{dep}', durum BLOCKED")
                elif dep not in self.scheduler.completed_tasks:
                    dep_status = assignment_by_id.get(dep, {}).get("status", "UNSATISFIED")
                    block_reasons.append(f"bağımlı olduğu görev '{dep}', durum {dep_status}")

            if not block_reasons:
                block_reasons.append("Çözülemeyen veya döngüsel bağımlılık")

            reason_str = "; ".join(block_reasons)
            self.scheduler.mark_blocked(task_id)
            record = {
                "task_id": task_id,
                "title": task["title"],
                "assigned_agent": None,
                "model_used": None,
                "fit_score": 0.0,
                "execution_time_seconds": 0.0,
                "status": "BLOCKED",
                "agent_result_status": None,
                "reason": reason_str,
                "attempted_agents": []
            }
            assignments.append(record)
            assignment_by_id[task_id] = record
            self._db(db_manager.save_task_result, run_id, task, record, agent_ids=agent_ids)

        # Calculate system status
        completed_count = len(self.scheduler.completed_tasks)
        failed_count = len(self.scheduler.failed_tasks)
        unassigned_count = len(self.scheduler.unassigned_tasks)
        blocked_count = len(self.scheduler.blocked_tasks)
        total_tasks = len(tasks)

        if completed_count == total_tasks:
            system_status = "COMPLETED"
        elif completed_count == 0:
            system_status = "FAILED"
        else:
            system_status = "PARTIALLY_COMPLETED"

        status_counts = {
            "COMPLETED": completed_count,
            "FAILED": failed_count,
            "UNASSIGNED": unassigned_count,
            "BLOCKED": blocked_count
        }
        self._db(db_manager.upsert_agents, self.evaluator.registered_agents)
        self._db(db_manager.finish_run, run_id, system_status, status_counts)

        return {
            "run_id": run_id,
            "project_title": project_title,
            "requirement_id": decomposition["requirement_id"],
            "total_tasks_processed": len(assignments),
            "task_assignments": assignments,
            "system_status": system_status,
            "status_counts": {
                "COMPLETED": completed_count,
                "FAILED": failed_count,
                "UNASSIGNED": unassigned_count,
                "BLOCKED": blocked_count
            }
        }
