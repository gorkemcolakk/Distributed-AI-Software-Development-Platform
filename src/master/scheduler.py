"""
Task Scheduler & Dependency Manager.
Coordinates execution order based on task DAG dependencies and agent capability scores.
"""

from typing import List, Dict, Any, Set


class TaskScheduler:
    """Schedules subtasks respecting dependency graph constraints."""

    def __init__(self):
        self.completed_tasks: Set[str] = set()

    def get_executable_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Returns tasks whose dependencies have all been satisfied."""
        executable = []
        for task in tasks:
            task_id = task["task_id"]
            if task_id in self.completed_tasks:
                continue
            
            dependencies = task.get("dependencies", [])
            if all(dep in self.completed_tasks for dep in dependencies):
                executable.append(task)

        return executable

    def mark_completed(self, task_id: str):
        """Marks a task as successfully completed."""
        self.completed_tasks.add(task_id)

    def is_all_completed(self, tasks: List[Dict[str, Any]]) -> bool:
        """Checks if all tasks in the list have completed."""
        return len(self.completed_tasks) == len(tasks)
