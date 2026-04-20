"""Tests for config loading, including variant resolution."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mat_runtime.config import AgentDefinition, load_agent_definitions


@pytest.fixture
def base_coder() -> AgentDefinition:
    """Sample base coder agent."""
    return AgentDefinition(
        name="coder",
        description="Code implementation agent",
        role="worker",
        cli="codex",
        allowed_mat_ops=["codex.implement", "codex.refactor"],
        tools=["read", "write", "edit", "bash"],
        temperature=0.2,
        system_prompt="You are a code implementation agent.",
    )


@pytest.fixture
def variant_without_cli(base_coder: AgentDefinition) -> AgentDefinition:
    """Variant that doesn't specify cli."""
    return AgentDefinition(
        name="ruby-engineer",
        description="Ruby specialist",
        role="",  # Will be inherited
        cli="",  # Will be inherited
        allowed_mat_ops=["codex.diagnose"],
        tools=[],  # Will be inherited
        system_prompt="You specialize in Ruby.",
        variant_of="coder",
        specialization={"domain": "backend", "languages": ["ruby"]},
    )


@pytest.fixture
def variant_with_cli(base_coder: AgentDefinition) -> AgentDefinition:
    """Variant that specifies its own cli."""
    return AgentDefinition(
        name="python-engineer",
        description="Python specialist",
        role="",
        cli="claude",  # Override
        allowed_mat_ops=[],
        tools=["read", "glob", "grep"],  # Override
        temperature=0.5,  # Override
        system_prompt="",  # Will inherit base system_prompt
        variant_of="coder",
        specialization={"domain": "backend", "languages": ["python"]},
    )


class TestAgentDefinitionResolveVariant:
    """Tests for AgentDefinition.resolve_variant()."""

    def test_variant_inherits_cli_from_base(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """Variant without cli inherits base's cli."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        assert resolved.cli == "codex"

    def test_variant_overrides_cli_if_present(
        self, base_coder: AgentDefinition, variant_with_cli: AgentDefinition
    ):
        """Variant with cli uses its own cli."""
        resolved = variant_with_cli.resolve_variant(base_coder)
        assert resolved.cli == "claude"

    def test_variant_overrides_system_prompt(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """Variant with system_prompt replaces base's system_prompt."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        assert resolved.system_prompt == "You specialize in Ruby."

    def test_variant_inherits_system_prompt_if_empty(
        self, base_coder: AgentDefinition, variant_with_cli: AgentDefinition
    ):
        """Variant without system_prompt inherits base's system_prompt."""
        resolved = variant_with_cli.resolve_variant(base_coder)
        assert resolved.system_prompt == "You are a code implementation agent."

    def test_variant_appends_allowed_mat_ops(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """Variant ops = base ops + variant ops, no duplicates."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        # Base has: implement, refactor
        # Variant adds: diagnose
        assert "codex.implement" in resolved.allowed_mat_ops
        assert "codex.refactor" in resolved.allowed_mat_ops
        assert "codex.diagnose" in resolved.allowed_mat_ops
        assert len(resolved.allowed_mat_ops) == 3

    def test_variant_appends_allowed_mat_ops_no_duplicates(
        self, base_coder: AgentDefinition
    ):
        """Appending duplicate ops doesn't create duplicates."""
        variant = AgentDefinition(
            name="test-variant",
            description="Test",
            role="",
            cli="",
            allowed_mat_ops=["codex.implement", "codex.test"],  # implement is duplicate
            variant_of="coder",
        )
        resolved = variant.resolve_variant(base_coder)
        # Base has: implement, refactor
        # Variant adds: implement (dup), test
        assert resolved.allowed_mat_ops.count("codex.implement") == 1
        assert "codex.test" in resolved.allowed_mat_ops
        assert len(resolved.allowed_mat_ops) == 3

    def test_variant_always_inherits_role(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """Role is always inherited from base, never overridden."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        assert resolved.role == "worker"

    def test_variant_replaces_tools_if_present(
        self, base_coder: AgentDefinition, variant_with_cli: AgentDefinition
    ):
        """Variant with tools replaces base's tools entirely."""
        resolved = variant_with_cli.resolve_variant(base_coder)
        assert resolved.tools == ["read", "glob", "grep"]
        assert "write" not in resolved.tools
        assert "bash" not in resolved.tools

    def test_variant_inherits_tools_if_empty(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """Variant without tools inherits base's tools."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        assert resolved.tools == ["read", "write", "edit", "bash"]

    def test_variant_overrides_temperature(
        self, base_coder: AgentDefinition, variant_with_cli: AgentDefinition
    ):
        """Variant with temperature uses its own value."""
        resolved = variant_with_cli.resolve_variant(base_coder)
        assert resolved.temperature == 0.5

    def test_variant_inherits_temperature_if_none(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """Variant without temperature inherits base's temperature."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        assert resolved.temperature == 0.2

    def test_variant_keeps_own_description(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """Variant description is not inherited."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        assert resolved.description == "Ruby specialist"

    def test_variant_keeps_specialization(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """Specialization is preserved after resolution."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        assert resolved.specialization == {"domain": "backend", "languages": ["ruby"]}

    def test_variant_keeps_variant_of(
        self, base_coder: AgentDefinition, variant_without_cli: AgentDefinition
    ):
        """variant_of is preserved after resolution."""
        resolved = variant_without_cli.resolve_variant(base_coder)
        assert resolved.variant_of == "coder"


class TestLoadAgentDefinitions:
    """Tests for load_agent_definitions() with variants."""

    def test_variant_missing_base_raises(self, tmp_path: Path):
        """ValueError when variant_of points at unknown name."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        variants_dir = agents_dir / "variants"
        variants_dir.mkdir()

        # Create variant without base
        (variants_dir / "orphan.md").write_text(
            """---
name: orphan-variant
description: References non-existent base
variant_of: nonexistent-agent
---

Orphan variant.
"""
        )

        with pytest.raises(ValueError, match="non-existent base agent"):
            load_agent_definitions(agents_dir=agents_dir)

    def test_variant_circular_reference_raises(self, tmp_path: Path):
        """ValueError on circular variant_of chain."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        variants_dir = agents_dir / "variants"
        variants_dir.mkdir()

        # Create two variants that reference each other
        (variants_dir / "circular-a.md").write_text(
            """---
name: circular-a
description: Points to circular-b
variant_of: circular-b
---

Circular A.
"""
        )
        (variants_dir / "circular-b.md").write_text(
            """---
name: circular-b
description: Points to circular-a
variant_of: circular-a
---

Circular B.
"""
        )

        with pytest.raises(ValueError, match="Circular variant_of references"):
            load_agent_definitions(agents_dir=agents_dir)

    def test_load_agent_definitions_resolves_variants(self, tmp_path: Path):
        """End-to-end: load agents/ including variants, confirm resolution."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        variants_dir = agents_dir / "variants"
        variants_dir.mkdir()

        # Create base agent
        (agents_dir / "coder.md").write_text(
            """---
name: coder
description: Code implementation agent
role: worker
cli: codex
allowed_mat_ops:
  - codex.implement
  - codex.refactor
tools:
  - read
  - write
temperature: 0.2
---

You are a code implementation agent.
"""
        )

        # Create variant
        (variants_dir / "ruby-engineer.md").write_text(
            """---
name: ruby-engineer
description: Ruby specialist
variant_of: coder
cli: codex
allowed_mat_ops:
  - codex.diagnose
specialization:
  domain: backend
  languages:
    - ruby
---

You specialize in Ruby.
"""
        )

        agents = load_agent_definitions(agents_dir=agents_dir)

        # Check base agent
        assert "coder" in agents
        assert agents["coder"].role == "worker"
        assert agents["coder"].cli == "codex"

        # Check variant was loaded and resolved
        assert "ruby-engineer" in agents
        ruby = agents["ruby-engineer"]

        # Inherited from base
        assert ruby.role == "worker"
        assert ruby.tools == ["read", "write"]
        assert ruby.temperature == 0.2

        # From variant
        assert ruby.cli == "codex"
        assert ruby.system_prompt == "You specialize in Ruby."
        assert ruby.description == "Ruby specialist"
        assert ruby.variant_of == "coder"
        assert ruby.specialization == {"domain": "backend", "languages": ["ruby"]}

        # Union of allowed_mat_ops
        assert "codex.implement" in ruby.allowed_mat_ops
        assert "codex.refactor" in ruby.allowed_mat_ops
        assert "codex.diagnose" in ruby.allowed_mat_ops

    def test_load_skips_readme(self, tmp_path: Path):
        """README.md files are skipped."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        (agents_dir / "README.md").write_text("# Agents\n\nDocumentation.")
        (agents_dir / "coder.md").write_text(
            """---
name: coder
description: Coder
role: worker
cli: codex
---

Coder.
"""
        )

        agents = load_agent_definitions(agents_dir=agents_dir)
        assert "coder" in agents
        assert len(agents) == 1  # Only coder, not README

    def test_variant_chain_resolution(self, tmp_path: Path):
        """Variants can extend other variants (chain resolution)."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        variants_dir = agents_dir / "variants"
        variants_dir.mkdir()

        # Base agent
        (agents_dir / "coder.md").write_text(
            """---
name: coder
description: Base coder
role: worker
cli: codex
allowed_mat_ops:
  - codex.implement
tools:
  - read
  - write
---

Base coder.
"""
        )

        # First-level variant
        (variants_dir / "backend-engineer.md").write_text(
            """---
name: backend-engineer
description: Backend specialist
variant_of: coder
allowed_mat_ops:
  - codex.refactor
---

Backend specialist.
"""
        )

        # Second-level variant (extends backend-engineer)
        (variants_dir / "ruby-engineer.md").write_text(
            """---
name: ruby-engineer
description: Ruby specialist
variant_of: backend-engineer
allowed_mat_ops:
  - codex.diagnose
specialization:
  domain: backend
  languages:
    - ruby
---

Ruby specialist.
"""
        )

        agents = load_agent_definitions(agents_dir=agents_dir)

        # Check chain resolution
        ruby = agents["ruby-engineer"]
        assert ruby.role == "worker"  # From coder
        assert ruby.cli == "codex"  # From coder
        assert ruby.tools == ["read", "write"]  # From coder
        assert ruby.system_prompt == "Ruby specialist."  # From ruby-engineer

        # Union of all ops in chain
        assert "codex.implement" in ruby.allowed_mat_ops  # From coder
        assert "codex.refactor" in ruby.allowed_mat_ops  # From backend-engineer
        assert "codex.diagnose" in ruby.allowed_mat_ops  # From ruby-engineer
