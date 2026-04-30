"""Base classes and protocols for E-CLI skills system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass
class SkillMetadata:
    """Metadata for a skill."""

    name: str
    version: str
    description: str
    author: str = "unknown"
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)


@dataclass
class SkillResult:
    """Result from skill execution."""

    ok: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class Skill(Protocol):
    """Protocol that all skills must implement."""

    @property
    def metadata(self) -> SkillMetadata:
        """Return skill metadata."""
        ...

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters.

        Args:
            **kwargs: Input parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        ...

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute the skill with given parameters.

        Args:
            **kwargs: Execution parameters

        Returns:
            SkillResult with execution outcome
        """
        ...

    def get_schema(self) -> dict[str, Any]:
        """Return JSON schema for skill parameters.

        Returns:
            JSON schema dictionary
        """
        ...


class BaseSkill(ABC):
    """Abstract base class for implementing skills.

    Provides common functionality for skill implementations.
    """

    def __init__(self, skill_path: Path | None = None) -> None:
        """Initialize the skill.

        Args:
            skill_path: Optional path to skill directory
        """
        self.skill_path = skill_path
        self._metadata: SkillMetadata | None = None

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """Return skill metadata."""
        pass

    @abstractmethod
    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute the skill."""
        pass

    def get_schema(self) -> dict[str, Any]:
        """Return JSON schema for skill parameters.

        Default implementation returns empty schema.
        Override for specific parameter requirements.
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def _success(self, output: str, data: dict[str, Any] | None = None) -> SkillResult:
        """Create a success result.

        Args:
            output: Output message
            data: Optional result data

        Returns:
            SkillResult indicating success
        """
        return SkillResult(ok=True, output=output, data=data or {})

    def _error(self, error: str, output: str = "") -> SkillResult:
        """Create an error result.

        Args:
            error: Error message
            output: Optional output message

        Returns:
            SkillResult indicating failure
        """
        return SkillResult(ok=False, output=output, error=error)


class PythonSkill(BaseSkill):
    """Base class for Python-based skills.

    Provides helpers for skills implemented directly in Python.
    """

    def __init__(self, skill_path: Path | None = None) -> None:
        """Initialize Python skill."""
        super().__init__(skill_path)

    def load_config(self) -> dict[str, Any]:
        """Load skill configuration from skill.yaml if present.

        Returns:
            Configuration dictionary
        """
        if not self.skill_path:
            return {}

        config_file = self.skill_path / "skill.yaml"
        if not config_file.exists():
            return {}

        try:
            import yaml
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}


@dataclass
class SkillManifest:
    """Manifest file for a skill, typically loaded from skill.yaml."""

    name: str
    version: str
    description: str
    author: str = "unknown"
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    entry_point: str = "executor.py"
    parameters: list[dict[str, Any]] = field(default_factory=list)

    def to_metadata(self) -> SkillMetadata:
        """Convert manifest to metadata."""
        return SkillMetadata(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            category=self.category,
            tags=self.tags,
            dependencies=self.dependencies,
            permissions=self.permissions,
        )

    @staticmethod
    def from_yaml(yaml_path: Path) -> SkillManifest:
        """Load manifest from YAML file.

        Args:
            yaml_path: Path to skill.yaml

        Returns:
            SkillManifest instance
        """
        import yaml

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        return SkillManifest(
            name=data.get("name", "unknown"),
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", "unknown"),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", []),
            permissions=data.get("permissions", []),
            entry_point=data.get("entry_point", "executor.py"),
            parameters=data.get("parameters", []),
        )
