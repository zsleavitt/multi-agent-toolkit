# mat_runtime/swarm/__init__.py
"""Swarm runtime - parallel dispatch to multiple CLI adapters."""

from mat_runtime.swarm.types import SwarmTask, CandidateResult, SwarmResult

__all__ = [
    "SwarmTask",
    "CandidateResult",
    "SwarmResult",
]
