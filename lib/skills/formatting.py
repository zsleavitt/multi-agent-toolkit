"""Shared response formatting for MAT skills."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mat_runtime.router import MAT2Response


def format_success(response: "MAT2Response", label: str) -> str:
    """Format a successful response for display."""
    result = response.result or {}
    output = result.get("output", "")
    files_modified = result.get("files_modified", [])

    lines = [f"## {label}", ""]

    if output:
        lines.extend(["### Output", "", output.strip(), ""])

    if files_modified:
        lines.extend(["### Files Modified", ""])
        for f in files_modified:
            lines.append(f"- `{f}`")
        lines.append("")

    return "\n".join(lines)


def format_error(response: "MAT2Response", label: str) -> str:
    """Format an error response for display."""
    error = response.error or {}
    code = error.get("code", "unknown")
    message = error.get("message", "An unknown error occurred")

    lines = [f"## Error: {label}", "", f"**Code:** `{code}`", "", f"**Message:** {message}", ""]

    suggestions = {
        "agent_not_found": ["Run `python -m mat_runtime list-agents` to see available agents"],
        "timeout": [
            "The task took too long to complete",
            "Try breaking it into smaller, more focused tasks",
            "Increase the timeout with `--timeout-ms`",
        ],
        "execution_error": [
            "Check that the required CLI tool is installed (`bin/setup --check`)",
            "Verify the CLI tool is authenticated",
        ],
    }

    if code in suggestions:
        lines.extend(["### Suggestions", ""])
        for s in suggestions[code]:
            lines.append(f"- {s}")
        lines.append("")

    return "\n".join(lines)
