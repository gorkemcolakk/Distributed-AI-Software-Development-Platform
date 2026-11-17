"""
Requirements Analyzer & Task Decomposition Engine.
Decomposes long software requirements documents into structured subtasks with clear dependencies.
"""

from typing import Dict, Any, List
import uuid
from src.agents.base_agent import TaskCategory


class RequirementsAnalyzer:
    """Decomposes high-level requirements into execution tasks for worker agents."""

    def decompose(self, requirement_text: str, project_title: str = "Generated Software System") -> Dict[str, Any]:
        """
        Parses requirements document and outputs a structured DAG of subtasks.
        """
        req_id = f"req-{uuid.uuid4().hex[:6]}"
        
        # Standard software development lifecycle decomposition DAG
        tasks = [
            {
                "task_id": "task-req-1",
                "title": "System Specification & Architecture Design",
                "category": TaskCategory.REQUIREMENTS.value,
                "description": (
                    f"Analyze requirement spec for '{project_title}' and generate a concise "
                    "FastAPI architecture skeleton with /health and 2 core resource endpoints (under 45 lines)."
                ),
                "dependencies": [],
                "required_specialty": "architecture"
            },
            {
                "task_id": "task-db-1",
                "title": "Database Schema & Migration Definition",
                "category": TaskCategory.DATABASE.value,
                "description": (
                    "Design simple SQLite 3 tables, relationships, and indexes based on architecture spec. "
                    "IMPORTANT: Do NOT use CHECK constraints, triggers, or subqueries; "
                    "use only simple CREATE TABLE IF NOT EXISTS and CREATE INDEX statements."
                ),
                "dependencies": ["task-req-1"],
                "required_specialty": "database"
            },
            {
                "task_id": "task-be-1",
                "title": "Core Backend API Implementation",
                "category": TaskCategory.BACKEND.value,
                "description": (
                    "Implement a concise FastAPI service (under 50 lines) with /health, "
                    "GET and POST endpoints using Pydantic BaseModel and in-memory dict storage."
                ),
                "dependencies": ["task-db-1"],
                "required_specialty": "backend"
            },
            {
                "task_id": "task-fe-1",
                "title": "Frontend User Interface & Components",
                "category": TaskCategory.FRONTEND.value,
                "description": (
                    "Develop a concise responsive HTML5 UI page with header, main, form, input, button, and ul."
                ),
                "dependencies": ["task-be-1"],
                "required_specialty": "frontend"
            },
            {
                "task_id": "task-qa-1",
                "title": "Automated Testing & Quality Assurance",
                "category": TaskCategory.TESTING.value,
                "description": (
                    "Write 3 concise, self-contained pytest unit test functions (test_normal, test_invalid, "
                    "test_edge, under 35 lines total) using simple assert statements."
                ),
                "dependencies": ["task-fe-1"],
                "required_specialty": "testing"
            },
            {
                "task_id": "task-int-1",
                "title": "Code Review, Integration & Deployment Package",
                "category": TaskCategory.INTEGRATION.value,
                "description": "Review code quality, resolve integration conflicts, assemble final build package and documentation.",
                "dependencies": ["task-qa-1"],
                "required_specialty": "integration"
            }
        ]

        return {
            "requirement_id": req_id,
            "project_title": project_title,
            "raw_requirement": requirement_text,
            "total_tasks": len(tasks),
            "tasks": tasks
        }
