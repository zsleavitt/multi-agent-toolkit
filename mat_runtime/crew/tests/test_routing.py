"""Tests for routing strategies."""

from __future__ import annotations

import pytest

from mat_runtime.crew.definition import AgentRef
from mat_runtime.crew.routing import (
    RoutingState,
    RoundRobinStrategy,
    PriorityStrategy,
    RandomStrategy,
    CapabilityStrategy,
    create_routing_strategy,
)
from mat_runtime.crew.types import CrewTask


@pytest.fixture
def agents() -> list[AgentRef]:
    """Sample agents for testing."""
    return [
        AgentRef(name="coder", priority=5),
        AgentRef(name="reviewer", priority=10),
        AgentRef(name="tester", priority=3),
    ]


@pytest.fixture
def agent_definitions() -> dict[str, dict]:
    """Mock agent definitions with specializations."""
    return {
        "coder": {
            "specialization": {
                "languages": ["python", "typescript"],
                "frameworks": ["django", "react"],
            }
        },
        "reviewer": {
            "specialization": {
                "languages": ["python"],
                "domain": "security",
            }
        },
        "tester": {
            "specialization": {
                "languages": ["python"],
                "tags": ["testing", "qa"],
            }
        },
    }


class TestRoundRobinStrategy:
    """Tests for round-robin routing."""

    def test_cycles_through_agents(self, agents: list[AgentRef]) -> None:
        strategy = RoundRobinStrategy()
        state = RoutingState()
        task = CrewTask(instruction="test")

        # First call: coder (index 0)
        result = strategy.select(agents, task, state)
        assert result.name == "coder"

        # Simulate state update
        state.task_count = 1

        # Second call: reviewer (index 1)
        result = strategy.select(agents, task, state)
        assert result.name == "reviewer"

        state.task_count = 2

        # Third call: tester (index 2)
        result = strategy.select(agents, task, state)
        assert result.name == "tester"

        state.task_count = 3

        # Fourth call: back to coder (index 0)
        result = strategy.select(agents, task, state)
        assert result.name == "coder"


class TestPriorityStrategy:
    """Tests for priority-based routing."""

    def test_selects_highest_priority(self, agents: list[AgentRef]) -> None:
        strategy = PriorityStrategy()
        state = RoutingState()
        task = CrewTask(instruction="test")

        result = strategy.select(agents, task, state)
        assert result.name == "reviewer"  # Priority 10

    def test_consistent_on_tie(self) -> None:
        """When priorities tie, selection is deterministic."""
        agents = [
            AgentRef(name="a", priority=5),
            AgentRef(name="b", priority=5),
        ]
        strategy = PriorityStrategy()
        state = RoutingState()
        task = CrewTask(instruction="test")

        # Should consistently return the same agent
        results = [strategy.select(agents, task, state) for _ in range(5)]
        assert all(r.name == results[0].name for r in results)


class TestRandomStrategy:
    """Tests for random routing."""

    def test_returns_valid_agent(self, agents: list[AgentRef]) -> None:
        strategy = RandomStrategy()
        state = RoutingState()
        task = CrewTask(instruction="test")

        for _ in range(10):
            result = strategy.select(agents, task, state)
            assert result in agents


class TestCapabilityStrategy:
    """Tests for capability-based routing."""

    def test_matches_language(
        self,
        agents: list[AgentRef],
        agent_definitions: dict[str, dict],
    ) -> None:
        strategy = CapabilityStrategy(
            agent_definitions=agent_definitions,
            match_on=["languages"],
            fallback="round-robin",
        )
        state = RoutingState()
        task = CrewTask(
            instruction="test",
            required_capabilities=["typescript"],
        )

        result = strategy.select(agents, task, state)
        assert result.name == "coder"  # Only coder has typescript

    def test_fallback_when_no_match(
        self,
        agents: list[AgentRef],
        agent_definitions: dict[str, dict],
    ) -> None:
        strategy = CapabilityStrategy(
            agent_definitions=agent_definitions,
            match_on=["languages"],
            fallback="round-robin",
        )
        state = RoutingState()
        task = CrewTask(
            instruction="test",
            required_capabilities=["rust"],  # No one has rust
        )

        # Should fall back to round-robin (first agent)
        result = strategy.select(agents, task, state)
        assert result.name == "coder"

    def test_fallback_when_no_capabilities(
        self,
        agents: list[AgentRef],
        agent_definitions: dict[str, dict],
    ) -> None:
        strategy = CapabilityStrategy(
            agent_definitions=agent_definitions,
            match_on=["languages"],
            fallback="priority",
        )
        state = RoutingState()
        task = CrewTask(instruction="test")  # No required_capabilities

        # Should fall back to priority (reviewer has highest)
        result = strategy.select(agents, task, state)
        assert result.name == "reviewer"


class TestCreateRoutingStrategy:
    """Tests for strategy factory."""

    def test_create_round_robin(self) -> None:
        strategy = create_routing_strategy("round-robin")
        assert isinstance(strategy, RoundRobinStrategy)

    def test_create_priority(self) -> None:
        strategy = create_routing_strategy("priority")
        assert isinstance(strategy, PriorityStrategy)

    def test_create_random(self) -> None:
        strategy = create_routing_strategy("random")
        assert isinstance(strategy, RandomStrategy)

    def test_create_capability(self) -> None:
        strategy = create_routing_strategy(
            "capability",
            agent_definitions={},
            match_on=["languages"],
            fallback="round-robin",
        )
        assert isinstance(strategy, CapabilityStrategy)

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown routing strategy"):
            create_routing_strategy("unknown")
