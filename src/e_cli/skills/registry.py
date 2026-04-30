"""Skill registry for discovering and managing skills."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from e_cli.skills.base import Skill, SkillMetadata


@dataclass
class RegisteredSkill:
    """Represents a registered skill."""

    name: str
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
        name: str,
        skill_instance: Skill | None,
        manifest_path: Path,
        category: str = "general",
    ) -> RegisteredSkill:
        """Register a skill.

        Args:
            name: Skill name
            skill_instance: Skill instance
            manifest_path: Path to skill directory
            category: Skill category
        """
        # Build metadata from skill instance if available, otherwise use defaults
        version = "1.0.0"
        description = ""
        author = "unknown"
        tags: list[str] = []

        if skill_instance is not None:
            try:
                sm = skill_instance.metadata
                version = sm.version
                description = sm.description
                author = sm.author
                tags = list(sm.tags)
            except Exception:
                pass

        meta = SkillMetadata(
            name=name,
            version=version,
            description=description,
            author=author,
            category=category,
            tags=tags,
        )

        registered = RegisteredSkill(
            name=name,
            metadata=meta,
            skill_path=manifest_path,
            skill_instance=skill_instance,
        )
        self._skills[name] = registered

        # Update categories index
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)

        return registered

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
