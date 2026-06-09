"""Base CLI adapter for invoking AI tools."""

from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def model_from_kwargs(kwargs: Any) -> str | None:
    """Extract an optional model hint forwarded from swarm model_matrix."""
    model = kwargs.get("model")
    if isinstance(model, str) and model.strip():
        return model
    return None


@dataclass
class InvocationResult:
    """Result of a CLI invocation."""

    ok: bool
    stdout: str
    stderr: str
    return_code: int
    correlation_id: str
    timeout_exceeded: bool = False


@dataclass
class CLIAdapter:
    """
    Base adapter for invoking CLI tools.

    Subclasses override build_command() to construct tool-specific invocations.
    """

    command: str | None = None
    flags: list[str] = field(default_factory=list)
    working_dir: str | None = None
    timeout_ms: int = 300_000  # 5 minutes default

    def build_command(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """
        Build the CLI command to execute.

        Override in subclasses for tool-specific command construction.
        """
        if not self.command:
            raise ValueError("CLIAdapter requires explicit 'command' for custom CLI tools")
        cmd = [self.command, *self.flags]
        if prompt:
            cmd.extend(["--prompt", prompt])
        return cmd

    def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> InvocationResult:
        """
        Invoke the CLI tool with the given prompt.

        Args:
            prompt: The instruction/prompt to send to the CLI tool.
            system_prompt: Optional system prompt (agent definition body).
            working_dir: Working directory for the CLI process.
            timeout_ms: Timeout in milliseconds.
            correlation_id: Optional correlation ID for tracking.

        Returns:
            InvocationResult with stdout, stderr, and status.
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        cwd = working_dir or self.working_dir
        timeout_sec = (timeout_ms or self.timeout_ms) / 1000.0

        cmd = self.build_command(prompt, system_prompt=system_prompt, **kwargs)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
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

    def invoke_with_file(
        self,
        prompt: str,
        system_prompt: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> InvocationResult:
        """
        Invoke CLI tool using a temporary file for the prompt.

        Useful for long prompts that exceed shell argument limits.
        """
        correlation_id = correlation_id or str(uuid.uuid4())

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            if system_prompt:
                f.write(f"{system_prompt}\n\n---\n\n")
            f.write(prompt)
            f.flush()
            prompt_file = f.name

        try:
            return self.invoke(
                prompt=f"@{prompt_file}",
                working_dir=working_dir,
                timeout_ms=timeout_ms,
                correlation_id=correlation_id,
                **kwargs,
            )
        finally:
            Path(prompt_file).unlink(missing_ok=True)
