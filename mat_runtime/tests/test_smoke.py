# mat_runtime/tests/test_smoke.py
"""Tests for mat_runtime.smoke (preflight and MAT-2 selection helpers; no real CLIs)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mat_runtime.config import AgentDefinition, load_agent_definitions
from mat_runtime.smoke import (
    SMOKE_REAL_ENV,
    _mise_broken_version_output,
    _representative_agent_for_cli,
    check_cli_on_path,
    pick_smoke_op,
    run_smoke,
)


def test_mise_broken_detects() -> None:
    assert _mise_broken_version_output("mise ERROR: codex@latest not currently active")
    assert _mise_broken_version_output("No version is set for shim codex")
    assert not _mise_broken_version_output("1.0.0")


@patch("mat_runtime.smoke.shutil.which")
@patch("mat_runtime.smoke.subprocess.run")
def test_check_cli_on_path_not_found(mock_run, mock_which) -> None:
    mock_which.return_value = None
    ok, msg = check_cli_on_path("codex")
    assert not ok
    assert "PATH" in msg
    mock_run.assert_not_called()


@patch("mat_runtime.smoke.shutil.which")
@patch("mat_runtime.smoke.subprocess.run")
def test_check_cli_on_path_version_ok(mock_run, mock_which) -> None:
    mock_which.return_value = "/x/codex"
    mock_run.return_value = type("R", (), {"stdout": "codex 0.1\n", "stderr": "", "returncode": 0})()
    ok, msg = check_cli_on_path("codex")
    assert ok
    assert "codex" in msg


def test_pick_smoke_op_prefers_review() -> None:
    a = AgentDefinition(
        name="x",
        description="d",
        role="worker",
        allowed_mat_ops=["codex.implement", "codex.review", "codex.test"],
    )
    assert pick_smoke_op(a) == "codex.review"


def test_pick_smoke_op_no_ops_uses_default() -> None:
    a = AgentDefinition(
        name="o",
        description="d",
        role="orchestrator",
        cli="claude",
    )
    assert pick_smoke_op(a) == "smoke.ping"


def test_representative_prefers_coder_for_codex() -> None:
    root = Path(__file__).resolve().parents[2]
    agents = load_agent_definitions(repo_root=root)
    name = _representative_agent_for_cli(agents, "codex")
    assert name == "coder"


def test_representative_prefers_reviewer_for_codex_review() -> None:
    root = Path(__file__).resolve().parents[2]
    agents = load_agent_definitions(repo_root=root)
    name = _representative_agent_for_cli(agents, "codex-review")
    assert name == "reviewer"


def test_run_smoke_dry_succeeds_from_repo_root() -> None:
    root = Path(__file__).resolve().parents[2]
    assert run_smoke(root, real=False, per_cli=False, agent=None, instruction="x", timeout_ms=1, strict=False, as_json=True) == 0


def test_run_smoke_real_refuses_without_env() -> None:
    root = Path(__file__).resolve().parents[2]
    with patch.dict(os.environ, {SMOKE_REAL_ENV: ""}, clear=False):
        assert (
            run_smoke(
                root,
                real=True,
                per_cli=False,
                agent="reviewer",
                instruction="x",
                timeout_ms=1,
                strict=False,
                as_json=True,
            )
            == 1
        )


def test_run_smoke_real_refuses_on_mat_smoke_zero() -> None:
    root = Path(__file__).resolve().parents[2]
    with patch.dict(os.environ, {SMOKE_REAL_ENV: "0"}):
        assert (
            run_smoke(
                root,
                real=True,
                per_cli=True,
                agent=None,
                instruction="x",
                timeout_ms=1,
                strict=False,
                as_json=True,
            )
            == 1
        )
