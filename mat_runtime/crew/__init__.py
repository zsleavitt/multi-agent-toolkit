"""Crew runtime - orchestration layer for multi-agent task routing."""

from mat_runtime.crew.types import CrewTask, CrewResult
from mat_runtime.crew.definition import (
    AgentRef,
    RoutingConfig,
    ConstraintsConfig,
    HooksConfig,
    CommunicationConfig,
    CrewDefinition,
    load_crew_definition,
)
from mat_runtime.crew.context import (
    ContextStore,
    MemoryContextStore,
    NullContextStore,
    create_context_store,
)
from mat_runtime.crew.hooks import HookRunner, HookResult
from mat_runtime.crew.routing import (
    RoutingState,
    RoutingStrategy,
    RoundRobinStrategy,
    PriorityStrategy,
    RandomStrategy,
    CapabilityStrategy,
    create_routing_strategy,
)
from mat_runtime.crew.crew import Crew
from mat_runtime.crew.registry import CrewRegistry

__all__ = [
    # Types
    "CrewTask",
    "CrewResult",
    # Definition
    "AgentRef",
    "RoutingConfig",
    "ConstraintsConfig",
    "HooksConfig",
    "CommunicationConfig",
    "CrewDefinition",
    "load_crew_definition",
    # Context
    "ContextStore",
    "MemoryContextStore",
    "NullContextStore",
    "create_context_store",
    # Hooks
    "HookRunner",
    "HookResult",
    # Routing
    "RoutingState",
    "RoutingStrategy",
    "RoundRobinStrategy",
    "PriorityStrategy",
    "RandomStrategy",
    "CapabilityStrategy",
    "create_routing_strategy",
    # Crew
    "Crew",
    "CrewRegistry",
]
