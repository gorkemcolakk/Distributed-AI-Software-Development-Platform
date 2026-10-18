"""
Capability Evaluator & Agent Selection Algorithm.
Ranks registered agents for specific subtasks based on their capability scores (Coding, Reasoning, Context).
"""

from typing import List, Dict, Any, Optional
from src.agents.base_agent import BaseAgent, TaskCategory


class CapabilityEvaluator:
    """Evaluates agent suitability and selects optimal agent for each task."""

    def __init__(self, agents: Optional[List[BaseAgent]] = None):
        self.registered_agents: List[BaseAgent] = agents or []

    def register_agent(self, agent: BaseAgent):
        """Registers a worker agent into the master pool."""
        self.registered_agents.append(agent)

    def evaluate_and_rank(
        self,
        task_category: TaskCategory,
        required_specialty: Optional[str] = None,
        available_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Ranks all active agents for a given task category.
        If available_only=True, excludes agents in BUSY, OFFLINE, or ERROR status.
        Returns a sorted list of agents with fit scores.
        """
        unavailable_statuses = {"BUSY", "OFFLINE", "ERROR"}
        rankings = []
        for agent in self.registered_agents:
            # Check availability if filtering requested
            raw_status = getattr(agent.status, "value", str(agent.status))
            if available_only and raw_status in unavailable_statuses:
                continue

            fit_score = agent.capabilities.calculate_fit_score(task_category)
            
            # Bonus points for matching domain specialty
            if required_specialty and required_specialty in agent.capabilities.specialties:
                fit_score = min(100.0, fit_score + 5.0)

            rankings.append({
                "agent": agent,
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "model_name": agent.model_name,
                "fit_score": fit_score,
                "status": raw_status,
                "active_task_count": len(agent.current_tasks)
            })

        # Sort by fit_score descending, then by active_task_count ascending
        rankings.sort(key=lambda x: (x["fit_score"], -x["active_task_count"]), reverse=True)
        return rankings

    def select_best_agent(
        self,
        task_category: TaskCategory,
        required_specialty: Optional[str] = None,
        available_only: bool = True
    ) -> Optional[BaseAgent]:
        """Selects the best available agent for a task. Returns None if no suitable agent found."""
        rankings = self.evaluate_and_rank(task_category, required_specialty, available_only=available_only)
        if not rankings:
            return None
        return rankings[0]["agent"]
