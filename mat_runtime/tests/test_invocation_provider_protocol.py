"""MAT-53 — AgentInvocationProvider protocol compliance for CLI adapters."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from mat_runtime.adapters import (
    ClaudeAdapter,
    CodexAdapter,
    CodexReviewAdapter,
    GeminiAdapter,
    get_adapter,
)
from mat_runtime.providers import AgentInvocationProvider


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ClaudeAdapter(),
        lambda: CodexAdapter(),
        lambda: CodexReviewAdapter(),
        lambda: GeminiAdapter(),
        lambda: get_adapter("claude"),
        lambda: get_adapter("codex"),
        lambda: get_adapter("codex-review"),
        lambda: get_adapter("gemini"),
    ],
)
def test_cli_adapters_satisfy_invocation_protocol(
    factory: Callable[[], object],
) -> None:
    obj = factory()
    assert isinstance(obj, AgentInvocationProvider)
