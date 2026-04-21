"""Tests for crew definition loading."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mat_runtime.crew.definition import (
    AgentRef,
    CrewDefinition,
    load_crew_definition,
    _validate_hook_path,
)


class TestValidateHookPath:
    """Tests for hook path validation."""

    def test_relative_path_allowed(self) -> None:
        _validate_hook_path("scripts/hooks/on_start.sh")

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be relative"):
            _validate_hook_path("/etc/passwd")

    def test_windows_absolute_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be relative"):
            _validate_hook_path("\\Windows\\System32")

    def test_traversal_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot contain"):
            _validate_hook_path("../../../etc/passwd")

    def test_traversal_in_middle_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot contain"):
            _validate_hook_path("scripts/../../../etc/passwd")


class TestLoadCrewDefinition:
    """Tests for loading crew definitions."""

    def test_minimal_crew(self, tmp_path: Path) -> None:
        """Load a minimal valid crew definition."""
        crew_file = tmp_path / "minimal.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "test-crew",
            "agents": ["coder", "reviewer"],
        }))

        crew = load_crew_definition(crew_file)

        assert crew.name == "test-crew"
        assert len(crew.agents) == 2
        assert crew.agents[0].name == "coder"
        assert crew.agents[1].name == "reviewer"
        assert crew.routing.strategy == "round-robin"

    def test_agent_with_overrides(self, tmp_path: Path) -> None:
        """Load crew with agent override objects."""
        crew_file = tmp_path / "overrides.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "override-crew",
            "agents": [
                "coder",
                {
                    "name": "reviewer",
                    "timeout_ms": 60000,
                    "priority": 10,
                    "required_capabilities": ["security"],
                },
            ],
        }))

        crew = load_crew_definition(crew_file)

        assert crew.agents[0].name == "coder"
        assert crew.agents[0].timeout_ms is None
        assert crew.agents[1].name == "reviewer"
        assert crew.agents[1].timeout_ms == 60000
        assert crew.agents[1].priority == 10
        assert crew.agents[1].required_capabilities == ["security"]

    def test_full_crew(self, tmp_path: Path) -> None:
        """Load a fully-specified crew definition."""
        crew_file = tmp_path / "full.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "full-crew",
            "description": "A fully configured crew",
            "shared_goal": "Build the feature",
            "agents": ["coder"],
            "routing": {
                "strategy": "capability",
                "match_on": ["languages", "frameworks"],
                "fallback": "random",
                "task_assignment": {
                    "allow_reassignment": True,
                    "prefer_idle": False,
                },
            },
            "constraints": {
                "max_concurrent_agents": 2,
                "timeout_ms": 600000,
                "max_tasks": 100,
                "retry_policy": {
                    "max_retries": 3,
                    "backoff_ms": 2000,
                    "backoff_multiplier": 1.5,
                },
            },
            "hooks": {
                "on_start": "scripts/on_start.sh",
                "on_start_timeout_ms": 10000,
                "on_finish": "scripts/on_finish.sh",
            },
            "communication": {
                "shared_context": {
                    "type": "memory",
                    "ttl_ms": 60000,
                },
            },
        }))

        crew = load_crew_definition(crew_file)

        assert crew.description == "A fully configured crew"
        assert crew.shared_goal == "Build the feature"
        assert crew.routing.strategy == "capability"
        assert crew.routing.match_on == ["languages", "frameworks"]
        assert crew.routing.fallback == "random"
        assert crew.routing.allow_reassignment is True
        assert crew.routing.prefer_idle is False
        assert crew.constraints.max_concurrent_agents == 2
        assert crew.constraints.max_retries == 3
        assert crew.constraints.backoff_ms == 2000
        assert crew.hooks.on_start == "scripts/on_start.sh"
        assert crew.hooks.on_start_timeout_ms == 10000
        assert crew.communication.shared_context_type == "memory"

    def test_invalid_hook_path_rejected(self, tmp_path: Path) -> None:
        """Reject crew with unsafe hook paths."""
        crew_file = tmp_path / "bad-hooks.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "bad-crew",
            "agents": ["coder"],
            "hooks": {
                "on_start": "../../../etc/passwd",
            },
        }))

        with pytest.raises(ValueError, match="cannot contain"):
            load_crew_definition(crew_file)

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_crew_definition(tmp_path / "nonexistent.json")
