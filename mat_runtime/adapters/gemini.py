"""Google Gemini CLI adapter."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mat_runtime.adapters.base import CLIAdapter, InvocationResult


@dataclass
class GeminiAdapter(CLIAdapter):
    """
    Adapter for Google Gemini CLI.

    Invokes `gemini` CLI for research, git operations, and general tasks.
    """

    command: str = "gemini"
    flags: list[str] = field(default_factory=list)

    def build_command(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build gemini CLI command."""
        cmd = [self.command, *self.flags]

        # Gemini CLI uses -s for system instructions
        if system_prompt:
            cmd.extend(["-s", system_prompt])

        # Add prompt
        cmd.append(prompt)

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
        Invoke Gemini CLI.

        For long system prompts, writes to a temp file.
        """
        system_prompt_file = None
        actual_system_prompt = system_prompt

        if system_prompt and len(system_prompt) > 4000:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False
            ) as f:
                f.write(system_prompt)
                f.flush()
                system_prompt_file = f.name
                actual_system_prompt = f"@{system_prompt_file}"

        try:
            return super().invoke(
                prompt=prompt,
                system_prompt=actual_system_prompt,
                working_dir=working_dir,
                timeout_ms=timeout_ms,
                correlation_id=correlation_id,
                **kwargs,
            )
        finally:
            if system_prompt_file:
                Path(system_prompt_file).unlink(missing_ok=True)
