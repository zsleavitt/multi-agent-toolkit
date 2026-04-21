"""Core types for Crew runtime."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CrewTask:
    """Task submitted to a Crew for execution."""

    instruction: str
    op: str = "codex.implement"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    required_capabilities: list[str] = field(default_factory=list)
    scope_paths: list[str] = field(default_factory=list)
    timeout_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrewResult:
    """Result of executing a CrewTask."""

    ok: bool
    agent_used: str
    output: Any
    correlation_id: str
    duration_ms: int
    attempts: int = 1
    retry_reasons: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
