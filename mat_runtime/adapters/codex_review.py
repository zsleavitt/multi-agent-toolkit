"""OpenAI Codex CLI — `codex review` (non-interactive review path)."""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Any

from mat_runtime.adapters.base import CLIAdapter, InvocationResult


@dataclass
class CodexReviewAdapter(CLIAdapter):
    """
    Adapter for `codex review` — distinct from `codex exec` used for implement/test.

    Invoked via `npx --yes --package=@openai/codex -- codex review -` (stdin prompt) so Node/npx does not
    receive a long argv containing `https://` (e.g. GitHub PR URLs), which npm misparses
    as a package spec, and the global `codex` shim is optional.
    """

    command: str = "npx"
    # Use `--package=... -- codex` so the trailing `-` (stdin) is not parsed as an npm package name.
    flags: list[str] = field(
        default_factory=lambda: [
            "--yes",
            "--package=@openai/codex",
            "--",
            "codex",
            "review",
        ]
    )

    def build_command(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Argv for `codex review`; the instruction is read from process stdin, not this argv."""
        return [self.command, *self.flags, "-"]

    def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> InvocationResult:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\nTask: {prompt}"
        cmd = [self.command, *self.flags, "-"]
        correlation_id = correlation_id or str(uuid.uuid4())
        cwd = working_dir or self.working_dir
        timeout_sec = (timeout_ms or self.timeout_ms) / 1000.0

        try:
            result = subprocess.run(
                cmd,
                input=full_prompt,
                text=True,
                capture_output=True,
                cwd=cwd,
                timeout=timeout_sec,
            )
            return InvocationResult(
                ok=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                correlation_id=correlation_id,
                timeout_exceeded=False,
            )
        except subprocess.TimeoutExpired as e:
            return InvocationResult(
                ok=False,
                stdout=e.stdout or "" if hasattr(e, "stdout") else "",
                stderr=e.stderr or "" if hasattr(e, "stderr") else "",
                return_code=-1,
                correlation_id=correlation_id,
                timeout_exceeded=True,
            )
        except FileNotFoundError:
            return InvocationResult(
                ok=False,
                stdout="",
                stderr=f"CLI tool not found: {cmd[0]}",
                return_code=-1,
                correlation_id=correlation_id,
            )
