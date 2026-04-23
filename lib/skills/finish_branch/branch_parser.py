"""Parse work item references from git branch names."""

from __future__ import annotations

import re


def extract_work_item_ref(branch_name: str) -> str | None:
    """
    Extract work item reference from a branch name.

    Looks for patterns like:
    - MAT-42, mat-42, Mat-42 (case-insensitive)
    - PROJ-123 (Jira-style project keys)

    Args:
        branch_name: Git branch name (e.g., "feat/mat-42-crew-schema").

    Returns:
        Normalized work item reference (e.g., "MAT-42") or None if not found.
    """
    if not branch_name:
        return None

    # Pattern: word characters followed by hyphen and digits
    # Captures: MAT-42, PROJ-123, mat-42, etc.
    pattern = r"([A-Za-z]+-\d+)"
    match = re.search(pattern, branch_name)

    if not match:
        return None

    # Normalize to uppercase
    return match.group(1).upper()
