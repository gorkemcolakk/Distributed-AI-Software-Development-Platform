"""
Task Scheduler & Dependency Manager.
Coordinates execution order based on task DAG dependencies and agent capability scores.
"""

from typing import List, Dict, Any, Set, Optional
import uuid


class DagValidationError(ValueError):
    """The task list is structurally broken (duplicate/empty task_id, malformed dependencies).
    Such a graph cannot be scheduled at all, so the whole run is rejected."""


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

    def find_cycles(self, tasks: List[Dict[str, Any]]) -> List[List[str]]:
        """Returns each dependency cycle as a sorted list of task_ids (Tarjan SCC).
        Dependencies on undefined task_ids are ignored here; they are reported separately."""
        graph = {t["task_id"]: [d for d in t.get("dependencies", [])] for t in tasks}
        index: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        stack: List[str] = []
        on_stack: Set[str] = set()
        cycles: List[List[str]] = []

        def visit(node: str):
            index[node] = lowlink[node] = len(index)
            stack.append(node)
            on_stack.add(node)
            for dep in graph[node]:
                if dep not in graph:
                    continue
                if dep not in index:
                    visit(dep)
                    lowlink[node] = min(lowlink[node], lowlink[dep])
                elif dep in on_stack:
                    lowlink[node] = min(lowlink[node], index[dep])
            if lowlink[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1 or node in graph[node]:
                    cycles.append(sorted(component))

        for task_id in graph:
            if task_id not in index:
                visit(task_id)
        return cycles

    @staticmethod
    def _check_structure(tasks: List[Dict[str, Any]]):
        """Raises DagValidationError for problems that make the graph unschedulable."""
        if not isinstance(tasks, list):
            raise DagValidationError("Görev listesi bir liste olmalı.")
        seen: Set[str] = set()
        duplicates: List[str] = []
        for position, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise DagValidationError(f"{position}. görev bir sözlük değil.")
            task_id = task.get("task_id")
            if not isinstance(task_id, str) or not task_id.strip():
                raise DagValidationError(f"{position}. görevin task_id değeri boş veya geçersiz.")
            deps = task.get("dependencies", [])
            if not isinstance(deps, list) or not all(isinstance(d, str) and d.strip() for d in deps):
                raise DagValidationError(f"'{task_id}' görevinin dependencies alanı task_id listesi olmalı.")
            if task_id in seen and task_id not in duplicates:
                duplicates.append(task_id)
            seen.add(task_id)
        if duplicates:
            raise DagValidationError(f"Aynı task_id birden fazla kez tanımlanmış: {', '.join(duplicates)}")

    def validate_graph(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Pre-execution DAG check (S3-04).

        - Structural errors raise DagValidationError (whole run rejected).
        - Tasks in a dependency cycle or depending on an undefined task_id are
          returned in ``rejected`` with their reasons.
        - Every task that transitively depends on a rejected task is returned in
          ``blocked_downstream`` (direct upstream culprits as values).
        Neither group may ever be dispatched to an agent.
        """
        self._check_structure(tasks)
        known = {t["task_id"] for t in tasks}

        missing: Dict[str, List[str]] = {}
        for task in tasks:
            undefined = [d for d in task.get("dependencies", []) if d not in known]
            if undefined:
                missing[task["task_id"]] = undefined

        cycles = self.find_cycles(tasks)
        cycle_of = {tid: cycle for cycle in cycles for tid in cycle}

        rejected: Dict[str, List[str]] = {}
        for task in tasks:
            task_id = task["task_id"]
            reasons = []
            if task_id in cycle_of:
                reasons.append(f"döngüsel bağımlılık tespit edildi: {' <-> '.join(cycle_of[task_id])}")
            for dep in missing.get(task_id, []):
                reasons.append(f"bağımlı olduğu görev '{dep}' tanımlı değil")
            if reasons:
                rejected[task_id] = reasons

        # Propagate to every transitive dependent of a rejected task
        dependents: Dict[str, List[str]] = {tid: [] for tid in known}
        for task in tasks:
            for dep in task.get("dependencies", []):
                if dep in dependents:
                    dependents[dep].append(task["task_id"])

        unusable: Set[str] = set(rejected)
        frontier = list(rejected)
        while frontier:
            node = frontier.pop()
            for child in dependents[node]:
                if child not in unusable:
                    unusable.add(child)
                    frontier.append(child)

        blocked_downstream: Dict[str, List[str]] = {}
        for task in tasks:
            task_id = task["task_id"]
            if task_id in unusable and task_id not in rejected:
                blocked_downstream[task_id] = [d for d in task.get("dependencies", []) if d in unusable]

        return {
            "is_valid": not rejected,
            "cycles": cycles,
            "missing_dependencies": missing,
            "rejected": rejected,
            "blocked_downstream": blocked_downstream,
        }

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
