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
    """Parsed agent definition from agents/*.md files."""

    name: str
    description: str
    role: str
    cli: str
    allowed_mat_ops: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    timeout_ms: int | None = None
    temperature: float | None = None
    system_prompt: str = ""
    source_path: Path | None = None


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
    """Load a single agent definition from a markdown file."""
    content = path.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(content)

    return AgentDefinition(
        name=frontmatter.get("name", path.stem),
        description=frontmatter.get("description", ""),
        role=frontmatter.get("role", "worker"),
        cli=frontmatter.get("cli", "claude"),
        allowed_mat_ops=frontmatter.get("allowed_mat_ops", []),
        tools=frontmatter.get("tools", []),
        timeout_ms=frontmatter.get("timeout_ms"),
        temperature=frontmatter.get("temperature"),
        system_prompt=body,
        source_path=path,
    )


def load_agent_definitions(
    agents_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> dict[str, AgentDefinition]:
    """
    Load all agent definitions from agents/ directory.

    Args:
        agents_dir: Path to agents directory. If None, uses repo_root/agents.
        repo_root: Repository root. If None, searches up from cwd.

    Returns:
        Dict mapping agent name to AgentDefinition.
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
    for md_file in agents_path.glob("*.md"):
        agent = load_agent_definition(md_file)
        agents[agent.name] = agent

    return agents


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
