"""
Master Agent Orchestrator.
Main entrypoint connecting decomposition, capability evaluation, task scheduling, and agent execution.
"""

from typing import Dict, Any, List, Optional
from src.master.analyzer import RequirementsAnalyzer
from src.master.capability_eval import CapabilityEvaluator
from src.master.scheduler import TaskScheduler
from src.agents.base_agent import BaseAgent, TaskCategory, TaskResult


class MasterOrchestrator:
    """Master Agent Orchestrator managing distributed multi-agent software development lifecycle."""

    def __init__(self, evaluator: Optional[CapabilityEvaluator] = None):
        self.analyzer = RequirementsAnalyzer()
        self.evaluator = evaluator or CapabilityEvaluator()
        self.scheduler = TaskScheduler()
        self.execution_history: List[TaskResult] = []

    def process_requirement(self, requirement_text: str, project_title: str) -> Dict[str, Any]:
        """
        Full orchestration pipeline:
        1. Decompose requirement into task DAG
        2. Evaluate agent capabilities and match tasks to agents
        3. Schedule and execute tasks in topological order
        4. Collect results and integrate software artifacts
        """
        decomposition = self.analyzer.decompose(requirement_text, project_title)
        tasks = decomposition["tasks"]
        assignments = []
        
        while not self.scheduler.is_all_completed(tasks):
            executable_tasks = self.scheduler.get_executable_tasks(tasks)
            if not executable_tasks:
                break
                
            for task in executable_tasks:
                category = TaskCategory(task["category"])
                specialty = task.get("required_specialty")
                
                # Evaluate and match best agent based on capability fit score
                agent = self.evaluator.select_best_agent(category, specialty)
                
                if not agent:
                    # Fallback if no specific agent registered
                    assignments.append({
                        "task_id": task["task_id"],
                        "title": task["title"],
                        "assigned_agent": None,
                        "status": "UNASSIGNED_NO_SUITABLE_AGENT"
                    })
                    self.scheduler.mark_completed(task["task_id"])
                    continue
                
                result = agent.execute_task(task)
                self.execution_history.append(result)
                self.scheduler.mark_completed(task["task_id"])
                
                assignments.append({
                    "task_id": task["task_id"],
                    "title": task["title"],
                    "assigned_agent": agent.name,
                    "model_used": agent.model_name,
                    "fit_score": agent.capabilities.calculate_fit_score(category),
                    "execution_time_seconds": result.execution_time_seconds,
                    "status": result.status
                })

        return {
            "project_title": project_title,
            "requirement_id": decomposition["requirement_id"],
            "total_tasks_processed": len(assignments),
            "task_assignments": assignments,
            "system_status": "COMPLETED"
        }
