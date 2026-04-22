# mat_runtime/swarm/tests/test_swarm_integration.py
"""Integration tests for Swarm with real agent definitions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mat_runtime.swarm import Swarm


def _write_definition(data: dict) -> Path:
    """Write a definition to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestSwarmIntegration:
    """Integration tests with real agent definitions."""

    @pytest.fixture
    def repo_root(self) -> Path:
        """Find repo root by walking up from test file."""
        current = Path(__file__).resolve()
        while current.parent != current:
            if (current / "agents").is_dir():
                return current
            current = current.parent
        pytest.skip("Could not find repo root with agents/ directory")

    def test_swarm_loads_real_variant_agents(self, repo_root: Path):
        """Swarm can load real variant agent definitions."""
        path = _write_definition({
            "name": "real-variants",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "ruby-engineer"],
            "consensus_strategy": "return-all",
        })

        try:
            swarm = Swarm(definition_path=path, repo_root=repo_root)

            assert swarm.name == "real-variants"
            assert swarm.definition.dispatch_mode == "variant"
            assert "python-engineer" in swarm._agents
            assert "ruby-engineer" in swarm._agents

            # Verify variant_of inheritance was resolved
            python_agent = swarm._agents["python-engineer"]
            assert python_agent.variant_of == "coder"
            assert python_agent.cli == "codex"

            ruby_agent = swarm._agents["ruby-engineer"]
            assert ruby_agent.variant_of == "coder"
            assert ruby_agent.cli == "codex"
        finally:
            path.unlink()

    def test_swarm_rejects_nonexistent_variant(self, repo_root: Path):
        """Swarm rejects variants that don't exist in agents/."""
        path = _write_definition({
            "name": "bad-variants",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "nonexistent-agent"],
            "consensus_strategy": "return-all",
        })

        try:
            with pytest.raises(ValueError, match="Unknown agent variant"):
                Swarm(definition_path=path, repo_root=repo_root)
        finally:
            path.unlink()
