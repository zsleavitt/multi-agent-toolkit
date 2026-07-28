"""Mock invocation adapters for eval runs — never call live CLIs."""

from __future__ import annotations

from typing import Any

from mat_runtime.adapters.base import InvocationResult


def _result_from_spec(
    spec: dict[str, Any],
    *,
    correlation_id: str,
) -> InvocationResult:
    kind = spec.get("kind")

    if kind == "timeout" or spec.get("timeout_exceeded"):
        return InvocationResult(
            ok=False,
            stdout=str(spec.get("stdout", "")),
            stderr=str(spec.get("stderr", "")),
            return_code=int(spec.get("return_code", -1)),
            correlation_id=correlation_id,
            timeout_exceeded=True,
        )

    if kind == "refuse":
        return InvocationResult(
            ok=False,
            stdout=str(spec.get("stdout", "I refuse this request.")),
            stderr=str(spec.get("stderr", "")),
            return_code=int(spec.get("return_code", 1)),
            correlation_id=correlation_id,
            timeout_exceeded=False,
        )

    if kind == "execution_error" or spec.get("ok") is False:
        return InvocationResult(
            ok=False,
            stdout=str(spec.get("stdout", "")),
            stderr=str(spec.get("stderr", "Connection refused")),
            return_code=int(spec.get("return_code", 1)),
            correlation_id=correlation_id,
            timeout_exceeded=False,
        )

    return InvocationResult(
        ok=True,
        stdout=str(spec.get("stdout", "ok")),
        stderr=str(spec.get("stderr", "")),
        return_code=int(spec.get("return_code", 0)),
        correlation_id=correlation_id,
        timeout_exceeded=False,
    )


def expand_mock_behavior(mock: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Normalize task ``setup.mock`` into a sequence of result specs."""
    if not mock:
        return [{"kind": "ok", "stdout": "ok"}]
    if "sequence" in mock:
        seq = mock["sequence"]
        if not isinstance(seq, list) or not seq:
            raise ValueError("mock.sequence must be a non-empty list")
        return [dict(item) for item in seq]
    return [dict(mock)]


class ScenarioMockAdapter:
    """Deterministic mock adapter driven by golden-task ``setup.mock``."""

    def __init__(self, behavior: dict[str, Any] | None = None):
        self._specs = expand_mock_behavior(behavior)
        self.calls = 0
        self.call_kwargs: list[dict[str, Any]] = []

    def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> InvocationResult:
        self.calls += 1
        self.call_kwargs.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "working_dir": working_dir,
                "timeout_ms": timeout_ms,
                "correlation_id": correlation_id,
                **kwargs,
            }
        )
        cid = correlation_id or "eval-correlation"
        idx = min(self.calls - 1, len(self._specs) - 1)
        return _result_from_spec(self._specs[idx], correlation_id=cid)
