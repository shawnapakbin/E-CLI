"""Skill manager for coordinating skill operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from e_cli.config import get_app_dir
from e_cli.skills.base import Skill, SkillResult
from e_cli.skills.loader import SkillLoader
from e_cli.skills.registry import RegisteredSkill, SkillRegistry


class SkillManager:
    """High-level interface for skill management."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        """Initialize the skill manager.

        Args:
            skills_dir: Optional custom skills directory
        """
        if skills_dir is None:
            skills_dir = get_app_dir() / "skills"

        self.registry = SkillRegistry(skills_dir)
        self.loader = SkillLoader(self.registry)

    def initialize(self) -> int:
        """Initialize the skill system by loading all skills.

        Returns:
            Number of skills loaded
        """
        return self.loader.load_all_skills()

    def execute_skill(self, skill_name: str, **kwargs: Any) -> SkillResult:
        """Execute a skill by name.

        Args:
            skill_name: Name of skill to execute
            **kwargs: Parameters to pass to skill

        Returns:
            SkillResult from execution
        """
        registered = self.registry.get(skill_name)

        if not registered:
            return SkillResult(
                ok=False,
                output="",
                error=f"Skill '{skill_name}' not found"
            )

        if not registered.enabled:
            return SkillResult(
                ok=False,
                output="",
                error=f"Skill '{skill_name}' is disabled"
            )

        if registered.load_error:
            return SkillResult(
                ok=False,
                output="",
                error=f"Skill '{skill_name}' failed to load: {registered.load_error}"
            )

        if not registered.skill_instance:
            return SkillResult(
                ok=False,
                output="",
                error=f"Skill '{skill_name}' has no executable instance"
            )

        # Validate input
        is_valid, error_msg = registered.skill_instance.validate_input(**kwargs)
        if not is_valid:
            return SkillResult(
                ok=False,
                output="",
                error=f"Invalid input: {error_msg}"
            )

        # Execute skill
        try:
            return registered.skill_instance.execute(**kwargs)
        except Exception as e:
            return SkillResult(
                ok=False,
                output="",
                error=f"Execution error: {e}"
            )

    def list_skills(
        self,
        category: str | None = None,
        enabled_only: bool = False,
    ) -> list[RegisteredSkill]:
        """List available skills.

        Args:
            category: Optional category filter
            enabled_only: Only return enabled skills

        Returns:
            List of registered skills
        """
        if category:
            skills = self.registry.list_by_category(category)
        else:
            skills = self.registry.list_all()

        if enabled_only:
            skills = [s for s in skills if s.enabled]

        return skills

    def get_skill_info(self, skill_name: str) -> RegisteredSkill | None:
        """Get information about a skill.

        Args:
            skill_name: Name of skill

        Returns:
            RegisteredSkill or None
        """
        return self.registry.get(skill_name)

    def enable_skill(self, skill_name: str) -> bool:
        """Enable a skill.

        Args:
            skill_name: Name of skill to enable

        Returns:
            True if successful
        """
        return self.registry.enable(skill_name)

    def disable_skill(self, skill_name: str) -> bool:
        """Disable a skill.

        Args:
            skill_name: Name of skill to disable

        Returns:
            True if successful
        """
        return self.registry.disable(skill_name)

    def reload_skill(self, skill_name: str) -> bool:
        """Reload a skill from disk.

        Args:
            skill_name: Name of skill to reload

        Returns:
            True if successful
        """
        return self.loader.reload_skill(skill_name)

    def install_skill(self, source_path: Path, category: str = "custom") -> bool:
        """Install a skill from a directory.

        Args:
            source_path: Path to skill directory
            category: Category to install into

        Returns:
            True if successful
        """
        return self.loader.install_skill_from_directory(source_path, category)

    def search_skills(
        self,
        query: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> list[RegisteredSkill]:
        """Search for skills.

        Args:
            query: Search term
            category: Category filter
            tags: Tag filters

        Returns:
            List of matching skills
        """
        return self.registry.search(query=query, category=category, tags=tags)

    def get_stats(self) -> dict[str, Any]:
        """Get skill system statistics.

        Returns:
            Statistics dictionary
        """
        return self.registry.get_stats()


# Global skill manager instance
_skill_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    """Get the global skill manager instance.

    Returns:
        SkillManager instance
    """
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
        _skill_manager.initialize()
    return _skill_manager
