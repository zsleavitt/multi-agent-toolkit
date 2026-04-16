#!/usr/bin/env python3
"""Validate MAT-5 Gumloop example files and embedded MAT-2 payloads."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUMLOOP_EXAMPLES = ROOT / "examples" / "gumloop"
MAT2_SCHEMA = ROOT / "schemas" / "codex-code-exec" / "v1" / "request.schema.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as e:
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    if not GUMLOOP_EXAMPLES.is_dir():
        raise SystemExit(f"Gumloop examples directory missing: {GUMLOOP_EXAMPLES}")

    # Validate all JSON files are well-formed
    json_files = list(GUMLOOP_EXAMPLES.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in {GUMLOOP_EXAMPLES}")

    for path in sorted(json_files):
        try:
            _load_json(path)
            print(f"OK json     {path.relative_to(ROOT)}")
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid JSON in {path}: {e}") from e

    # Validate embedded MAT-2 request in start-pipeline example
    start_pipeline = GUMLOOP_EXAMPLES / "start-pipeline.request.example.json"
    if start_pipeline.is_file():
        mat2_schema = _load_json(MAT2_SCHEMA)
        validator = Draft202012Validator(mat2_schema)

        payload = _load_json(start_pipeline)
        for inp in payload.get("pipeline_inputs", []):
            if inp.get("input_name") == "mat2_request_json":
                embedded = json.loads(inp["value"])
                validator.validate(embedded)
                print(f"OK mat2     {start_pipeline.relative_to(ROOT)} (embedded mat2_request_json)")
                break

    print("All MAT-5 Gumloop example checks passed.")


if __name__ == "__main__":
    main()
