"""Tests for CrewRegistry."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mat_runtime.config import AgentDefinition
from mat_runtime.crew.definition import AgentRef, load_crew_definition
from mat_runtime.crew.registry import CrewRegistry, definition_to_dict


@pytest.fixture
def mock_router() -> MagicMock:
    router = MagicMock()
    router.agents = {
        "coder": AgentDefinition(
            name="coder",
            description="Coder agent",
            role="worker",
            specialization={"languages": ["python"]},
        ),
        "reviewer": AgentDefinition(
            name="reviewer",
            description="Reviewer agent",
            role="worker",
            specialization={"domain": "quality"},
        ),
        "tester": AgentDefinition(
            name="tester",
            description="Tester agent",
            role="worker",
            specialization={"domain": "testing"},
        ),
        "security": AgentDefinition(
            name="security",
            description="Security agent",
            role="worker",
            specialization={"domain": "security"},
        ),
    }
    router.find_agent.side_effect = lambda name: router.agents.get(name)
    return router


@pytest.fixture
def crews_dir(tmp_path: Path) -> Path:
    crews = tmp_path / "crews"
    crews.mkdir()

    (crews / "alpha-crew.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "name": "alpha-crew",
                "agents": ["coder", "reviewer"],
                "routing": {"strategy": "round-robin"},
            }
        )
    )
    (crews / "beta-crew.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "name": "beta-crew",
                "agents": [
                    "coder",
                    {
                        "name": "tester",
                        "priority": 10,
                    },
                ],
            }
        )
    )
    return crews


@pytest.fixture
def registry(tmp_path: Path, crews_dir: Path, mock_router: MagicMock) -> CrewRegistry:
    return CrewRegistry(
        repo_root=tmp_path,
        crews_dir=crews_dir,
        router=mock_router,
    )


class TestCrewRegistryDiscovery:
    def test_list_crews(self, registry: CrewRegistry) -> None:
        assert registry.list_crews() == ["alpha-crew", "beta-crew"]

    def test_list_members(self, registry: CrewRegistry) -> None:
        assert registry.list_members("alpha-crew") == ["coder", "reviewer"]
        assert registry.list_members("beta-crew") == ["coder", "tester"]

    def test_get_definition(self, registry: CrewRegistry) -> None:
        definition = registry.get_definition("alpha-crew")
        assert definition.name == "alpha-crew"
        assert [agent.name for agent in definition.agents] == ["coder", "reviewer"]

    def test_get_crew(self, registry: CrewRegistry) -> None:
        crew = registry.get_crew("alpha-crew")
        assert crew.name == "alpha-crew"
        assert registry.get_crew("alpha-crew") is crew

    def test_filename_must_match_name(
        self,
        tmp_path: Path,
        crews_dir: Path,
        mock_router: MagicMock,
    ) -> None:
        bad_file = crews_dir / "wrong-name.json"
        bad_file.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "name": "alpha-crew",
                    "agents": ["coder"],
                }
            )
        )

        with pytest.raises(ValueError, match="does not match name"):
            CrewRegistry(
                repo_root=tmp_path,
                crews_dir=crews_dir,
                router=mock_router,
            )


class TestCrewRegistryMembership:
    def test_add_agent_by_name(self, registry: CrewRegistry) -> None:
        registry.add_agent("alpha-crew", "tester")
        assert registry.list_members("alpha-crew") == ["coder", "reviewer", "tester"]

    def test_add_agent_by_ref(self, registry: CrewRegistry) -> None:
        registry.add_agent(
            "alpha-crew",
            AgentRef(name="security", timeout_ms=120000, priority=5),
        )
        members = registry.get_definition("alpha-crew").agents
        assert members[-1].name == "security"
        assert members[-1].timeout_ms == 120000

    def test_remove_agent(self, registry: CrewRegistry) -> None:
        registry.remove_agent("alpha-crew", "reviewer")
        assert registry.list_members("alpha-crew") == ["coder"]

    def test_reject_duplicate_agent(self, registry: CrewRegistry) -> None:
        with pytest.raises(ValueError, match="already a member"):
            registry.add_agent("alpha-crew", "coder")

    def test_reject_unknown_agent(self, registry: CrewRegistry) -> None:
        with pytest.raises(ValueError, match="Unknown agent"):
            registry.add_agent("alpha-crew", "missing-agent")

    def test_reject_unknown_crew(self, registry: CrewRegistry) -> None:
        with pytest.raises(ValueError, match="Unknown crew"):
            registry.list_members("missing-crew")

    def test_reject_remove_last_agent(self, registry: CrewRegistry) -> None:
        registry.remove_agent("alpha-crew", "reviewer")
        with pytest.raises(ValueError, match="Cannot remove last agent"):
            registry.remove_agent("alpha-crew", "coder")

    def test_reject_remove_unknown_member(self, registry: CrewRegistry) -> None:
        with pytest.raises(ValueError, match="is not a member"):
            registry.remove_agent("alpha-crew", "tester")

    def test_membership_invalidates_cached_crew(
        self,
        registry: CrewRegistry,
    ) -> None:
        first = registry.get_crew("alpha-crew")
        registry.add_agent("alpha-crew", "tester")
        second = registry.get_crew("alpha-crew")
        assert first is not second
        assert len(second.definition.agents) == 3


class TestCrewRegistrySave:
    def test_save_round_trip(
        self,
        registry: CrewRegistry,
        crews_dir: Path,
        mock_router: MagicMock,
        tmp_path: Path,
    ) -> None:
        registry.add_agent("alpha-crew", "security")
        registry.save("alpha-crew")

        saved = json.loads((crews_dir / "alpha-crew.json").read_text())
        assert saved["agents"][-1] == "security"

        reloaded = CrewRegistry(
            repo_root=tmp_path,
            crews_dir=crews_dir,
            router=mock_router,
        )
        assert reloaded.list_members("alpha-crew") == [
            "coder",
            "reviewer",
            "security",
        ]

    def test_definition_to_dict_preserves_overrides(self) -> None:
        definition = load_crew_definition(
            Path(__file__).resolve().parents[3]
            / "schemas"
            / "crew"
            / "v1"
            / "examples"
            / "valid"
            / "dev-crew.json"
        )
        data = definition_to_dict(definition)
        assert data["name"] == "dev-crew"
        assert isinstance(data["agents"][2], dict)
        assert data["agents"][2]["name"] == "reviewer"
