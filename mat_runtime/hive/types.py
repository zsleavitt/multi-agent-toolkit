"""Core types for Hive runtime."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from mat_runtime.crew.types import CrewResult


@dataclass
class HiveTask:
    """Task submitted to a Hive for multi-crew execution."""

    instruction: str
    op: str = "codex.implement"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str | None = None
    required_capabilities: list[str] = field(default_factory=list)
    scope_paths: list[str] = field(default_factory=list)
    timeout_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrewStageResult:
    """Result from a single crew stage within a hive pipeline."""

    crew_ref: str
    ok: bool
    crew_result: CrewResult
    duration_ms: int


@dataclass
class HiveResult:
    """Result of executing a HiveTask across one or more crews."""

    ok: bool
    correlation_id: str
    stages: list[CrewStageResult]
    final_crew: str | None
    total_duration_ms: int
    agent_invocations: int
    error: dict[str, Any] | None = None


@dataclass
class HiveSession:
    """In-memory session tracking cross-crew execution state."""

    correlation_id: str
    hive_name: str
    completed_crews: set[str] = field(default_factory=set)
    stage_results: list[CrewStageResult] = field(default_factory=list)
    shared_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class HandoffContext:
    """Context passed when evaluating inter-crew handoff rules."""

    from_crew: str
    to_crew: str
    when: str
    stage_result: CrewStageResult
    shared_context: dict[str, Any]
