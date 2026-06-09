"""Tests for scripts/validate_hive.py semantic validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATE = ROOT / "scripts" / "validate_hive.py"
VALID_DIR = ROOT / "schemas" / "hive" / "v1" / "examples" / "valid"
INVALID_DIR = ROOT / "schemas" / "hive" / "v1" / "examples" / "invalid"

sys.path.insert(0, str(ROOT / "scripts"))
import validate_hive  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_validate_hive_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_valid_fixture_passes_semantic_validation() -> None:
    instance = _load(VALID_DIR / "dev-pipeline.json")
    known = validate_hive._load_known_crew_refs()
    validate_hive._semantic_validation(instance, VALID_DIR / "dev-pipeline.json", known)


def test_circular_dependency_fails() -> None:
    instance = _load(INVALID_DIR / "circular-depends-on.json")
    known = validate_hive._load_known_crew_refs()
    with pytest.raises(ValueError, match="Circular depends_on"):
        validate_hive._semantic_validation(
            instance, INVALID_DIR / "circular-depends-on.json", known
        )


def test_unknown_crew_ref_fails() -> None:
    instance = {
        "schema_version": "1.0.0",
        "name": "test-hive",
        "crews": [{"ref": "nonexistent-crew-xyz"}],
    }
    known = validate_hive._load_known_crew_refs()
    with pytest.raises(ValueError, match="Unknown crew ref"):
        validate_hive._semantic_validation(instance, Path("test.json"), known)


def test_invalid_examples_fail_schema_validation() -> None:
    from jsonschema import Draft202012Validator

    schema = _load(ROOT / "schemas" / "hive" / "v1" / "hive.schema.json")
    validator = Draft202012Validator(schema)

    for name in ("missing-crews.json", "invalid-crew-ref.json"):
        instance = _load(INVALID_DIR / name)
        errors = list(validator.iter_errors(instance))
        assert errors, f"Expected schema failure for {name}"
