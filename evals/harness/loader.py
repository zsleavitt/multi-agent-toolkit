"""Load golden eval tasks from ``evals/tasks/``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def evals_root() -> Path:
    return Path(__file__).resolve().parent.parent


def tasks_dir() -> Path:
    return evals_root() / "tasks"


def baseline_path() -> Path:
    return evals_root() / "baseline.json"


@dataclass
class EvalTask:
    """A single golden eval task."""

    id: str
    description: str
    request: dict[str, Any]
    expected: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    must_pass: bool = False
    setup: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], source: Path | None = None) -> "EvalTask":
        task_id = data.get("id")
        if not task_id or not isinstance(task_id, str):
            raise ValueError(f"Task missing string 'id': {source}")
        if "request" not in data or not isinstance(data["request"], dict):
            raise ValueError(f"Task {task_id!r} missing object 'request'")
        if "expected" not in data or not isinstance(data["expected"], dict):
            raise ValueError(f"Task {task_id!r} missing object 'expected'")
        return cls(
            id=task_id,
            description=str(data.get("description") or ""),
            request=data["request"],
            expected=data["expected"],
            tags=list(data.get("tags") or []),
            must_pass=bool(data.get("must_pass", False)),
            setup=dict(data.get("setup") or {}),
            source_path=source,
        )


def load_task_file(path: Path) -> EvalTask:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Task file must be a JSON object: {path}")
    return EvalTask.from_dict(data, source=path)


def load_tasks(
    directory: Path | None = None,
    *,
    tags: list[str] | None = None,
    task_ids: list[str] | None = None,
) -> list[EvalTask]:
    """Load and optionally filter golden tasks (sorted by id)."""
    root = directory or tasks_dir()
    if not root.exists():
        return []

    tasks: list[EvalTask] = []
    for path in sorted(root.glob("*.json")):
        if path.name.startswith("_"):
            continue
        tasks.append(load_task_file(path))

    if tags:
        tag_set = set(tags)
        tasks = [t for t in tasks if tag_set.intersection(t.tags)]
    if task_ids:
        id_set = set(task_ids)
        tasks = [t for t in tasks if t.id in id_set]

    tasks.sort(key=lambda t: t.id)
    return tasks
