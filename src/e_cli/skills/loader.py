"""Skill loading and hot-reload functionality."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from e_cli.skills.base import Skill, SkillManifest, SkillMetadata
from e_cli.skills.registry import SkillRegistry, RegisteredSkill


class SkillLoader:
    """Loads skills from the filesystem."""

    def __init__(self, registry: SkillRegistry) -> None:
        """Initialize the skill loader.

        Args:
            registry: Skill registry to populate
        """
        self.registry = registry

    def discover_skills(self, base_dir: Path) -> list[Path]:
        """Discover skill directories in a base directory.

        Args:
            base_dir: Base directory to search

        Returns:
            List of paths to skill directories
        """
        if not base_dir.exists():
            return []

        skill_dirs = []

        # Look for directories containing skill.yaml
        for item in base_dir.iterdir():
            if item.is_dir():
                manifest_file = item / "skill.yaml"
                if manifest_file.exists():
                    skill_dirs.append(item)
                else:
                    # Recursively search subdirectories
                    skill_dirs.extend(self.discover_skills(item))

        return skill_dirs

    def load_skill_from_path(self, skill_path: Path) -> RegisteredSkill | None:
        """Load a skill from a directory.

        Args:
            skill_path: Path to skill directory

        Returns:
            RegisteredSkill or None if loading failed
        """
        manifest_file = skill_path / "skill.yaml"
        if not manifest_file.exists():
            return None

        try:
            # Load manifest
            manifest = SkillManifest.from_yaml(manifest_file)
            metadata = manifest.to_metadata()

            # Try to load the skill implementation
            skill_instance = None
            entry_point = skill_path / manifest.entry_point

            if entry_point.exists() and entry_point.suffix == ".py":
                skill_instance = self._load_python_skill(entry_point, skill_path)

            # Register the skill
            self.registry.register(metadata, skill_path, skill_instance)

            registered = self.registry.get(metadata.name)
            return registered

        except Exception as e:
            # Create a registration with error
            metadata = SkillMetadata(
                name=skill_path.name,
                version="unknown",
                description=f"Failed to load: {e}",
            )
            self.registry.register(metadata, skill_path)
            registered = self.registry.get(metadata.name)
            if registered:
                registered.enabled = False
                registered.load_error = str(e)
            return registered

    def _load_python_skill(self, entry_point: Path, skill_path: Path) -> Skill | None:
        """Load a Python skill module.

        Args:
            entry_point: Path to Python entry point file
            skill_path: Path to skill directory

        Returns:
            Skill instance or None if loading failed
        """
        try:
            # Create a unique module name
            module_name = f"e_cli.skills.custom.{skill_path.name}"

            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, entry_point)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Look for a class that implements Skill protocol
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Skill):  # type: ignore[misc]
                    # Found a Skill class, instantiate it
                    if hasattr(attr, "__init__"):
                        return attr(skill_path=skill_path)  # type: ignore[call-arg]
                    return attr()

            return None

        except Exception:
            return None

    def load_all_skills(self) -> int:
        """Discover and load all skills in the registry's skills directory.

        Returns:
            Number of skills loaded
        """
        # Search in core, custom, and community directories
        search_dirs = [
            self.registry.skills_dir / "core",
            self.registry.skills_dir / "custom",
            self.registry.skills_dir / "community",
        ]

        loaded_count = 0

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            skill_dirs = self.discover_skills(search_dir)
            for skill_dir in skill_dirs:
                result = self.load_skill_from_path(skill_dir)
                if result:
                    loaded_count += 1

        return loaded_count

    def reload_skill(self, skill_name: str) -> bool:
        """Reload a skill from disk.

        Args:
            skill_name: Name of skill to reload

        Returns:
            True if reload succeeded, False otherwise
        """
        registered = self.registry.get(skill_name)
        if not registered:
            return False

        # Unregister current version
        self.registry.unregister(skill_name)

        # Reload from path
        reloaded = self.load_skill_from_path(registered.skill_path)
        return reloaded is not None

    def install_skill_from_directory(self, source_dir: Path, target_category: str = "custom") -> bool:
        """Install a skill from a source directory.

        Args:
            source_dir: Source directory containing skill
            target_category: Target category (core/custom/community)

        Returns:
            True if installation succeeded
        """
        import shutil

        if not source_dir.exists():
            return False

        manifest_file = source_dir / "skill.yaml"
        if not manifest_file.exists():
            return False

        try:
            # Load manifest to get skill name
            manifest = SkillManifest.from_yaml(manifest_file)

            # Determine target directory
            target_dir = self.registry.skills_dir / target_category / manifest.name

            # Copy skill directory
            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.copytree(source_dir, target_dir)

            # Load the skill
            result = self.load_skill_from_path(target_dir)
            return result is not None

        except Exception:
            return False
