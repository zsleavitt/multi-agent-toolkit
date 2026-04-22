# mat_runtime/swarm/types.py
"""Core types for Swarm runtime."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from mat_runtime.adapters import InvocationResult


@dataclass
class SwarmTask:
    """Task submitted to a Swarm for parallel dispatch."""

    instruction: str
    op: str = "codex.implement"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timeout_ms: int | None = None


@dataclass
class CandidateResult:
    """Result from a single candidate in the swarm.

    For parallel_model mode: response contains InvocationResult from CLI adapter.
    For variant mode: variant_output contains the MAT2Response result dict.
    """

    candidate: str  # CLI adapter name or agent variant name
    ok: bool
    response: InvocationResult | None  # Used in parallel_model mode
    duration_ms: int
    error: str | None = None
    variant_output: dict[str, Any] | None = None  # Used in variant mode


@dataclass
class SwarmResult:
    """Result of swarm dispatch with consensus applied."""

    ok: bool
    consensus_strategy: str
    winning_candidate: str | None
    output: Any
    correlation_id: str
    duration_ms: int
    candidate_results: list[CandidateResult]
    error: dict[str, Any] | None = None
