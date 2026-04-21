#!/usr/bin/env python3
"""Validate MAT-42 Crew definition files."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "crew@v1"
_ENV_BUNDLE_DIR = "MAT_CREW_V1"


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
    return (root / "schemas" / "crew" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)
CREWS_DIR = ROOT / "crews"
AGENTS_DIR = ROOT / "agents"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_agent_names() -> set[str]:
    """Load all valid agent names from agents/*.md frontmatter."""
    import re
    names: set[str] = set()
    if not AGENTS_DIR.is_dir():
        return names

    # Match agents/*.md and agents/variants/*.md
    for pattern in ["*.md", "variants/*.md"]:
        for path in AGENTS_DIR.glob(pattern):
            content = path.read_text(encoding="utf-8")
            # Extract name from YAML frontmatter
            match = re.search(r"^---\s*\n.*?^name:\s*([a-z][a-z0-9-]*)", content, re.MULTILINE | re.DOTALL)
            if match:
                names.add(match.group(1))
    return names


def _extract_agent_refs(instance: dict) -> list[str]:
    """Extract all agent name references from a crew definition."""
    refs = []
    for agent in instance.get("agents", []):
        if isinstance(agent, str):
            refs.append(agent)
        elif isinstance(agent, dict):
            name = agent.get("name")
            if name:
                refs.append(name)
    return refs


def _build_registry():
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    schema_file = V1 / "crew.schema.json"
    uri = schema_file.as_uri()
    doc = _load_json(schema_file)
    registry = registry.with_resource(uri, DRAFT202012.create_resource(doc))
    return registry


def main() -> None:
    if not V1.is_dir():
        raise SystemExit(
            f"Bundle directory missing: {V1}\n"
            f"Set {_ENV_BUNDLE_DIR} or config/schema-registry.json → schema_bundles.{_BUNDLE_KEY}.root_relative"
        )

    schema = _load_json(V1 / "crew.schema.json")

    from jsonschema import Draft202012Validator

    registry = _build_registry()
    validator = Draft202012Validator(schema, registry=registry)

    # Load known agent names for semantic validation
    known_agents = _load_agent_names()
    if known_agents:
        print(f"Loaded {len(known_agents)} agent names from {AGENTS_DIR}")
    else:
        print(f"Warning: No agents found in {AGENTS_DIR}; skipping agent reference validation")

    # Validate valid examples
    valid_dir = V1 / "examples" / "valid"
    if valid_dir.is_dir():
        for path in sorted(valid_dir.glob("*.json")):
            instance = _load_json(path)
            validator.validate(instance)
            # Semantic check: verify agent references exist (skip if no agents loaded)
            if known_agents:
                for ref in _extract_agent_refs(instance):
                    if ref not in known_agents:
                        raise SystemExit(
                            f"Unknown agent '{ref}' in {path}. "
                            f"Valid agents: {sorted(known_agents)}"
                        )
            print(f"OK valid    {path.relative_to(ROOT)}")

    # Validate invalid examples (should fail)
    invalid_dir = V1 / "examples" / "invalid"
    if invalid_dir.is_dir():
        for path in sorted(invalid_dir.glob("*.json")):
            instance = _load_json(path)
            errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if not errs:
                raise SystemExit(f"Expected validation failure for {path}")
            print(f"OK invalid  {path.relative_to(ROOT)} ({errs[0].message})")

    # Validate actual crew definitions
    if CREWS_DIR.is_dir():
        seen_names: set[str] = set()
        for path in sorted(CREWS_DIR.glob("*.json")):
            instance = _load_json(path)
            errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if errs:
                raise SystemExit(
                    f"Invalid crew definition in {path}:\n  {errs[0].message}"
                )

            # Semantic check: verify agent references exist
            if known_agents:
                for ref in _extract_agent_refs(instance):
                    if ref not in known_agents:
                        raise SystemExit(
                            f"Unknown agent '{ref}' in {path}. "
                            f"Valid agents: {sorted(known_agents)}"
                        )

            name = instance.get("name")
            if name in seen_names:
                raise SystemExit(f"Duplicate crew name '{name}' in {path}")
            seen_names.add(name)

            print(f"OK crew     {path.relative_to(ROOT)} (name={name})")
    else:
        print(f"No crews directory at {CREWS_DIR}; skipping crew file validation.")

    print(f"All MAT-42 crew definition checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
