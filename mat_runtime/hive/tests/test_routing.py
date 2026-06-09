"""Tests for inter-crew routing strategies and handoff evaluation."""

from __future__ import annotations

import pytest

from mat_runtime.crew.types import CrewResult
from mat_runtime.hive.definition import (
    CrewEntry,
    HiveDefinition,
    InterCrewRoutingConfig,
    RoutingRule,
)
from mat_runtime.hive.routing import (
    CapabilityStrategy,
    DependencyStrategy,
    ManualStrategy,
    SequentialStrategy,
    evaluate_handoff,
)
from mat_runtime.hive.types import HiveTask


def _pipeline_definition(strategy: str = "sequential") -> HiveDefinition:
    return HiveDefinition(
        name="dev-pipeline",
        crews=[
            CrewEntry(ref="dev-crew"),
            CrewEntry(ref="review-crew", depends_on=["dev-crew"], role="review"),
        ],
        inter_crew_routing=InterCrewRoutingConfig(
            strategy=strategy,
            default_handoff="on_success",
            rules=[
                RoutingRule(
                    from_crew="dev-crew",
                    to_crew="review-crew",
                    when="task_complete",
                    condition="success",
                )
            ],
        ),
    )


class TestExecutionOrder:
    def test_sequential_order(self):
        definition = _pipeline_definition("sequential")
        order = SequentialStrategy().get_execution_order(
            definition,
            HiveTask(instruction="test"),
        )
        assert order == ["dev-crew", "review-crew"]

    def test_dependency_order(self):
        definition = _pipeline_definition("dependency")
        order = DependencyStrategy().get_execution_order(
            definition,
            HiveTask(instruction="test"),
        )
        assert order == ["dev-crew", "review-crew"]

    def test_capability_order_matches_role_first(self):
        definition = _pipeline_definition("capability")
        order = CapabilityStrategy().get_execution_order(
            definition,
            HiveTask(instruction="test", role="review"),
        )
        assert order[0] == "review-crew"

    def test_manual_order_follows_rules(self):
        definition = _pipeline_definition("manual")
        order = ManualStrategy().get_execution_order(
            definition,
            HiveTask(instruction="test"),
        )
        assert order[:2] == ["dev-crew", "review-crew"]


class TestHandoffEvaluation:
    def test_rule_allows_success_handoff(self):
        routing = _pipeline_definition().inter_crew_routing
        result = CrewResult(
            ok=True,
            agent_used="coder",
            output="done",
            correlation_id="c1",
            duration_ms=1,
        )
        assert evaluate_handoff("dev-crew", "review-crew", result, routing)

    def test_rule_blocks_failed_handoff(self):
        routing = _pipeline_definition().inter_crew_routing
        result = CrewResult(
            ok=False,
            agent_used="coder",
            output=None,
            correlation_id="c1",
            duration_ms=1,
            error={"code": "failed"},
        )
        assert not evaluate_handoff("dev-crew", "review-crew", result, routing)

    def test_default_handoff_on_success(self):
        routing = InterCrewRoutingConfig(default_handoff="on_success")
        ok_result = CrewResult(
            ok=True,
            agent_used="coder",
            output="done",
            correlation_id="c1",
            duration_ms=1,
        )
        fail_result = CrewResult(
            ok=False,
            agent_used="coder",
            output=None,
            correlation_id="c1",
            duration_ms=1,
        )
        assert evaluate_handoff("a", "b", ok_result, routing)
        assert not evaluate_handoff("a", "b", fail_result, routing)

    def test_default_handoff_always(self):
        routing = InterCrewRoutingConfig(default_handoff="always")
        result = CrewResult(
            ok=False,
            agent_used="coder",
            output=None,
            correlation_id="c1",
            duration_ms=1,
        )
        assert evaluate_handoff("a", "b", result, routing)

    def test_failure_condition(self):
        routing = InterCrewRoutingConfig(
            rules=[
                RoutingRule(
                    from_crew="dev-crew",
                    to_crew="review-crew",
                    when="task_complete",
                    condition="failure",
                )
            ]
        )
        result = CrewResult(
            ok=False,
            agent_used="coder",
            output=None,
            correlation_id="c1",
            duration_ms=1,
        )
        assert evaluate_handoff("dev-crew", "review-crew", result, routing)
