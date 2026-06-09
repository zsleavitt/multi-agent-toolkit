"""
MAT Runtime — Multi-Agent Toolkit runtime adapter layer.

Provides CLI-based agent invocation following the CLI delegation model (ADR 0002).
No direct API calls — each CLI tool manages its own authentication.
"""

from mat_runtime.router import AgentRouter
from mat_runtime.config import load_provider_config, load_agent_definitions
from mat_runtime.providers import AgentInvocationProvider
from mat_runtime.crew import (
    Crew,
    CrewTask,
    CrewResult,
    CrewDefinition,
    CrewRegistry,
    load_crew_definition,
)
from mat_runtime.swarm import (
    Swarm,
    SwarmTask,
    SwarmResult,
    CandidateResult,
    SwarmDefinition,
    load_swarm_definition,
)
from mat_runtime.hive import (
    Hive,
    HiveTask,
    HiveResult,
    HiveDefinition,
    HiveRegistry,
    load_hive_definition,
)

__all__ = [
    "AgentRouter",
    "AgentInvocationProvider",
    "load_provider_config",
    "load_agent_definitions",
    # Crew
    "Crew",
    "CrewTask",
    "CrewResult",
    "CrewDefinition",
    "CrewRegistry",
    "load_crew_definition",
    # Swarm
    "Swarm",
    "SwarmTask",
    "SwarmResult",
    "CandidateResult",
    "SwarmDefinition",
    "load_swarm_definition",
    # Hive
    "Hive",
    "HiveTask",
    "HiveResult",
    "HiveDefinition",
    "HiveRegistry",
    "load_hive_definition",
]
__version__ = "0.1.0"
