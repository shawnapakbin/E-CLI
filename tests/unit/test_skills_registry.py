"""Unit tests for skills registry."""

import pytest
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from e_cli.skills.base import BaseSkill, SkillMetadata, SkillResult
from e_cli.skills.registry import SkillRegistry, RegisteredSkill


@dataclass
class TestSkill(BaseSkill):
    """Test skill implementation."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="test-skill",
            version="1.0.0",
            description="Test skill",
            category="test",
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        return True, ""

    def execute(self, **kwargs: Any) -> SkillResult:
        return SkillResult(ok=True, output="test")

    def get_schema(self) -> dict[str, Any]:
        return {"type": "object"}


class TestSkillRegistry:
    """Test SkillRegistry class."""

    def test_registry_initialization(self, tmp_path):
        """Test registry initialization."""
        registry = SkillRegistry(tmp_path)
        assert registry.skills_dir == tmp_path
        assert len(registry.list_all()) == 0

    def test_register_skill(self, tmp_path):
        """Test registering a skill."""
        registry = SkillRegistry(tmp_path)
        skill = TestSkill()

        registered = registry.register(
            name="test-skill",
            skill_instance=skill,
            manifest_path=tmp_path / "test-skill",
            category="test",
        )

        assert registered.name == "test-skill"
        assert registered.skill_instance == skill
        assert registered.enabled is True
        assert registered.load_error is None

    def test_get_skill(self, tmp_path):
        """Test retrieving a skill."""
        registry = SkillRegistry(tmp_path)
        skill = TestSkill()

        registry.register(
            name="test-skill",
            skill_instance=skill,
            manifest_path=tmp_path / "test-skill",
            category="test",
        )

        retrieved = registry.get("test-skill")
        assert retrieved is not None
        assert retrieved.name == "test-skill"

    def test_get_nonexistent_skill(self, tmp_path):
        """Test retrieving non-existent skill."""
        registry = SkillRegistry(tmp_path)
        retrieved = registry.get("nonexistent")
        assert retrieved is None

    def test_list_all_skills(self, tmp_path):
        """Test listing all skills."""
        registry = SkillRegistry(tmp_path)
        skill1 = TestSkill()
        skill2 = TestSkill()

        registry.register("skill1", skill1, tmp_path / "skill1", "cat1")
        registry.register("skill2", skill2, tmp_path / "skill2", "cat2")

        all_skills = registry.list_all()
        assert len(all_skills) == 2
        assert any(s.name == "skill1" for s in all_skills)
        assert any(s.name == "skill2" for s in all_skills)

    def test_list_by_category(self, tmp_path):
        """Test listing skills by category."""
        registry = SkillRegistry(tmp_path)
        skill1 = TestSkill()
        skill2 = TestSkill()

        registry.register("skill1", skill1, tmp_path / "skill1", "development")
        registry.register("skill2", skill2, tmp_path / "skill2", "devops")

        dev_skills = registry.list_by_category("development")
        assert len(dev_skills) == 1
        assert dev_skills[0].name == "skill1"

    def test_enable_disable_skill(self, tmp_path):
        """Test enabling and disabling skills."""
        registry = SkillRegistry(tmp_path)
        skill = TestSkill()

        registry.register("test-skill", skill, tmp_path / "test", "test")

        # Disable skill
        result = registry.disable("test-skill")
        assert result is True
        registered = registry.get("test-skill")
        assert registered.enabled is False

        # Enable skill
        result = registry.enable("test-skill")
        assert result is True
        registered = registry.get("test-skill")
        assert registered.enabled is True

    def test_unregister_skill(self, tmp_path):
        """Test unregistering a skill."""
        registry = SkillRegistry(tmp_path)
        skill = TestSkill()

        registry.register("test-skill", skill, tmp_path / "test", "test")
        assert registry.get("test-skill") is not None

        result = registry.unregister("test-skill")
        assert result is True
        assert registry.get("test-skill") is None

    def test_search_skills(self, tmp_path):
        """Test searching skills."""
        registry = SkillRegistry(tmp_path)

        # Create skills with different metadata
        skill1 = TestSkill()
        skill2 = TestSkill()

        reg1 = registry.register("git-helper", skill1, tmp_path / "git", "development")
        reg1.metadata.tags = ["git", "vcs"]

        reg2 = registry.register("docker-helper", skill2, tmp_path / "docker", "devops")
        reg2.metadata.tags = ["docker", "containers"]

        # Search by name
        results = registry.search("git")
        assert len(results) >= 1
        assert any(s.name == "git-helper" for s in results)

        # Search by tag
        results = registry.search("docker", tags=["containers"])
        assert len(results) >= 1
        assert any(s.name == "docker-helper" for s in results)
