"""Configuration loading for MAT runtime."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Try to import yaml, fall back to simple parsing if not available
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class AgentDefinition:
    """Parsed agent definition from agents/*.md files.

    For variants, fields set to None indicate "inherit from base".
    Empty string/list means "explicitly set to empty" (override, not inherit).
    """

    name: str
    description: str
    role: str
    cli: str | None = None
    allowed_mat_ops: list[str] | None = None
    tools: list[str] | None = None
    timeout_ms: int | None = None
    temperature: float | None = None
    system_prompt: str | None = None
    source_path: Path | None = None
    variant_of: str | None = None
    specialization: dict[str, Any] | None = None

    def resolve_variant(self, base: "AgentDefinition") -> "AgentDefinition":
        """
        Resolve this variant against its base agent.

        Inheritance rules (None = inherit, explicit value = override):
        - system_prompt: base if variant is None; variant replaces if not None
        - cli: variant overrides if not None, otherwise inherits
        - tools: variant replaces if not None; inherits if None
        - allowed_mat_ops: variant appends to base list (union); None = inherit only
        - role: always inherits from base; cannot be overridden
        - temperature: variant overrides if not None, otherwise inherits
        - description: variant must provide its own; does not inherit
        - timeout_ms: variant overrides if not None, otherwise inherits
        - specialization: variant-only field
        - variant_of: variant-only field
        """
        # Union of allowed_mat_ops (base + variant, no duplicates)
        base_ops = base.allowed_mat_ops or []
        variant_ops = self.allowed_mat_ops or []
        combined_ops = list(base_ops)
        for op in variant_ops:
            if op not in combined_ops:
                combined_ops.append(op)

        # For tools: None means inherit, empty list means explicitly empty
        if self.tools is not None:
            resolved_tools = list(self.tools)
        else:
            resolved_tools = list(base.tools) if base.tools else []

        return AgentDefinition(
            name=self.name,
            description=self.description,  # Must be provided by variant
            role=base.role,  # Always inherited from base
            cli=self.cli if self.cli is not None else base.cli,
            allowed_mat_ops=combined_ops,
            tools=resolved_tools,
            timeout_ms=self.timeout_ms if self.timeout_ms is not None else base.timeout_ms,
            temperature=self.temperature if self.temperature is not None else base.temperature,
            system_prompt=self.system_prompt if self.system_prompt is not None else base.system_prompt,
            source_path=self.source_path,
            variant_of=self.variant_of,
            specialization=self.specialization,
        )


@dataclass
class ProviderConfig:
    """Parsed MAT-16 provider configuration."""

    schema_version: str
    agents: dict[str, dict[str, Any]]
    routing: dict[str, str] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body_content).
    """
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    frontmatter_str = content[3 : end_match.start() + 3]
    body = content[end_match.end() + 3 :].strip()

    if HAS_YAML:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
    else:
        # Simple fallback parser for basic YAML
        frontmatter = {}
        for line in frontmatter_str.strip().split("\n"):
            if ":" in line and not line.strip().startswith("-"):
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                # Handle simple arrays
                if value.startswith("[") and value.endswith("]"):
                    value = [
                        v.strip().strip("\"'")
                        for v in value[1:-1].split(",")
                        if v.strip()
                    ]
                # Handle booleans and numbers
                elif value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                elif value.replace(".", "").replace("-", "").isdigit():
                    value = float(value) if "." in value else int(value)
                else:
                    value = value.strip("\"'")
                frontmatter[key] = value
            elif line.strip().startswith("- ") and frontmatter:
                # Handle multi-line arrays
                last_key = list(frontmatter.keys())[-1]
                if not isinstance(frontmatter[last_key], list):
                    frontmatter[last_key] = []
                frontmatter[last_key].append(line.strip()[2:].strip("\"'"))

    return frontmatter, body


def load_agent_definition(path: Path) -> AgentDefinition:
    """Load a single agent definition from a markdown file.

    Uses None for fields not present in frontmatter, allowing variants
    to distinguish "inherit from base" (None) from "explicitly empty" ([]/``).
    """
    content = path.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(content)

    # For variants, None means "inherit from base"
    # For base agents, we apply sensible defaults after loading
    is_variant = "variant_of" in frontmatter

    return AgentDefinition(
        name=frontmatter.get("name", path.stem),
        description=frontmatter.get("description", ""),
        role=frontmatter.get("role", "worker"),
        # Use None if absent (for variants to inherit); base agents get cli from frontmatter
        cli=frontmatter.get("cli"),
        # Use None if key absent; explicit [] in YAML becomes empty list
        allowed_mat_ops=frontmatter.get("allowed_mat_ops"),
        tools=frontmatter.get("tools"),
        timeout_ms=frontmatter.get("timeout_ms"),
        temperature=frontmatter.get("temperature"),
        # body is always present (may be empty string); use None only if truly absent
        system_prompt=body if body else (None if is_variant else ""),
        source_path=path,
        variant_of=frontmatter.get("variant_of"),
        specialization=frontmatter.get("specialization"),
    )


def _detect_circular_variants(
    agents: dict[str, AgentDefinition],
) -> list[str]:
    """
    Detect circular references in variant_of chains.

    Returns list of agent names involved in circular references.
    """
    circular: list[str] = []

    for name, agent in agents.items():
        if not agent.variant_of:
            continue

        # Walk the chain, tracking visited nodes
        visited: set[str] = {name}
        current = agent.variant_of

        while current:
            if current in visited:
                circular.append(name)
                break
            visited.add(current)
            current_agent = agents.get(current)
            if not current_agent:
                break
            current = current_agent.variant_of

    return circular


def load_agent_definitions(
    agents_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> dict[str, AgentDefinition]:
    """
    Load all agent definitions from agents/ directory.

    Loads base agents from agents/*.md and variants from agents/variants/*.md.
    Variants are resolved against their base agents per inheritance rules.

    Args:
        agents_dir: Path to agents directory. If None, uses repo_root/agents.
        repo_root: Repository root. If None, searches up from cwd.

    Returns:
        Dict mapping agent name to AgentDefinition (resolved variants included).

    Raises:
        ValueError: If a variant references a non-existent base agent.
        ValueError: If circular variant_of references are detected.
    """
    if agents_dir:
        agents_path = Path(agents_dir)
    elif repo_root:
        agents_path = Path(repo_root) / "agents"
    else:
        # Search up from cwd for agents/ directory
        cwd = Path.cwd()
        agents_path = cwd / "agents"
        while not agents_path.exists() and cwd.parent != cwd:
            cwd = cwd.parent
            agents_path = cwd / "agents"

    if not agents_path.exists():
        return {}

    agents: dict[str, AgentDefinition] = {}

    # Load base agents from agents/*.md (excluding README and other non-agent files)
    for md_file in agents_path.glob("*.md"):
        if md_file.name.lower() == "readme.md":
            continue
        agent = load_agent_definition(md_file)
        agents[agent.name] = agent

    # Load variants from agents/variants/*.md
    variants_path = agents_path / "variants"
    if variants_path.exists():
        for md_file in variants_path.glob("*.md"):
            if md_file.name.lower() == "readme.md":
                continue
            agent = load_agent_definition(md_file)
            agents[agent.name] = agent

    # Detect circular references before resolution
    circular = _detect_circular_variants(agents)
    if circular:
        raise ValueError(
            f"Circular variant_of references detected: {', '.join(circular)}"
        )

    # Resolve variants against their bases
    # Need to resolve in dependency order (base before variant)
    resolved: dict[str, AgentDefinition] = {}

    def resolve_agent(name: str) -> AgentDefinition:
        """Recursively resolve an agent, handling variant chains."""
        if name in resolved:
            return resolved[name]

        agent = agents.get(name)
        if agent is None:
            raise ValueError(f"Agent '{name}' not found")

        if agent.variant_of is None:
            # Base agent, no resolution needed
            resolved[name] = agent
            return agent

        # Variant: resolve the base first
        base_name = agent.variant_of
        if base_name not in agents:
            raise ValueError(
                f"Variant '{name}' references non-existent base agent '{base_name}'"
            )

        base = resolve_agent(base_name)
        resolved_agent = agent.resolve_variant(base)
        resolved[name] = resolved_agent
        return resolved_agent

    for name in agents:
        resolve_agent(name)

    return resolved


def load_provider_config(
    config_path: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> ProviderConfig | None:
    """
    Load MAT-16 provider configuration.

    Searches for:
    1. Explicit config_path
    2. repo_root/mat-config.json
    3. repo_root/.mat/config.json
    4. Search up from cwd

    Returns None if no config found.
    """
    search_paths: list[Path] = []

    if config_path:
        search_paths.append(Path(config_path))
    elif repo_root:
        root = Path(repo_root)
        search_paths.extend([
            root / "mat-config.json",
            root / ".mat" / "config.json",
        ])
    else:
        # Search up from cwd
        cwd = Path.cwd()
        while cwd.parent != cwd:
            search_paths.append(cwd / "mat-config.json")
            search_paths.append(cwd / ".mat" / "config.json")
            cwd = cwd.parent

    for path in search_paths:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return ProviderConfig(
                schema_version=data.get("schema_version", "1.0.0"),
                agents=data.get("agents", {}),
                routing=data.get("routing", {}),
                defaults=data.get("defaults", {}),
            )

    return None
