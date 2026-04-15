#!/usr/bin/env python3
"""Validate MAT-6 HITL Asana JSON Schemas and example payloads (requires requirements-dev.txt)."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "hitl-asana-approval@v1"
_ENV_BUNDLE_DIR = "MAT_HITL_ASANA_APPROVAL_V1"


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
    return (root / "schemas" / "hitl-asana-approval" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_registry(trigger_schema: dict, callback_schema: dict) -> object:
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    for name, doc in (
        ("trigger.schema.json", trigger_schema),
        ("callback.schema.json", callback_schema),
    ):
        uri = (V1 / name).as_uri()
        registry = registry.with_resource(uri, DRAFT202012.create_resource(doc))
    return registry


def main() -> None:
    if not V1.is_dir():
        raise SystemExit(
            f"Bundle directory missing: {V1}\nSet {_ENV_BUNDLE_DIR} or config/schema-registry.json → schema_bundles.{_BUNDLE_KEY}.root_relative"
        )

    manifest = _load_json(V1 / "manifest.json")
    trig_rel = manifest.get("trigger_schema")
    cb_rel = manifest.get("callback_schema")
    if not isinstance(trig_rel, str) or not trig_rel.strip():
        raise SystemExit("manifest.json must set trigger_schema to a relative path")
    if not isinstance(cb_rel, str) or not cb_rel.strip():
        raise SystemExit("manifest.json must set callback_schema to a relative path")

    trigger_path = (V1 / trig_rel).resolve()
    callback_path = (V1 / cb_rel).resolve()
    for p, label in ((trigger_path, trig_rel), (callback_path, cb_rel)):
        if not p.is_file() or not p.is_relative_to(V1):
            raise SystemExit(f"{label} missing or escapes bundle: {label}")

    trigger_schema = _load_json(trigger_path)
    callback_schema = _load_json(callback_path)
    if trigger_schema.get("title") is None:
        raise SystemExit("trigger.schema.json should include a title for humans")
    if callback_schema.get("title") is None:
        raise SystemExit("callback.schema.json should include a title for humans")

    from jsonschema import Draft202012Validator

    registry = _build_registry(trigger_schema, callback_schema)
    trig_validator = Draft202012Validator(trigger_schema, registry=registry)
    cb_validator = Draft202012Validator(callback_schema, registry=registry)

    trig_valid = V1 / "examples" / "trigger-valid"
    if not trig_valid.is_dir():
        raise SystemExit(f"Missing examples directory: {trig_valid}")

    for path in sorted(trig_valid.glob("*.json")):
        instance = _load_json(path)
        trig_validator.validate(instance)
        print(f"OK trigger  {path.relative_to(ROOT)}")

    for path in sorted((V1 / "examples" / "trigger-invalid").glob("*.json")):
        instance = _load_json(path)
        errs = sorted(trig_validator.iter_errors(instance), key=lambda e: e.path)
        if not errs:
            raise SystemExit(f"Expected validation failure for {path}")
        print(f"OK invalid   {path.relative_to(ROOT)} ({errs[0].message})")

    for path in sorted((V1 / "examples" / "callback-valid").glob("*.json")):
        instance = _load_json(path)
        cb_validator.validate(instance)
        print(f"OK callback  {path.relative_to(ROOT)}")

    for path in sorted((V1 / "examples" / "callback-invalid").glob("*.json")):
        instance = _load_json(path)
        errs = sorted(cb_validator.iter_errors(instance), key=lambda e: e.path)
        if not errs:
            raise SystemExit(f"Expected validation failure for {path}")
        print(f"OK invalid   {path.relative_to(ROOT)} ({errs[0].message})")

    print(f"All MAT-6 schema checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
