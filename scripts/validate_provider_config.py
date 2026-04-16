#!/usr/bin/env python3
"""Validate MAT-16 Provider Configuration JSON Schemas and example payloads."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "provider-config@v1"
_ENV_BUNDLE_DIR = "MAT_PROVIDER_CONFIG_V1"


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
    return (root / "schemas" / "provider-config" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_registry():
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    schema_file = V1 / "provider-config.schema.json"
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

    config_schema = _load_json(V1 / "provider-config.schema.json")

    from jsonschema import Draft202012Validator

    registry = _build_registry()
    validator = Draft202012Validator(config_schema, registry=registry)

    valid_dir = V1 / "examples" / "valid"
    invalid_dir = V1 / "examples" / "invalid"

    for path in sorted(valid_dir.glob("*.json")):
        instance = _load_json(path)
        validator.validate(instance)
        print(f"OK valid    {path.relative_to(ROOT)}")

    for path in sorted(invalid_dir.glob("*.json")):
        instance = _load_json(path)
        errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
        if not errs:
            raise SystemExit(f"Expected validation failure for {path}")
        print(f"OK invalid  {path.relative_to(ROOT)} ({errs[0].message})")

    print(f"All MAT-16 schema checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
