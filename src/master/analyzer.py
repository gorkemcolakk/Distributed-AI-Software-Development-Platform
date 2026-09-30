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
                "task_id": f"task-req-1",
                "title": "System Specification & Architecture Design",
                "category": TaskCategory.REQUIREMENTS.value,
                "description": f"Analyze requirement spec for '{project_title}' and generate system architecture, API endpoints, and schema design.",
                "dependencies": [],
                "required_specialty": "architecture"
            },
            {
                "task_id": f"task-db-1",
                "title": "Database Schema & Migration Definition",
                "category": TaskCategory.DATABASE.value,
                "description": "Design SQL/NoSQL schemas, tables, relationships, and seed data scripts based on architecture spec.",
                "dependencies": ["task-req-1"],
                "required_specialty": "database"
            },
            {
                "task_id": f"task-be-1",
                "title": "Core Backend API Implementation",
                "category": TaskCategory.BACKEND.value,
                "description": "Implement RESTful API endpoints, business logic, authentication, and database ORM layer.",
                "dependencies": ["task-db-1"],
                "required_specialty": "backend"
            },
            {
                "task_id": f"task-fe-1",
                "title": "Frontend User Interface & Components",
                "category": TaskCategory.FRONTEND.value,
                "description": "Develop modern responsive web UI components, connect to API endpoints, and handle state management.",
                "dependencies": ["task-be-1"],
                "required_specialty": "frontend"
            },
            {
                "task_id": f"task-qa-1",
                "title": "Automated Testing & Quality Assurance",
                "category": TaskCategory.TESTING.value,
                "description": "Write unit tests, API integration tests, and end-to-end component validation tests.",
                "dependencies": ["task-fe-1"],
                "required_specialty": "testing"
            },
            {
                "task_id": f"task-int-1",
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
