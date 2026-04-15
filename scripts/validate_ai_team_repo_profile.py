#!/usr/bin/env python3
"""Validate MAT-9 repo profile JSON Schema and example documents (requires requirements-dev.txt)."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "ai-team-repo-profile@v1"
_ENV_BUNDLE_DIR = "MAT_AI_TEAM_REPO_PROFILE_V1"


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
    return (root / "schemas" / "ai-team-repo-profile" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_registry(schema: dict) -> object:
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    uri = (V1 / "repo-profile.schema.json").as_uri()
    return Registry().with_resource(uri, DRAFT202012.create_resource(schema))


def main() -> None:
    if not V1.is_dir():
        raise SystemExit(
            f"Bundle directory missing: {V1}\nSet {_ENV_BUNDLE_DIR} or config/schema-registry.json → schema_bundles.{_BUNDLE_KEY}.root_relative"
        )

    manifest = _load_json(V1 / "manifest.json")
    rel = manifest.get("document_schema")
    if not isinstance(rel, str) or not rel.strip():
        raise SystemExit("manifest.json must set document_schema to a relative path")
    schema_path = (V1 / rel).resolve()
    if not schema_path.is_file() or not schema_path.is_relative_to(V1):
        raise SystemExit(f"document_schema missing or escapes bundle: {rel}")

    schema = _load_json(schema_path)
    if schema.get("title") is None:
        raise SystemExit("repo-profile.schema.json should include a title for humans")

    from jsonschema import Draft202012Validator

    registry = _build_registry(schema)
    validator = Draft202012Validator(schema, registry=registry)

    valid_dir = V1 / "examples" / "valid"
    if not valid_dir.is_dir():
        raise SystemExit(f"Missing examples directory: {valid_dir}")

    for path in sorted(valid_dir.glob("*.json")):
        instance = _load_json(path)
        validator.validate(instance)
        print(f"OK profile {path.relative_to(ROOT)}")

    invalid_dir = V1 / "examples" / "invalid"
    for path in sorted(invalid_dir.glob("*.json")):
        instance = _load_json(path)
        errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
        if not errs:
            raise SystemExit(f"Expected validation failure for {path}")
        print(f"OK invalid  {path.relative_to(ROOT)} ({errs[0].message})")

    print(f"All MAT-9 schema checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
