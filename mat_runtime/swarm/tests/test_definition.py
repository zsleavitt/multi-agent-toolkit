# mat_runtime/swarm/tests/test_definition.py
"""Tests for swarm definition loading."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mat_runtime.swarm.definition import (
    ConstraintsConfig,
    SwarmDefinition,
    load_swarm_definition,
)


def _write_definition(data: dict) -> Path:
    """Write a definition to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestLoadSwarmDefinition:
    """Tests for load_swarm_definition()."""

    def test_load_valid_parallel_model_definition(self):
        """Load a valid parallel_model swarm definition."""
        path = _write_definition({
            "schema_version": "1.0.0",
            "name": "test-swarm",
            "description": "Test swarm",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex", "gemini"],
            "consensus_strategy": "first-complete",
            "constraints": {
                "timeout_ms": 120000
            }
        })

        definition = load_swarm_definition(path)

        assert definition.name == "test-swarm"
        assert definition.description == "Test swarm"
        assert definition.dispatch_mode == "parallel_model"
        assert definition.candidates == ["claude", "codex", "gemini"]
        assert definition.consensus_strategy == "first-complete"
        assert definition.constraints.timeout_ms == 120000
        assert definition.source_path == path

        path.unlink()

    def test_load_minimal_definition(self):
        """Load definition with only required fields."""
        path = _write_definition({
            "name": "minimal",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "first-complete",
        })

        definition = load_swarm_definition(path)

        assert definition.name == "minimal"
        assert definition.description is None
        assert definition.constraints.timeout_ms is None
        assert definition.schema_version == "1.0.0"

        path.unlink()

    def test_reject_variant_mode(self):
        """Reject variant dispatch mode (not supported in MAT-46)."""
        path = _write_definition({
            "name": "variant-swarm",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "ruby-engineer"],
            "consensus_strategy": "return-all",
        })

        with pytest.raises(ValueError, match="dispatch_mode 'variant' not supported"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_majority_vote(self):
        """Reject majority-vote consensus (not implemented in MAT-46)."""
        path = _write_definition({
            "name": "majority-swarm",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex", "gemini"],
            "consensus_strategy": "majority-vote",
        })

        with pytest.raises(ValueError, match="majority-vote' not implemented"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_invalid_consensus_for_mode(self):
        """Reject consensus strategy not valid for parallel_model."""
        path = _write_definition({
            "name": "invalid-consensus",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "return-all",
        })

        with pytest.raises(ValueError, match="not valid for parallel_model"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_fewer_than_two_candidates(self):
        """Reject swarm with fewer than 2 candidates."""
        path = _write_definition({
            "name": "single-candidate",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude"],
            "consensus_strategy": "first-complete",
        })

        with pytest.raises(ValueError, match="at least 2 candidates"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_missing_name(self):
        """Reject definition missing name."""
        path = _write_definition({
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "first-complete",
        })

        with pytest.raises(ValueError, match="missing required field: name"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_missing_dispatch_mode(self):
        """Reject definition missing dispatch_mode."""
        path = _write_definition({
            "name": "no-mode",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "first-complete",
        })

        with pytest.raises(ValueError, match="missing required field: dispatch_mode"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_missing_consensus_strategy(self):
        """Reject definition missing consensus_strategy."""
        path = _write_definition({
            "name": "no-consensus",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
        })

        with pytest.raises(ValueError, match="missing required field: consensus_strategy"):
            load_swarm_definition(path)

        path.unlink()

    def test_file_not_found(self):
        """Raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_swarm_definition("/nonexistent/path.json")

    def test_invalid_json(self):
        """Raise JSONDecodeError for invalid JSON."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("not valid json {")
        f.close()
        path = Path(f.name)

        with pytest.raises(json.JSONDecodeError):
            load_swarm_definition(path)

        path.unlink()
