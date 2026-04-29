#!/usr/bin/env python3
"""Validate MAT-45 Swarm definition files."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "swarm@v1"
_ENV_BUNDLE_DIR = "MAT_SWARM_V1"


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
    return (root / "schemas" / "swarm" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)
SWARMS_DIR = ROOT / "swarms"
AGENTS_DIR = ROOT / "agents"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_agent_names() -> set[str]:
    """Load all valid agent names from agents/*.md frontmatter."""
    import re
    import yaml
    names: set[str] = set()
    if not AGENTS_DIR.is_dir():
        return names

    for pattern in ["*.md", "variants/*.md"]:
        for path in AGENTS_DIR.glob(pattern):
            if path.name.lower() in ("readme.md", "index.md"):
                continue

            content = path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            end = content.find("\n---", 3)
            if end == -1:
                continue
            try:
                frontmatter = yaml.safe_load(content[4:end])
                if isinstance(frontmatter, dict) and "name" in frontmatter:
                    name = frontmatter["name"]
                    if isinstance(name, str) and re.match(r"^[a-z][a-z0-9-]*$", name):
                        names.add(name)
            except yaml.YAMLError:
                continue
    return names


def _semantic_validation(instance: dict, path: Path, known_agents: set[str]) -> None:
    """Run Python-side semantic validation (belt-and-suspenders)."""
    dispatch_mode = instance.get("dispatch_mode")
    consensus_strategy = instance.get("consensus_strategy")
    candidates = instance.get("candidates", [])

    # Check consensus strategy validity per mode
    if dispatch_mode == "variant" and consensus_strategy != "return-all":
        raise ValueError(
            f"consensus_strategy '{consensus_strategy}' is not valid for "
            f"dispatch_mode 'variant'. Use 'return-all'. ({path})"
        )

    # Check majority-vote requires >= 3 candidates
    if consensus_strategy == "majority-vote" and len(candidates) < 3:
        raise ValueError(
            f"majority-vote requires at least 3 candidates — with {len(candidates)} candidates, "
            f"any disagreement resolves to first-complete by tie-breaking. "
            f"Use first-complete directly or add a third candidate. ({path})"
        )

    # Check variant candidates exist in agents/ directory
    if dispatch_mode == "variant" and known_agents:
        for candidate in candidates:
            if candidate not in known_agents:
                raise ValueError(
                    f"Unknown agent '{candidate}' in {path}. "
                    f"For dispatch_mode 'variant', candidates must exist in agents/. "
                    f"Valid agents: {sorted(known_agents)}"
                )

    # MAT-54: model_matrix keys must be swarm candidates; non-empty matrix needs 1.1.0
    model_matrix = instance.get("model_matrix")
    if isinstance(model_matrix, dict) and model_matrix:
        schema_version = instance.get("schema_version", "1.0.0")
        if schema_version != "1.1.0":
            raise ValueError(
                f"model_matrix is set but schema_version is '{schema_version}' — "
                f"use '1.1.0' when supplying model_matrix. ({path})"
            )
        for key in model_matrix:
            if key not in candidates:
                raise ValueError(
                    f"model_matrix key '{key}' is not in candidates {list(candidates)}. ({path})"
                )


def _build_registry():
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    schema_file = V1 / "swarm.schema.json"
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

    schema = _load_json(V1 / "swarm.schema.json")

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
    examples_dir = V1 / "examples"
    for path in sorted(examples_dir.glob("*.json")):
        instance = _load_json(path)
        validator.validate(instance)
        _semantic_validation(instance, path, known_agents)
        print(f"OK valid    {path.relative_to(ROOT)}")

    # Validate invalid examples
    invalid_dir = V1 / "examples" / "invalid"
    if invalid_dir.is_dir():
        for path in sorted(invalid_dir.glob("*.json")):
            instance = _load_json(path)

            # Check if schema catches it
            schema_errors = list(validator.iter_errors(instance))
            if schema_errors:
                print(f"OK invalid  {path.relative_to(ROOT)} (schema: {schema_errors[0].message})")
                continue

            # Check if Python semantic validation catches it
            try:
                _semantic_validation(instance, path, known_agents)
                raise SystemExit(f"Expected validation failure for {path}")
            except ValueError as e:
                print(f"OK invalid  {path.relative_to(ROOT)} (python: {e})")

    # Validate actual swarm definitions
    if SWARMS_DIR.is_dir():
        seen_names: set[str] = set()
        for path in sorted(SWARMS_DIR.glob("*.json")):
            instance = _load_json(path)
            errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if errs:
                raise SystemExit(
                    f"Invalid swarm definition in {path}:\n  {errs[0].message}"
                )

            # Semantic validation
            _semantic_validation(instance, path, known_agents)

            name = instance.get("name")
            if name in seen_names:
                raise SystemExit(f"Duplicate swarm name '{name}' in {path}")
            seen_names.add(name)

            print(f"OK swarm    {path.relative_to(ROOT)} (name={name})")
    else:
        print(f"No swarms directory at {SWARMS_DIR}; skipping swarm file validation.")

    print(f"All MAT-45 swarm definition checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
