#!/usr/bin/env python3
"""Validate MAT-17 Agent Definition files (Markdown with YAML frontmatter)."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "agent-definition@v1"
_ENV_BUNDLE_DIR = "MAT_AGENT_DEFINITION_V1"


def resolve_bundle_dir(root: Path) -> Path:
    env = os.environ.get(_ENV_BUNDLE_DIR)
    if env:
        return Path(env).expanduser().resolve()
    cfg_path = root / "config" / "schema-registry.json"
    if cfg_path.is_file():
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        bundle = (data.get("schema_bundles") or {}).get(_BUNDLE_KEY) or {}
        rel = bundle.get("root_relative")
        if isinstance(rel, str) and rel.strip():
            return (root / rel).resolve()
    return (root / "schemas" / "agent-definition" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)
AGENTS_DIR = ROOT / "agents"
VARIANTS_DIR = AGENTS_DIR / "variants"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from Markdown content."""
    try:
        import yaml
    except ImportError:
        # Fallback to basic parsing if PyYAML not available
        match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
        if not match:
            return None, content
        # Very basic YAML parsing for simple cases
        fm_text = match.group(1)
        body = match.group(2)
        fm = {}
        for line in fm_text.split("\n"):
            if ":" in line and not line.strip().startswith("-"):
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if val.startswith("[") or val == "":
                    continue  # Skip arrays and empty for basic parser
                fm[key] = val
        return fm, body

    match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not match:
        return None, content
    fm_text = match.group(1)
    body = match.group(2)
    try:
        fm = yaml.safe_load(fm_text)
        return fm if isinstance(fm, dict) else None, body
    except yaml.YAMLError:
        return None, content


def _build_registry():
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    schema_file = V1 / "agent-frontmatter.schema.json"
    uri = schema_file.as_uri()
    doc = _load_json(schema_file)
    registry = registry.with_resource(uri, DRAFT202012.create_resource(doc))
    return registry


def _detect_circular_variants(agents: dict[str, dict]) -> list[str]:
    """
    Detect circular references in variant_of chains.

    Returns list of agent names involved in circular references.
    """
    circular: list[str] = []

    for name, fm in agents.items():
        variant_of = fm.get("variant_of")
        if not variant_of:
            continue

        # Walk the chain, tracking visited nodes
        visited: set[str] = {name}
        current = variant_of

        while current:
            if current in visited:
                circular.append(name)
                break
            visited.add(current)
            current_fm = agents.get(current)
            if not current_fm:
                break
            current = current_fm.get("variant_of")

    return circular


def main() -> None:
    if not V1.is_dir():
        raise SystemExit(
            f"Bundle directory missing: {V1}\n"
            f"Set {_ENV_BUNDLE_DIR} or config/schema-registry.json → schema_bundles.{_BUNDLE_KEY}.root_relative"
        )

    schema = _load_json(V1 / "agent-frontmatter.schema.json")

    from jsonschema import Draft202012Validator

    registry = _build_registry()
    validator = Draft202012Validator(schema, registry=registry)

    # Validate example frontmatter files (JSON)
    valid_dir = V1 / "examples" / "valid"
    invalid_dir = V1 / "examples" / "invalid"

    if valid_dir.is_dir():
        for path in sorted(valid_dir.glob("*.json")):
            instance = _load_json(path)
            validator.validate(instance)
            print(f"OK valid    {path.relative_to(ROOT)}")

    if invalid_dir.is_dir():
        for path in sorted(invalid_dir.glob("*.json")):
            instance = _load_json(path)
            errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if not errs:
                raise SystemExit(f"Expected validation failure for {path}")
            print(f"OK invalid  {path.relative_to(ROOT)} ({errs[0].message})")

    # Validate actual agent definition files
    if not AGENTS_DIR.is_dir():
        print(f"No agents directory at {AGENTS_DIR}; skipping agent file validation.")
    else:
        seen_names: set[str] = set()
        all_agents: dict[str, dict] = {}  # name -> frontmatter
        base_agents: set[str] = set()  # Names of base agents (in agents/*.md)

        # First pass: validate base agents in agents/*.md
        for path in sorted(AGENTS_DIR.glob("*.md")):
            # Skip README and other non-agent files
            if path.name.lower() == "readme.md":
                continue

            content = path.read_text(encoding="utf-8")
            fm, _ = _parse_frontmatter(content)
            if fm is None:
                raise SystemExit(f"Missing or invalid frontmatter in {path}")

            # Validate frontmatter against schema
            errs = sorted(validator.iter_errors(fm), key=lambda e: e.path)
            if errs:
                raise SystemExit(
                    f"Invalid frontmatter in {path}:\n  {errs[0].message}"
                )

            # Check name uniqueness
            name = fm.get("name")
            if name in seen_names:
                raise SystemExit(f"Duplicate agent name '{name}' in {path}")
            seen_names.add(name)
            base_agents.add(name)
            all_agents[name] = fm

            # Base agents should not have variant_of
            if fm.get("variant_of"):
                raise SystemExit(
                    f"Base agent '{name}' in {path} has variant_of set. "
                    "Base agents must not be variants. Move to agents/variants/ if this is a variant."
                )

            print(f"OK agent    {path.relative_to(ROOT)} (name={name}, role={fm.get('role')})")

        # Second pass: validate variants in agents/variants/*.md
        if VARIANTS_DIR.is_dir():
            for path in sorted(VARIANTS_DIR.glob("*.md")):
                # Skip README
                if path.name.lower() == "readme.md":
                    continue

                content = path.read_text(encoding="utf-8")
                fm, _ = _parse_frontmatter(content)
                if fm is None:
                    raise SystemExit(f"Missing or invalid frontmatter in {path}")

                # Validate frontmatter against schema
                errs = sorted(validator.iter_errors(fm), key=lambda e: e.path)
                if errs:
                    raise SystemExit(
                        f"Invalid frontmatter in {path}:\n  {errs[0].message}"
                    )

                # Check name uniqueness
                name = fm.get("name")
                if name in seen_names:
                    raise SystemExit(f"Duplicate agent name '{name}' in {path}")
                seen_names.add(name)
                all_agents[name] = fm

                # Variants must have variant_of
                variant_of = fm.get("variant_of")
                if not variant_of:
                    raise SystemExit(
                        f"Variant '{name}' in {path} is missing variant_of. "
                        "Variants must specify their base agent."
                    )

                # variant_of must reference an existing base agent
                if variant_of not in all_agents:
                    raise SystemExit(
                        f"Variant '{name}' references non-existent base agent '{variant_of}'"
                    )

                print(f"OK variant  {path.relative_to(ROOT)} (name={name}, variant_of={variant_of})")

        # Detect circular references
        circular = _detect_circular_variants(all_agents)
        if circular:
            raise SystemExit(
                f"Circular variant_of references detected: {', '.join(circular)}"
            )

    print(f"All MAT-17 agent definition checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
