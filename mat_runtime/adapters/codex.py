"""OpenAI Codex CLI adapter."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mat_runtime.adapters.base import CLIAdapter, InvocationResult, model_from_kwargs


@dataclass
class CodexAdapter(CLIAdapter):
    """
    Adapter for OpenAI Codex CLI.

    Invokes `codex exec` for non-interactive code implementation, testing, and refactoring.
    """

    command: str = "codex"
    flags: list[str] = field(default_factory=lambda: ["--full-auto"])

    def build_command(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build codex CLI command."""
        # Use 'codex exec' for non-interactive execution
        cmd = [self.command, "exec", *self.flags]

        model = model_from_kwargs(kwargs)
        if model:
            cmd.extend(["--model", model])

        # Combine system prompt with the task prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\nTask: {prompt}"

        # Add the prompt as the main argument
        cmd.append(full_prompt)

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
        Invoke Codex CLI.

        Uses `codex exec` with --full-auto for sandboxed automatic execution.
        """
        # For very long prompts, write to a temp file and read from stdin
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\nTask: {prompt}"

        return super().invoke(
            prompt=full_prompt,
            system_prompt=None,  # Already combined into prompt
            working_dir=working_dir,
            timeout_ms=timeout_ms,
            correlation_id=correlation_id,
            **kwargs,
        )
