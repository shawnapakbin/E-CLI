"""Skill registry for discovering and managing skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from e_cli.skills.base import Skill, SkillMetadata


@dataclass
class RegisteredSkill:
    """Represents a registered skill."""

    metadata: SkillMetadata
    skill_path: Path
    skill_instance: Skill | None = None
    enabled: bool = True
    load_error: str | None = None


class SkillRegistry:
    """Registry for managing available skills."""

    def __init__(self, skills_dir: Path) -> None:
        """Initialize the skill registry.

        Args:
            skills_dir: Base directory containing skills
        """
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, RegisteredSkill] = {}
        self._categories: dict[str, list[str]] = {}

    def register(
        self,
        metadata: SkillMetadata,
        skill_path: Path,
        skill_instance: Skill | None = None,
    ) -> None:
        """Register a skill.

        Args:
            metadata: Skill metadata
            skill_path: Path to skill directory
            skill_instance: Optional pre-loaded skill instance
        """
        skill_id = metadata.name
        self._skills[skill_id] = RegisteredSkill(
            metadata=metadata,
            skill_path=skill_path,
            skill_instance=skill_instance,
        )

        # Update categories index
        category = metadata.category
        if category not in self._categories:
            self._categories[category] = []
        if skill_id not in self._categories[category]:
            self._categories[category].append(skill_id)

    def unregister(self, skill_name: str) -> bool:
        """Unregister a skill.

        Args:
            skill_name: Name of skill to unregister

        Returns:
            True if skill was unregistered, False if not found
        """
        if skill_name not in self._skills:
            return False

        skill = self._skills[skill_name]
        category = skill.metadata.category

        # Remove from category index
        if category in self._categories and skill_name in self._categories[category]:
            self._categories[category].remove(skill_name)

        # Remove skill
        del self._skills[skill_name]
        return True

    def get(self, skill_name: str) -> RegisteredSkill | None:
        """Get a registered skill by name.

        Args:
            skill_name: Name of skill to retrieve

        Returns:
            RegisteredSkill or None if not found
        """
        return self._skills.get(skill_name)

    def list_all(self) -> list[RegisteredSkill]:
        """List all registered skills.

        Returns:
            List of all registered skills
        """
        return list(self._skills.values())

    def list_by_category(self, category: str) -> list[RegisteredSkill]:
        """List skills in a specific category.

        Args:
            category: Category name

        Returns:
            List of skills in the category
        """
        skill_names = self._categories.get(category, [])
        return [self._skills[name] for name in skill_names if name in self._skills]

    def list_categories(self) -> list[str]:
        """List all skill categories.

        Returns:
            List of category names
        """
        return list(self._categories.keys())

    def search(
        self,
        query: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> list[RegisteredSkill]:
        """Search for skills matching criteria.

        Args:
            query: Search term for name/description
            category: Filter by category
            tags: Filter by tags

        Returns:
            List of matching skills
        """
        results = self.list_all()

        if category:
            results = [s for s in results if s.metadata.category == category]

        if tags:
            results = [
                s for s in results
                if any(tag in s.metadata.tags for tag in tags)
            ]

        if query:
            query_lower = query.lower()
            results = [
                s for s in results
                if query_lower in s.metadata.name.lower()
                or query_lower in s.metadata.description.lower()
            ]

        return results

    def is_enabled(self, skill_name: str) -> bool:
        """Check if a skill is enabled.

        Args:
            skill_name: Name of skill to check

        Returns:
            True if enabled, False otherwise
        """
        skill = self.get(skill_name)
        return skill.enabled if skill else False

    def enable(self, skill_name: str) -> bool:
        """Enable a skill.

        Args:
            skill_name: Name of skill to enable

        Returns:
            True if skill was enabled, False if not found
        """
        skill = self.get(skill_name)
        if skill:
            skill.enabled = True
            return True
        return False

    def disable(self, skill_name: str) -> bool:
        """Disable a skill.

        Args:
            skill_name: Name of skill to disable

        Returns:
            True if skill was disabled, False if not found
        """
        skill = self.get(skill_name)
        if skill:
            skill.enabled = False
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dictionary with registry stats
        """
        total = len(self._skills)
        enabled = sum(1 for s in self._skills.values() if s.enabled)
        disabled = total - enabled
        categories = len(self._categories)

        return {
            "total_skills": total,
            "enabled_skills": enabled,
            "disabled_skills": disabled,
            "categories": categories,
            "category_breakdown": {
                cat: len(skills) for cat, skills in self._categories.items()
            },
        }
