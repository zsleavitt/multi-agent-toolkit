"""Tests for skills.lib.formatting module."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skills.lib.formatting import format_error, format_success


@dataclass
class MockMAT2Response:
    """Mock MAT2Response for testing."""

    ok: bool
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class TestFormatSuccess:
    """Tests for format_success function."""

    def test_with_output_only(self) -> None:
        response = MockMAT2Response(
            ok=True,
            result={"output": "Task completed successfully."},
        )
        result = format_success(response, "Development")  # type: ignore[arg-type]

        assert "## Development" in result
        assert "### Output" in result
        assert "Task completed successfully." in result
        assert "### Files Modified" not in result

    def test_with_files_modified_only(self) -> None:
        response = MockMAT2Response(
            ok=True,
            result={"files_modified": ["src/main.py", "src/utils.py"]},
        )
        result = format_success(response, "Test Results")  # type: ignore[arg-type]

        assert "## Test Results" in result
        assert "### Files Modified" in result
        assert "- `src/main.py`" in result
        assert "- `src/utils.py`" in result
        assert "### Output" not in result

    def test_with_output_and_files(self) -> None:
        response = MockMAT2Response(
            ok=True,
            result={
                "output": "All tests passed.",
                "files_modified": ["tests/test_app.py"],
            },
        )
        result = format_success(response, "Testing")  # type: ignore[arg-type]

        assert "## Testing" in result
        assert "### Output" in result
        assert "All tests passed." in result
        assert "### Files Modified" in result
        assert "- `tests/test_app.py`" in result

    def test_with_empty_result(self) -> None:
        response = MockMAT2Response(ok=True, result={})
        result = format_success(response, "Plan")  # type: ignore[arg-type]

        assert "## Plan" in result
        assert "### Output" not in result
        assert "### Files Modified" not in result

    def test_with_none_result(self) -> None:
        response = MockMAT2Response(ok=True, result=None)
        result = format_success(response, "Diagnosis")  # type: ignore[arg-type]

        assert "## Diagnosis" in result


class TestFormatError:
    """Tests for format_error function."""

    def test_agent_not_found_error(self) -> None:
        response = MockMAT2Response(
            ok=False,
            error={"code": "agent_not_found", "message": "Agent 'foo' not found"},
        )
        result = format_error(response, "foo")  # type: ignore[arg-type]

        assert "## Error: foo" in result
        assert "**Code:** `agent_not_found`" in result
        assert "Agent 'foo' not found" in result
        assert "### Suggestions" in result
        assert "list-agents" in result

    def test_timeout_error(self) -> None:
        response = MockMAT2Response(
            ok=False,
            error={"code": "timeout", "message": "Task timed out after 300000ms"},
        )
        result = format_error(response, "orchestrator")  # type: ignore[arg-type]

        assert "## Error: orchestrator" in result
        assert "**Code:** `timeout`" in result
        assert "### Suggestions" in result
        assert "took too long" in result
        assert "smaller, more focused tasks" in result
        assert "--timeout-ms" in result

    def test_execution_error(self) -> None:
        response = MockMAT2Response(
            ok=False,
            error={"code": "execution_error", "message": "CLI tool failed"},
        )
        result = format_error(response, "coder")  # type: ignore[arg-type]

        assert "## Error: coder" in result
        assert "**Code:** `execution_error`" in result
        assert "### Suggestions" in result
        assert "bin/setup --check" in result
        assert "authenticated" in result

    def test_unknown_error_code(self) -> None:
        response = MockMAT2Response(
            ok=False,
            error={"code": "some_new_error", "message": "Something went wrong"},
        )
        result = format_error(response, "reviewer")  # type: ignore[arg-type]

        assert "## Error: reviewer" in result
        assert "**Code:** `some_new_error`" in result
        assert "Something went wrong" in result
        assert "### Suggestions" not in result

    def test_missing_error_fields(self) -> None:
        response = MockMAT2Response(ok=False, error={})
        result = format_error(response, "tester")  # type: ignore[arg-type]

        assert "## Error: tester" in result
        assert "**Code:** `unknown`" in result
        assert "An unknown error occurred" in result

    def test_none_error(self) -> None:
        response = MockMAT2Response(ok=False, error=None)
        result = format_error(response, "agent")  # type: ignore[arg-type]

        assert "## Error: agent" in result
        assert "**Code:** `unknown`" in result
