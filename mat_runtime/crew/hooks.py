"""Hook runner for crew lifecycle events."""

from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mat_runtime.crew.definition import HooksConfig


@dataclass
class HookResult:
    """Result of running a hook."""

    ok: bool
    hook_name: str
    skipped: bool = False
    timeout_exceeded: bool = False
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    duration_ms: int = 0


class HookRunner:
    """
    Runs lifecycle hooks with per-hook timeouts.

    Hook failures are non-fatal - they emit results but don't
    abort the crew operation.
    """

    def __init__(self, config: HooksConfig, repo_root: Path | str):
        self._config = config
        self._repo_root = Path(repo_root)

    def _get_hook_path(self, hook_name: str) -> str | None:
        """Get the configured path for a hook."""
        return getattr(self._config, hook_name, None)

    def _get_hook_timeout(self, hook_name: str) -> int:
        """Get the configured timeout for a hook in ms."""
        timeout_attr = f"{hook_name}_timeout_ms"
        return getattr(self._config, timeout_attr, 30000)

    async def run(self, hook_name: str, context: dict[str, Any]) -> HookResult:
        """
        Run a lifecycle hook.

        Args:
            hook_name: Name of the hook (e.g., 'on_start', 'on_task_complete').
            context: Context dict to pass as environment variables.

        Returns:
            HookResult indicating success/failure. Failures are non-fatal.
        """
        import time

        start_time = time.monotonic()

        # Check if hook is configured
        hook_path = self._get_hook_path(hook_name)
        if not hook_path:
            return HookResult(
                ok=True,
                hook_name=hook_name,
                skipped=True,
            )

        # Resolve full path
        full_path = self._repo_root / hook_path

        # Check if script exists
        if not full_path.exists():
            return HookResult(
                ok=False,
                hook_name=hook_name,
                error=f"Hook script not found: {full_path}",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Build environment with MAT_ prefix for context
        env = os.environ.copy()
        for key, value in context.items():
            env_key = f"MAT_{key.upper()}"
            env[env_key] = str(value)

        # Get timeout
        timeout_ms = self._get_hook_timeout(hook_name)
        timeout_sec = timeout_ms / 1000

        try:
            proc = await asyncio.create_subprocess_exec(
                str(full_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._repo_root),
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_sec,
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")

                duration_ms = int((time.monotonic() - start_time) * 1000)

                return HookResult(
                    ok=proc.returncode == 0,
                    hook_name=hook_name,
                    return_code=proc.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=duration_ms,
                )

            except asyncio.TimeoutError:
                # Kill the process
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass  # Already terminated

                duration_ms = int((time.monotonic() - start_time) * 1000)

                return HookResult(
                    ok=False,
                    hook_name=hook_name,
                    timeout_exceeded=True,
                    error=f"Hook timed out after {timeout_ms}ms",
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return HookResult(
                ok=False,
                hook_name=hook_name,
                error=str(e),
                duration_ms=duration_ms,
            )
