#!/usr/bin/env python3
"""Validate MAT-1 JSON Schemas and example payloads (requires requirements-dev.txt)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "gemini-git-ops@v1"
_ENV_BUNDLE_DIR = "MAT_GEMINI_GIT_OPS_V1"


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
    return (root / "schemas" / "gemini-git-ops" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_matches_request_ops(manifest: dict, request_schema: dict) -> None:
    m_ops = set(manifest["allowed_operations"])
    req_enum = set(request_schema["properties"]["op"]["enum"])
    if m_ops != req_enum:
        raise SystemExit(
            f"manifest allowed_operations != request op enum:\n  only in manifest: {m_ops - req_enum}\n  only in schema: {req_enum - m_ops}"
        )


def _build_registry():
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    for name in ("request.schema.json", "response.schema.json"):
        uri = (V1 / name).as_uri()
        doc = _load_json(V1 / name)
        registry = registry.with_resource(uri, DRAFT202012.create_resource(doc))
    return registry


def main() -> None:
    if not V1.is_dir():
        raise SystemExit(f"Bundle directory missing: {V1}\nSet {_ENV_BUNDLE_DIR} or config/schema-registry.json → schema_bundles.{_BUNDLE_KEY}.root_relative")

    manifest = _load_json(V1 / "manifest.json")
    request_schema = _load_json(V1 / "request.schema.json")
    response_schema = _load_json(V1 / "response.schema.json")

    _manifest_matches_request_ops(manifest, request_schema)

    from jsonschema import Draft202012Validator

    registry = _build_registry()

    req_validator = Draft202012Validator(request_schema, registry=registry)
    resp_validator = Draft202012Validator(response_schema, registry=registry)

    for path in sorted((V1 / "examples" / "request-valid").glob("*.json")):
        instance = _load_json(path)
        req_validator.validate(instance)
        print(f"OK request  {path.relative_to(ROOT)}")

    for path in sorted((V1 / "examples" / "request-invalid").glob("*.json")):
        instance = _load_json(path)
        errs = sorted(req_validator.iter_errors(instance), key=lambda e: e.path)
        if not errs:
            raise SystemExit(f"Expected validation failure for {path}")
        print(f"OK invalid  {path.relative_to(ROOT)} ({errs[0].message})")

    for path in sorted((V1 / "examples" / "response-valid").glob("*.json")):
        instance = _load_json(path)
        resp_validator.validate(instance)
        print(f"OK response {path.relative_to(ROOT)}")

    print(f"All MAT-1 schema checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
