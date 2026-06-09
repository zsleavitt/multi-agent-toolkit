#!/usr/bin/env python3
"""Validate MAT-49 Hive definition files."""

from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "hive@v1"
_ENV_BUNDLE_DIR = "MAT_HIVE_V1"


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
    return (root / "schemas" / "hive" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)
HIVES_DIR = ROOT / "hives"
CREWS_DIR = ROOT / "crews"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_known_crew_refs() -> set[str]:
    """Load crew names from crews/*.json files."""
    refs: set[str] = set()
    if not CREWS_DIR.is_dir():
        return refs
    for path in CREWS_DIR.glob("*.json"):
        try:
            data = _load_json(path)
            name = data.get("name")
            if isinstance(name, str) and name:
                refs.add(name)
        except (json.JSONDecodeError, OSError):
            continue
    return refs


def _extract_crew_refs(instance: dict) -> list[str]:
    """Extract crew ref strings from a hive definition."""
    refs: list[str] = []
    for crew in instance.get("crews", []):
        if isinstance(crew, dict):
            ref = crew.get("ref")
            if isinstance(ref, str):
                refs.append(ref)
    return refs


def _check_duplicate_crew_refs(refs: list[str], path: Path) -> None:
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            raise ValueError(
                f"Duplicate crew ref '{ref}' in {path}. "
                f"Each crew can only appear once in a hive."
            )
        seen.add(ref)


def _check_crew_refs_exist(refs: list[str], known_crews: set[str], path: Path) -> None:
    if not known_crews:
        return
    for ref in refs:
        if ref not in known_crews:
            raise ValueError(
                f"Unknown crew ref '{ref}' in {path}. "
                f"Valid crews: {sorted(known_crews)}"
            )


def _check_depends_on(crews: list[dict], hive_refs: set[str], path: Path) -> None:
    for crew in crews:
        if not isinstance(crew, dict):
            continue
        ref = crew.get("ref")
        for dep in crew.get("depends_on") or []:
            if dep not in hive_refs:
                raise ValueError(
                    f"depends_on entry '{dep}' for crew '{ref}' is not a crew ref "
                    f"in this hive ({path}). Valid refs: {sorted(hive_refs)}"
                )
            if dep == ref:
                raise ValueError(
                    f"Crew '{ref}' cannot depend on itself ({path})."
                )


def _check_no_cycles(crews: list[dict], path: Path) -> None:
    """Detect circular depends_on using Kahn's algorithm."""
    deps: dict[str, list[str]] = {}
    for crew in crews:
        if not isinstance(crew, dict):
            continue
        ref = crew.get("ref")
        if not isinstance(ref, str):
            continue
        deps[ref] = list(crew.get("depends_on") or [])

    in_degree = {ref: len(dep_list) for ref, dep_list in deps.items()}
    dependents: dict[str, list[str]] = {ref: [] for ref in deps}
    for ref, dep_list in deps.items():
        for dep in dep_list:
            if dep in dependents:
                dependents[dep].append(ref)

    queue = deque(ref for ref, degree in in_degree.items() if degree == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for child in dependents[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if visited != len(deps):
        raise ValueError(
            f"Circular depends_on detected in {path}. "
            f"Crew dependency graph must be acyclic."
        )


def _check_routing_rules(instance: dict, hive_refs: set[str], path: Path) -> None:
    routing = instance.get("inter_crew_routing")
    if not isinstance(routing, dict):
        return
    for rule in routing.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        for endpoint in ("from", "to"):
            ref = rule.get(endpoint)
            if isinstance(ref, str) and ref not in hive_refs:
                raise ValueError(
                    f"inter_crew_routing.rules {endpoint} '{ref}' is not a crew ref "
                    f"in this hive ({path}). Valid refs: {sorted(hive_refs)}"
                )


def _semantic_validation(
    instance: dict,
    path: Path,
    known_crews: set[str],
) -> None:
    crews = instance.get("crews") or []
    refs = _extract_crew_refs(instance)
    hive_refs = set(refs)

    _check_duplicate_crew_refs(refs, path)
    _check_crew_refs_exist(refs, known_crews, path)
    _check_depends_on(crews, hive_refs, path)
    _check_no_cycles(crews, path)
    _check_routing_rules(instance, hive_refs, path)


def _build_registry():
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    schema_file = V1 / "hive.schema.json"
    uri = schema_file.as_uri()
    doc = _load_json(schema_file)
    registry = registry.with_resource(uri, DRAFT202012.create_resource(doc))
    return registry


def main() -> None:
    if not V1.is_dir():
        raise SystemExit(
            f"Bundle directory missing: {V1}\n"
            f"Set {_ENV_BUNDLE_DIR} or config/schema-registry.json → "
            f"schema_bundles.{_BUNDLE_KEY}.root_relative"
        )

    schema = _load_json(V1 / "hive.schema.json")

    from jsonschema import Draft202012Validator

    registry = _build_registry()
    validator = Draft202012Validator(schema, registry=registry)

    known_crews = _load_known_crew_refs()
    if known_crews:
        print(f"Loaded {len(known_crews)} crew refs from {CREWS_DIR}")
    else:
        print(f"Warning: No crews found in {CREWS_DIR}; skipping crew ref validation")

    valid_dir = V1 / "examples" / "valid"
    if valid_dir.is_dir():
        for path in sorted(valid_dir.glob("*.json")):
            instance = _load_json(path)
            validator.validate(instance)
            _semantic_validation(instance, path, known_crews)
            print(f"OK valid    {path.relative_to(ROOT)}")

    invalid_dir = V1 / "examples" / "invalid"
    if invalid_dir.is_dir():
        for path in sorted(invalid_dir.glob("*.json")):
            instance = _load_json(path)
            schema_errors = list(validator.iter_errors(instance))
            if schema_errors:
                print(
                    f"OK invalid  {path.relative_to(ROOT)} "
                    f"(schema: {schema_errors[0].message})"
                )
                continue
            try:
                _semantic_validation(instance, path, known_crews)
                raise SystemExit(f"Expected validation failure for {path}")
            except ValueError as e:
                print(f"OK invalid  {path.relative_to(ROOT)} (python: {e})")

    if HIVES_DIR.is_dir():
        seen_names: set[str] = set()
        for path in sorted(HIVES_DIR.glob("*.json")):
            instance = _load_json(path)
            errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if errs:
                raise SystemExit(
                    f"Invalid hive definition in {path}:\n  {errs[0].message}"
                )

            _semantic_validation(instance, path, known_crews)

            name = instance.get("name")
            if not isinstance(name, str) or path.stem != name:
                raise SystemExit(
                    f"Filename must match name field in {path}: "
                    f"expected {name}.json, got {path.name}"
                )

            if name in seen_names:
                raise SystemExit(f"Duplicate hive name '{name}' in {path}")
            seen_names.add(name)

            print(f"OK hive     {path.relative_to(ROOT)} (name={name})")
    else:
        print(f"No hives directory at {HIVES_DIR}; skipping hive file validation.")

    print(f"All MAT-49 hive definition checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
