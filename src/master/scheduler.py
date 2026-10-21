"""
Task Scheduler & Dependency Manager.
Coordinates execution order based on task DAG dependencies and agent capability scores.
"""

from typing import List, Dict, Any, Set, Optional
import uuid


class TaskScheduler:
    """Schedules subtasks respecting dependency graph constraints and run lifecycle."""

    def __init__(self, run_id: Optional[str] = None):
        self.run_id: str = run_id or f"run-{uuid.uuid4().hex[:8]}"
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()
        self.unassigned_tasks: Set[str] = set()
        self.blocked_tasks: Set[str] = set()

    def reset(self, run_id: Optional[str] = None) -> str:
        """Resets all task sets for a new execution run with an isolated run_id."""
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.unassigned_tasks.clear()
        self.blocked_tasks.clear()
        return self.run_id

    def get_processed_tasks(self) -> Set[str]:
        """Returns all tasks that have reached a terminal status for this run."""
        return self.completed_tasks | self.failed_tasks | self.unassigned_tasks | self.blocked_tasks

    def get_executable_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Returns tasks whose dependencies have all been successfully completed."""
        executable = []
        processed = self.get_processed_tasks()
        for task in tasks:
            task_id = task["task_id"]
            if task_id in processed:
                continue
            
            dependencies = task.get("dependencies", [])
            if all(dep in self.completed_tasks for dep in dependencies):
                executable.append(task)

        return executable

    def mark_completed(self, task_id: str):
        """Marks a task as successfully completed."""
        self.completed_tasks.add(task_id)

    def mark_failed(self, task_id: str):
        """Marks a task as failed."""
        self.failed_tasks.add(task_id)

    def mark_unassigned(self, task_id: str):
        """Marks a task as unassigned (no suitable/available agent)."""
        self.unassigned_tasks.add(task_id)

    def mark_blocked(self, task_id: str):
        """Marks a task as blocked due to failed/missing prerequisites."""
        self.blocked_tasks.add(task_id)

    def is_all_completed(self, tasks: List[Dict[str, Any]]) -> bool:
        """Checks if all tasks in the list have completed successfully."""
        return len(self.completed_tasks) == len(tasks)

    def is_all_finished(self, tasks: List[Dict[str, Any]]) -> bool:
        """Checks if all tasks have been processed (completed, failed, unassigned, or blocked)."""
        return len(self.get_processed_tasks()) >= len(tasks)
