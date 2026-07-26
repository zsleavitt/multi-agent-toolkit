"""MAT-4 orchestrator state helpers (budgets + transitions, MAT-98)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANONICAL_STATE_NAMES = ("orchestrator.state.json", "ai-team.state.json")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_state_path(repo_root: Path | str) -> Path | None:
    """Locate a canonical orchestrator state file under ``repo_root`` if present."""
    root = Path(repo_root)
    candidates = [
        root / name for name in CANONICAL_STATE_NAMES
    ] + [
        root / ".mat" / name for name in CANONICAL_STATE_NAMES
    ] + [
        root / ".ai-team" / name for name in CANONICAL_STATE_NAMES
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_state(path: Path | str) -> dict[str, Any]:
    """Load orchestrator state JSON from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_state(path: Path | str, state: dict[str, Any]) -> None:
    """Persist orchestrator state JSON (pretty-printed)."""
    Path(path).write_text(
        json.dumps(state, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def budgets_from_state(
    state: dict[str, Any],
    *,
    queue_item_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Extract session/task budget fields for :class:`~mat_runtime.resilience.BudgetLimits`."""
    session = state.get("orchestrator_session") or {}
    item: dict[str, Any] = {}
    queue_items = ((state.get("queue") or {}).get("items")) or []
    if queue_item_id:
        for candidate in queue_items:
            if isinstance(candidate, dict) and candidate.get("id") == queue_item_id:
                item = candidate
                break
    elif correlation_id:
        for candidate in queue_items:
            if (
                isinstance(candidate, dict)
                and candidate.get("correlation_id") == correlation_id
            ):
                item = candidate
                break

    return {
        "session_token_budget": session.get("token_budget"),
        "session_cost_budget": session.get("cost_budget"),
        "session_tokens_used": int(session.get("tokens_used") or 0),
        "session_cost_used": float(session.get("cost_used") or 0),
        "task_token_budget": item.get("token_budget"),
        "task_cost_budget": item.get("cost_budget"),
        "task_tokens_used": int(item.get("tokens_used") or 0),
        "task_cost_used": float(item.get("cost_used") or 0),
        "queue_item_id": item.get("id"),
    }


def record_budget_exceeded_transition(
    state: dict[str, Any],
    *,
    reason: str,
    scope: str,
    queue_item_id: str | None = None,
    at: str | None = None,
) -> dict[str, Any]:
    """Mutate ``state``: set queue status to ``budget_exceeded`` and append a transition.

    Returns the mutated state (same object).
    """
    now = at or _utc_now_iso()
    previous: str | None = None
    items = ((state.get("queue") or {}).get("items")) or []
    if queue_item_id:
        for item in items:
            if isinstance(item, dict) and item.get("id") == queue_item_id:
                previous = item.get("status")
                item["status"] = "budget_exceeded"
                item["updated_at"] = now
                break

    meta = state.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        state["meta"] = meta
    transitions = meta.setdefault("transitions", [])
    if not isinstance(transitions, list):
        transitions = []
        meta["transitions"] = transitions

    entry: dict[str, Any] = {
        "at": now,
        "to": "budget_exceeded",
        "reason": reason,
        "scope": scope,
    }
    if previous is not None:
        entry["from"] = previous
    if queue_item_id:
        entry["queue_item_id"] = queue_item_id
    transitions.append(entry)
    meta["updated_at"] = now

    # Prefer 1.2.0 when writing budget fields / transitions.
    if state.get("schema_version") in ("1.0.0", "1.1.0", None):
        state["schema_version"] = "1.2.0"

    return state


def sync_usage_counters(
    state: dict[str, Any],
    *,
    session_tokens_used: int | None = None,
    session_cost_used: float | None = None,
    queue_item_id: str | None = None,
    task_tokens_used: int | None = None,
    task_cost_used: float | None = None,
) -> dict[str, Any]:
    """Write usage counters back into orchestrator state (best-effort)."""
    now = _utc_now_iso()
    session = state.get("orchestrator_session")
    if isinstance(session, dict):
        if session_tokens_used is not None:
            session["tokens_used"] = session_tokens_used
        if session_cost_used is not None:
            session["cost_used"] = session_cost_used
        session["updated_at"] = now

    if queue_item_id:
        for item in ((state.get("queue") or {}).get("items")) or []:
            if isinstance(item, dict) and item.get("id") == queue_item_id:
                if task_tokens_used is not None:
                    item["tokens_used"] = task_tokens_used
                if task_cost_used is not None:
                    item["cost_used"] = task_cost_used
                item["updated_at"] = now
                break

    meta = state.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["updated_at"] = now
    return state


__all__ = [
    "CANONICAL_STATE_NAMES",
    "find_state_path",
    "load_state",
    "save_state",
    "budgets_from_state",
    "record_budget_exceeded_transition",
    "sync_usage_counters",
]
