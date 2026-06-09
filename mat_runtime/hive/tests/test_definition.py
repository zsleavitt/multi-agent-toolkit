"""Tests for hive definition loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mat_runtime.hive.definition import (
    GlobalConfig,
    HiveDefinition,
    InterCrewRoutingConfig,
    load_hive_definition,
)


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Provide a temporary directory for hive test fixtures."""
    return tmp_path


def _write_definition(
    tmp_dir: Path, data: dict, crews: dict[str, dict] | None = None
) -> Path:
    if crews:
        crews_dir = tmp_dir / "crews"
        crews_dir.mkdir(exist_ok=True)
        for name, crew_data in crews.items():
            (crews_dir / f"{name}.json").write_text(
                json.dumps(crew_data),
                encoding="utf-8",
            )
    hive_file = tmp_dir / f"{data['name']}.json"
    hive_file.write_text(json.dumps(data), encoding="utf-8")
    return hive_file


class TestLoadHiveDefinition:
    def test_load_dev_pipeline_shape(self, tmp_repo: Path):
        path = _write_definition(
            tmp_repo,
            {
                "schema_version": "1.0.0",
                "name": "dev-pipeline",
                "shared_goal": "Ship features",
                "crews": [
                    {"ref": "dev-crew"},
                    {
                        "ref": "review-crew",
                        "depends_on": ["dev-crew"],
                        "role": "review",
                    },
                ],
                "global_config": {
                    "max_concurrent_crews": 2,
                    "max_tasks": 50,
                    "quotas": {"max_agent_invocations": 200},
                },
                "inter_crew_routing": {
                    "strategy": "sequential",
                    "default_handoff": "on_success",
                    "rules": [
                        {
                            "from": "dev-crew",
                            "to": "review-crew",
                            "when": "task_complete",
                            "condition": "success",
                        }
                    ],
                },
            },
            crews={
                "dev-crew": {
                    "name": "dev-crew",
                    "agents": ["coder"],
                },
                "review-crew": {
                    "name": "review-crew",
                    "agents": ["reviewer"],
                },
            },
        )

        definition = load_hive_definition(path, repo_root=path.parent)

        assert definition.name == "dev-pipeline"
        assert definition.shared_goal == "Ship features"
        assert len(definition.crews) == 2
        assert definition.crews[1].depends_on == ["dev-crew"]
        assert definition.global_config.max_tasks == 50
        assert definition.global_config.quotas.max_agent_invocations == 200
        assert definition.inter_crew_routing.strategy == "sequential"
        assert len(definition.inter_crew_routing.rules) == 1

    def test_reject_unknown_crew_ref(self, tmp_repo: Path):
        path = _write_definition(
            tmp_repo,
            {
                "name": "bad-hive",
                "crews": [{"ref": "missing-crew"}],
            },
            crews={
                "dev-crew": {"name": "dev-crew", "agents": ["coder"]},
            },
        )

        with pytest.raises(ValueError, match="Unknown crew ref 'missing-crew'"):
            load_hive_definition(path, repo_root=path.parent)

    def test_reject_circular_depends_on(self, tmp_repo: Path):
        path = _write_definition(
            tmp_repo,
            {
                "name": "cycle-hive",
                "crews": [
                    {"ref": "a-crew", "depends_on": ["b-crew"]},
                    {"ref": "b-crew", "depends_on": ["a-crew"]},
                ],
            },
            crews={
                "a-crew": {"name": "a-crew", "agents": ["coder"]},
                "b-crew": {"name": "b-crew", "agents": ["reviewer"]},
            },
        )

        with pytest.raises(ValueError, match="Circular depends_on"):
            load_hive_definition(path, repo_root=path.parent)

    def test_reject_manual_without_rules(self, tmp_repo: Path):
        path = _write_definition(
            tmp_repo,
            {
                "name": "manual-hive",
                "crews": [{"ref": "dev-crew"}],
                "inter_crew_routing": {"strategy": "manual"},
            },
            crews={"dev-crew": {"name": "dev-crew", "agents": ["coder"]}},
        )

        with pytest.raises(ValueError, match="manual.*requires at least one rule"):
            load_hive_definition(path, repo_root=path.parent)
