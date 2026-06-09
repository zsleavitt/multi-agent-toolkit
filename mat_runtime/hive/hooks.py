"""Hive lifecycle hooks (v1 stub — full observability deferred to MAT-52)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HookResult:
    """Result of running a hive lifecycle hook."""

    ok: bool
    hook_name: str
    skipped: bool = True


class HookRunner:
    """
    Placeholder hook runner for hive lifecycle events.

    Hive schema v1 has no hook fields. This stub preserves the API surface
    for MAT-52 observability integration.
    """

    async def run(self, hook_name: str, context: dict[str, Any]) -> HookResult:
        """No-op in v1 — hooks are deferred to MAT-52."""
        return HookResult(ok=True, hook_name=hook_name, skipped=True)
