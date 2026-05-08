"""Tests for .codex/hooks/mat_context.py (GitHub #74)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / ".codex" / "hooks" / "mat_context.py"


def _run(stdin_obj: dict | str) -> tuple[int, dict]:
    payload = stdin_obj if isinstance(stdin_obj, str) else json.dumps(stdin_obj)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert proc.stderr == "", proc.stderr
    out = json.loads(proc.stdout)
    return proc.returncode, out


def test_session_start_json_contract():
    code, data = _run(
        {
            "session_id": "s1",
            "hook_event_name": "SessionStart",
            "source": "startup",
            "cwd": str(REPO_ROOT),
            "model": "test-model",
        }
    )
    assert code == 0
    assert data["continue"] is True
    assert "MAT-1" in data["systemMessage"]
    assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "MAT-2" in data["hookSpecificOutput"]["additionalContext"]


def test_user_prompt_submit_json_contract():
    code, data = _run(
        {
            "session_id": "s1",
            "hook_event_name": "UserPromptSubmit",
            "turn_id": "t1",
            "prompt": "do the thing",
            "cwd": str(REPO_ROOT),
            "model": "test-model",
        }
    )
    assert code == 0
    assert data["continue"] is True
    h = data["hookSpecificOutput"]
    assert h["hookEventName"] == "UserPromptSubmit"
    assert "lib/skills/" in h["additionalContext"]
    assert "MAT-2" in h["additionalContext"]


def test_malformed_stdin_exits_zero_session_shape():
    code, data = _run("not-json{{{")
    assert code == 0
    assert data["continue"] is True
    assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"


@pytest.mark.parametrize(
    "stdin_obj",
    [
        {"prompt": "x", "cwd": "/tmp"},
        {},
    ],
)
def test_event_fallbacks(stdin_obj: dict):
    code, data = _run(stdin_obj)
    assert code == 0
    if "prompt" in stdin_obj and "hook_event_name" not in stdin_obj:
        assert data["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    else:
        assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"
