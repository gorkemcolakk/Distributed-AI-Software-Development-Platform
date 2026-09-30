"""
Base Agent Interface for Distributed AI Software Development Platform.
Defines capability metrics, status tracking, and standard task execution interfaces.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid
import time


class AgentStatus(Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class TaskCategory(Enum):
    REQUIREMENTS = "REQUIREMENTS"
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    DATABASE = "DATABASE"
    TESTING = "TESTING"
    INTEGRATION = "INTEGRATION"
    DOCUMENTATION = "DOCUMENTATION"


@dataclass
class AgentCapabilityProfile:
    coding_score: float         # 0-100 score for code generation accuracy & syntax
    reasoning_score: float      # 0-100 score for architectural logic & problem decomposition
    context_capacity: float     # 0-100 score representing context window & multi-file awareness
    specialties: List[str] = field(default_factory=list)

    def calculate_fit_score(self, task_category: TaskCategory) -> float:
        """
        Calculates weighted suitability score for a given task category based on model capability strengths.
        """
        weights = {
            TaskCategory.REQUIREMENTS: {"reasoning": 0.60, "context": 0.30, "coding": 0.10},
            TaskCategory.FRONTEND:     {"coding": 0.50, "context": 0.30, "reasoning": 0.20},
            TaskCategory.BACKEND:      {"coding": 0.45, "reasoning": 0.35, "context": 0.20},
            TaskCategory.DATABASE:     {"reasoning": 0.45, "coding": 0.40, "context": 0.15},
            TaskCategory.TESTING:      {"coding": 0.50, "reasoning": 0.30, "context": 0.20},
            TaskCategory.INTEGRATION:  {"reasoning": 0.50, "coding": 0.30, "context": 0.20},
            TaskCategory.DOCUMENTATION:{"context": 0.50, "reasoning": 0.35, "coding": 0.15}
        }
        
        w = weights.get(task_category, {"coding": 0.34, "reasoning": 0.33, "context": 0.33})
        
        score = (
            self.coding_score * w["coding"] +
            self.reasoning_score * w["reasoning"] +
            self.context_capacity * w["context"]
        )
        return round(score, 2)


@dataclass
class TaskResult:
    task_id: str
    agent_id: str
    status: str
    output_artifacts: Dict[str, Any]
    logs: List[str]
    execution_time_seconds: float
    error_message: Optional[str] = None


class BaseAgent:
    """Abstract Base Class for all LLM-powered Distributed Worker Agents."""

    def __init__(self, agent_id: str, name: str, model_name: str, capability_profile: AgentCapabilityProfile):
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.name = name
        self.model_name = model_name
        self.capabilities = capability_profile
        self.status = AgentStatus.IDLE
        self.current_tasks: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "model_name": self.model_name,
            "status": self.status.value,
            "capabilities": {
                "coding": self.capabilities.coding_score,
                "reasoning": self.capabilities.reasoning_score,
                "context_capacity": self.capabilities.context_capacity,
                "specialties": self.capabilities.specialties
            },
            "active_tasks": len(self.current_tasks)
        }

    def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """
        Executes an assigned software subtask.
        Must be overridden by specialized agent subclasses.
        """
        self.status = AgentStatus.BUSY
        task_id = task.get("task_id", f"task-{uuid.uuid4().hex[:6]}")
        self.current_tasks.append(task_id)
        start_time = time.time()
        
        logs = [f"[{self.name}] Starting execution for task '{task_id}': {task.get('title')}"]
        
        try:
            artifacts = self._process(task, logs)
            execution_time = time.time() - start_time
            self.status = AgentStatus.IDLE
            self.current_tasks.remove(task_id)
            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                status="SUCCESS",
                output_artifacts=artifacts,
                logs=logs,
                execution_time_seconds=round(execution_time, 2)
            )
        except Exception as e:
            execution_time = time.time() - start_time
            self.status = AgentStatus.ERROR
            if task_id in self.current_tasks:
                self.current_tasks.remove(task_id)
            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                status="FAILED",
                output_artifacts={},
                logs=logs,
                execution_time_seconds=round(execution_time, 2),
                error_message=str(e)
            )

    def _process(self, task: Dict[str, Any], logs: List[str]) -> Dict[str, Any]:
        """Subclasses override this method to provide LLM-specific processing."""
        raise NotImplementedError("Subclasses must implement _process method.")
