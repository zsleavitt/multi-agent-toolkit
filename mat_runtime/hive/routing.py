"""Inter-crew routing strategies and handoff evaluation."""

from __future__ import annotations

from collections import deque
from typing import Protocol

from mat_runtime.hive.definition import (
    CrewEntry,
    HiveDefinition,
    InterCrewRoutingConfig,
    RoutingRule,
)
from mat_runtime.hive.types import HandoffContext, HiveTask
from mat_runtime.crew.types import CrewResult


class InterCrewRoutingStrategy(Protocol):
    """Protocol for inter-crew routing strategy implementations."""

    def get_execution_order(
        self,
        definition: HiveDefinition,
        task: HiveTask,
    ) -> list[str]:
        """Return ordered crew refs to attempt for this task."""
        ...


class SequentialStrategy:
    """Process crews in declaration order, respecting depends_on."""

    def get_execution_order(
        self,
        definition: HiveDefinition,
        task: HiveTask,
    ) -> list[str]:
        return [entry.ref for entry in definition.crews]


class DependencyStrategy:
    """Follow depends_on graph via topological sort."""

    def get_execution_order(
        self,
        definition: HiveDefinition,
        task: HiveTask,
    ) -> list[str]:
        deps: dict[str, list[str]] = {
            entry.ref: list(entry.depends_on) for entry in definition.crews
        }
        in_degree = {ref: len(dep_list) for ref, dep_list in deps.items()}
        dependents: dict[str, list[str]] = {ref: [] for ref in deps}
        for ref, dep_list in deps.items():
            for dep in dep_list:
                if dep in dependents:
                    dependents[dep].append(ref)

        queue = deque(ref for ref, degree in in_degree.items() if degree == 0)
        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for child in dependents[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(deps):
            raise ValueError("Circular depends_on detected during routing")

        return order


class CapabilityStrategy:
    """Route by matching task.role to crew role, then remaining crews in order."""

    def get_execution_order(
        self,
        definition: HiveDefinition,
        task: HiveTask,
    ) -> list[str]:
        if not task.role:
            return SequentialStrategy().get_execution_order(definition, task)

        matching = [entry.ref for entry in definition.crews if entry.role == task.role]
        remaining = [
            entry.ref for entry in definition.crews if entry.ref not in matching
        ]
        return matching + remaining


class ManualStrategy:
    """
    Use explicit routing rules to determine reachable crews.

    Note: Returns an empty list if routing.rules is empty. This should not
    occur in practice since schema validation requires at least one rule
    for manual strategy, but programmatic construction could bypass this.
    """

    def get_execution_order(
        self,
        definition: HiveDefinition,
        task: HiveTask,
    ) -> list[str]:
        routing = definition.inter_crew_routing
        if not routing.rules:
            return []

        all_refs = {entry.ref for entry in definition.crews}
        targets = {rule.to_crew for rule in routing.rules}
        roots = [
            rule.from_crew
            for rule in routing.rules
            if rule.from_crew not in targets and rule.from_crew in all_refs
        ]
        if not roots:
            roots = [routing.rules[0].from_crew]

        order: list[str] = []
        seen: set[str] = set()
        current = roots[0]
        while current and current not in seen:
            order.append(current)
            seen.add(current)
            next_crew = _next_rule_target(current, routing.rules)
            current = next_crew

        for entry in definition.crews:
            if entry.ref not in seen:
                order.append(entry.ref)

        return order


def _next_rule_target(from_crew: str, rules: list[RoutingRule]) -> str | None:
    for rule in rules:
        if rule.from_crew == from_crew:
            return rule.to_crew
    return None


def _check_condition(condition: str | None, ok: bool) -> bool:
    if condition is None or condition == "any":
        return True
    if condition == "success":
        return ok
    if condition == "failure":
        return not ok
    return True


def evaluate_handoff(
    from_crew: str,
    to_crew: str,
    result: CrewResult,
    routing: InterCrewRoutingConfig,
    when: str = "task_complete",
) -> bool:
    """
    Determine whether execution should hand off from one crew to another.

    Explicit rules take precedence over default_handoff.
    """
    matching = [
        rule
        for rule in routing.rules
        if rule.from_crew == from_crew
        and rule.to_crew == to_crew
        and rule.when == when
    ]
    if matching:
        return _check_condition(matching[0].condition, result.ok)

    if routing.default_handoff == "never":
        return False
    if routing.default_handoff == "always":
        return True
    return result.ok


def evaluate_handoff_context(context: HandoffContext, routing: InterCrewRoutingConfig) -> bool:
    """Evaluate handoff using a HandoffContext."""
    return evaluate_handoff(
        from_crew=context.from_crew,
        to_crew=context.to_crew,
        result=context.stage_result.crew_result,
        routing=routing,
        when=context.when,
    )


def dependencies_satisfied(
    entry: CrewEntry,
    completed_successfully: set[str],
) -> bool:
    """Return True when all depends_on crews completed successfully."""
    return all(dep in completed_successfully for dep in entry.depends_on)


def get_crew_entry(definition: HiveDefinition, crew_ref: str) -> CrewEntry:
    for entry in definition.crews:
        if entry.ref == crew_ref:
            return entry
    raise ValueError(f"Unknown crew ref '{crew_ref}' in hive '{definition.name}'")


def create_routing_strategy(strategy: str) -> InterCrewRoutingStrategy:
    """
    Factory function to create an inter-crew routing strategy.

    Raises:
        ValueError: If strategy is unknown.
    """
    if strategy == "sequential":
        return SequentialStrategy()
    if strategy == "dependency":
        return DependencyStrategy()
    if strategy == "capability":
        return CapabilityStrategy()
    if strategy == "manual":
        return ManualStrategy()
    raise ValueError(f"Unknown inter-crew routing strategy: {strategy}")
