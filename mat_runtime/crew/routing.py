"""Routing strategies for task assignment."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Protocol

from mat_runtime.crew.definition import AgentRef
from mat_runtime.crew.types import CrewTask


@dataclass
class RoutingState:
    """
    Read-only state passed to routing strategies.

    Strategies read this but never mutate it. The Crew class
    maintains and updates this state.
    """

    task_count: int = 0
    agent_task_counts: dict[str, int] = field(default_factory=dict)
    last_agent: str | None = None


class RoutingStrategy(Protocol):
    """Protocol for routing strategy implementations."""

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        """
        Select an agent for a task.

        Args:
            agents: Available agents to choose from.
            task: The task to be assigned.
            state: Current routing state (read-only).

        Returns:
            The selected agent.
        """
        ...


class RoundRobinStrategy:
    """Cycles through agents in order."""

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        index = state.task_count % len(agents)
        return agents[index]


class PriorityStrategy:
    """Selects agent with highest priority."""

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        return max(agents, key=lambda a: a.priority)


class RandomStrategy:
    """Selects a random agent."""

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        return random.choice(agents)


class CapabilityStrategy:
    """
    Matches task required_capabilities against agent specializations.

    Falls back to a secondary strategy when no match is found or
    when the task has no required_capabilities.
    """

    def __init__(
        self,
        agent_definitions: dict[str, Any],
        match_on: list[str],
        fallback: str = "round-robin",
    ):
        self._agent_defs = agent_definitions
        self._match_on = match_on
        self._fallback = self._create_fallback(fallback)

    def _create_fallback(self, strategy_name: str) -> RoutingStrategy:
        """Create the fallback strategy."""
        if strategy_name == "round-robin":
            return RoundRobinStrategy()
        elif strategy_name == "priority":
            return PriorityStrategy()
        elif strategy_name == "random":
            return RandomStrategy()
        else:
            raise ValueError(f"Unknown fallback strategy: {strategy_name}")

    def _get_agent_capabilities(self, agent_name: str) -> set[str]:
        """Extract all capability values from agent specialization."""
        agent_def = self._agent_defs.get(agent_name, {})
        spec = agent_def.get("specialization", {})

        capabilities: set[str] = set()
        for field in self._match_on:
            value = spec.get(field)
            if isinstance(value, list):
                capabilities.update(value)
            elif isinstance(value, str):
                capabilities.add(value)

        return capabilities

    def _score_agent(self, agent: AgentRef, required: set[str]) -> int:
        """Score an agent by how many required capabilities it has."""
        capabilities = self._get_agent_capabilities(agent.name)
        return len(capabilities & required)

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        # No required capabilities -> use fallback
        if not task.required_capabilities:
            return self._fallback.select(agents, task, state)

        required = set(task.required_capabilities)

        # Score all agents
        scored = [(agent, self._score_agent(agent, required)) for agent in agents]

        # Find best match
        best_score = max(score for _, score in scored)

        if best_score == 0:
            # No matches -> use fallback
            return self._fallback.select(agents, task, state)

        # Return first agent with best score
        for agent, score in scored:
            if score == best_score:
                return agent

        # Should never reach here
        return self._fallback.select(agents, task, state)


def create_routing_strategy(
    strategy: str,
    agent_definitions: dict[str, Any] | None = None,
    match_on: list[str] | None = None,
    fallback: str = "round-robin",
) -> RoutingStrategy:
    """
    Factory function to create a routing strategy.

    Args:
        strategy: Strategy name ('round-robin', 'priority', 'random', 'capability').
        agent_definitions: Agent definitions (required for capability strategy).
        match_on: Fields to match on (required for capability strategy).
        fallback: Fallback strategy for capability routing.

    Returns:
        RoutingStrategy instance.

    Raises:
        ValueError: If strategy is unknown.
    """
    if strategy == "round-robin":
        return RoundRobinStrategy()
    elif strategy == "priority":
        return PriorityStrategy()
    elif strategy == "random":
        return RandomStrategy()
    elif strategy == "capability":
        return CapabilityStrategy(
            agent_definitions=agent_definitions or {},
            match_on=match_on or [],
            fallback=fallback,
        )
    else:
        raise ValueError(f"Unknown routing strategy: {strategy}")
