"""Google Gemini CLI adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mat_runtime.adapters.base import CLIAdapter, InvocationResult


@dataclass
class GeminiAdapter(CLIAdapter):
    """
    Adapter for Google Gemini CLI.

    Invokes `gemini` CLI in non-interactive mode for research, git operations, and general tasks.
    """

    command: str = "gemini"
    flags: list[str] = field(default_factory=lambda: ["--yolo"])  # Auto-approve actions

    def build_command(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build gemini CLI command."""
        cmd = [self.command, *self.flags]

        # Combine system prompt with task prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\nTask: {prompt}"

        # Use -p/--prompt for non-interactive (headless) mode
        cmd.extend(["--prompt", full_prompt])

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
        Invoke Gemini CLI in non-interactive mode.

        Uses --prompt for headless execution and --yolo for auto-approval.
        """
        # Combine prompts
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
