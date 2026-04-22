# mat_runtime/swarm/__init__.py
"""Swarm runtime - parallel dispatch to multiple CLI adapters."""

from mat_runtime.swarm.types import SwarmTask, CandidateResult, SwarmResult
from mat_runtime.swarm.definition import (
    ConstraintsConfig,
    SwarmDefinition,
    load_swarm_definition,
)
from mat_runtime.swarm.swarm import Swarm

__all__ = [
    # Types
    "SwarmTask",
    "CandidateResult",
    "SwarmResult",
    # Definition
    "ConstraintsConfig",
    "SwarmDefinition",
    "load_swarm_definition",
    # Swarm
    "Swarm",
]
