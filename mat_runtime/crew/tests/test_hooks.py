"""Tests for HookRunner."""

from __future__ import annotations

import asyncio
import stat
from pathlib import Path

import pytest

from mat_runtime.crew.hooks import HookRunner
from mat_runtime.crew.definition import HooksConfig


@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
    """Create a temp directory with executable hook scripts."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    return scripts


def create_script(path: Path, content: str, exit_code: int = 0) -> None:
    """Create an executable script."""
    script = f"""#!/bin/bash
{content}
exit {exit_code}
"""
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class TestHookRunner:
    """Tests for HookRunner."""

    def test_run_existing_hook(self, hooks_dir: Path) -> None:
        """Run a hook that exists and succeeds."""
        script = hooks_dir / "on_start.sh"
        create_script(script, "echo 'started'")

        config = HooksConfig(
            on_start="scripts/on_start.sh",
            on_start_timeout_ms=5000,
        )
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = asyncio.run(runner.run("on_start", {"crew": "test-crew"}))

        assert result.ok
        assert result.hook_name == "on_start"

    def test_run_nonexistent_hook_no_error(self, hooks_dir: Path) -> None:
        """Running a hook that's not configured is a no-op."""
        config = HooksConfig()  # No hooks configured
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = asyncio.run(runner.run("on_start", {}))

        assert result.ok
        assert result.skipped

    def test_run_missing_script_non_fatal(self, hooks_dir: Path) -> None:
        """Missing script file is non-fatal, returns error result."""
        config = HooksConfig(on_start="scripts/missing.sh")
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = asyncio.run(runner.run("on_start", {}))

        assert not result.ok
        assert "not found" in result.error.lower()

    def test_timeout_kills_process(self, hooks_dir: Path) -> None:
        """Hook that exceeds timeout is killed."""
        script = hooks_dir / "slow.sh"
        create_script(script, "sleep 10")

        config = HooksConfig(
            on_start="scripts/slow.sh",
            on_start_timeout_ms=100,  # 100ms timeout
        )
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = asyncio.run(runner.run("on_start", {}))

        assert not result.ok
        assert result.timeout_exceeded

    def test_hook_failure_non_fatal(self, hooks_dir: Path) -> None:
        """Hook that exits non-zero is non-fatal."""
        script = hooks_dir / "failing.sh"
        create_script(script, "echo 'oops'", exit_code=1)

        config = HooksConfig(on_start="scripts/failing.sh")
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = asyncio.run(runner.run("on_start", {}))

        assert not result.ok
        assert result.return_code == 1

    def test_context_passed_as_env(self, hooks_dir: Path) -> None:
        """Context dict is passed as environment variables."""
        script = hooks_dir / "env_check.sh"
        create_script(script, 'echo "CREW=$MAT_CREW"')

        config = HooksConfig(on_start="scripts/env_check.sh")
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = asyncio.run(runner.run("on_start", {"crew": "my-crew"}))

        assert result.ok
        assert "CREW=my-crew" in result.stdout
