"""Semantic validation for Hive definitions (shared with scripts/validate_hive.py)."""

from __future__ import annotations

from collections import deque
from pathlib import Path


def extract_crew_refs(instance: dict) -> list[str]:
    """Extract crew ref strings from a hive definition."""
    refs: list[str] = []
    for crew in instance.get("crews", []):
        if isinstance(crew, dict):
            ref = crew.get("ref")
            if isinstance(ref, str):
                refs.append(ref)
    return refs


def check_duplicate_crew_refs(refs: list[str], path: Path | str) -> None:
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            raise ValueError(
                f"Duplicate crew ref '{ref}' in {path}. "
                f"Each crew can only appear once in a hive."
            )
        seen.add(ref)


def check_crew_refs_exist(
    refs: list[str],
    known_crews: set[str],
    path: Path | str,
) -> None:
    if not known_crews:
        return
    for ref in refs:
        if ref not in known_crews:
            raise ValueError(
                f"Unknown crew ref '{ref}' in {path}. "
                f"Valid crews: {sorted(known_crews)}"
            )


def check_depends_on(
    crews: list[dict],
    hive_refs: set[str],
    path: Path | str,
) -> None:
    for crew in crews:
        if not isinstance(crew, dict):
            continue
        ref = crew.get("ref")
        for dep in crew.get("depends_on") or []:
            if dep not in hive_refs:
                raise ValueError(
                    f"depends_on entry '{dep}' for crew '{ref}' is not a crew ref "
                    f"in this hive ({path}). Valid refs: {sorted(hive_refs)}"
                )
            if dep == ref:
                raise ValueError(
                    f"Crew '{ref}' cannot depend on itself ({path})."
                )


def check_no_cycles(crews: list[dict], path: Path | str) -> None:
    """Detect circular depends_on using Kahn's algorithm."""
    deps: dict[str, list[str]] = {}
    for crew in crews:
        if not isinstance(crew, dict):
            continue
        ref = crew.get("ref")
        if not isinstance(ref, str):
            continue
        deps[ref] = list(crew.get("depends_on") or [])

    in_degree = {ref: len(dep_list) for ref, dep_list in deps.items()}
    dependents: dict[str, list[str]] = {ref: [] for ref in deps}
    for ref, dep_list in deps.items():
        for dep in dep_list:
            if dep in dependents:
                dependents[dep].append(ref)

    queue = deque(ref for ref, degree in in_degree.items() if degree == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for child in dependents[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if visited != len(deps):
        raise ValueError(
            f"Circular depends_on detected in {path}. "
            f"Crew dependency graph must be acyclic."
        )


def check_routing_rules(
    instance: dict,
    hive_refs: set[str],
    path: Path | str,
) -> None:
    routing = instance.get("inter_crew_routing")
    if not isinstance(routing, dict):
        return
    for rule in routing.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        for endpoint in ("from", "to"):
            ref = rule.get(endpoint)
            if isinstance(ref, str) and ref not in hive_refs:
                raise ValueError(
                    f"inter_crew_routing.rules {endpoint} '{ref}' is not a crew ref "
                    f"in this hive ({path}). Valid refs: {sorted(hive_refs)}"
                )


def semantic_validation(
    instance: dict,
    path: Path | str,
    known_crews: set[str],
) -> None:
    """Run all semantic checks on a hive definition dict."""
    crews = instance.get("crews") or []
    refs = extract_crew_refs(instance)
    hive_refs = set(refs)

    check_duplicate_crew_refs(refs, path)
    check_crew_refs_exist(refs, known_crews, path)
    check_depends_on(crews, hive_refs, path)
    check_no_cycles(crews, path)
    check_routing_rules(instance, hive_refs, path)
