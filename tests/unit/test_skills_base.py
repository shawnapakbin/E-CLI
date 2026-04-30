"""Unit tests for skills base module."""

from dataclasses import dataclass
from typing import Any

from e_cli.skills.base import BaseSkill, SkillMetadata, SkillResult


@dataclass
class MockSkill(BaseSkill):
    """Mock skill for testing."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="mock-skill",
            version="1.0.0",
            description="Mock skill for testing",
            author="test",
            category="test",
            tags=["test", "mock"],
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate that required param exists."""
        if "required_param" not in kwargs:
            return False, "required_param is missing"
        return True, ""

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute mock operation."""
        value = kwargs.get("required_param", "")
        return SkillResult(
            ok=True,
            output=f"Processed: {value}",
            metadata={"input": value},
        )

    def get_schema(self) -> dict[str, Any]:
        """Get parameter schema."""
        return {
            "type": "object",
            "properties": {
                "required_param": {
                    "type": "string",
                    "description": "Required parameter",
                }
            },
            "required": ["required_param"],
        }


class TestSkillMetadata:
    """Test SkillMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating skill metadata."""
        metadata = SkillMetadata(
            name="test-skill",
            version="1.0.0",
            description="Test description",
            author="tester",
            category="testing",
            tags=["test", "example"],
        )

        assert metadata.name == "test-skill"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test description"
        assert metadata.author == "tester"
        assert metadata.category == "testing"
        assert metadata.tags == ["test", "example"]

    def test_metadata_defaults(self):
        """Test metadata default values."""
        metadata = SkillMetadata(
            name="minimal",
            version="1.0.0",
            description="Minimal metadata",
        )

        assert metadata.author == "unknown"
        assert metadata.category == "general"
        assert metadata.tags == []


class TestSkillResult:
    """Test SkillResult dataclass."""

    def test_successful_result(self):
        """Test creating successful result."""
        result = SkillResult(
            ok=True,
            output="Success message",
            metadata={"key": "value"},
        )

        assert result.ok is True
        assert result.output == "Success message"
        assert result.error == ""
        assert result.metadata == {"key": "value"}

    def test_error_result(self):
        """Test creating error result."""
        result = SkillResult(
            ok=False,
            output="",
            error="Error message",
        )

        assert result.ok is False
        assert result.output == ""
        assert result.error == "Error message"
        assert result.metadata == {}


class TestBaseSkill:
    """Test BaseSkill abstract class."""

    def test_skill_metadata(self):
        """Test skill metadata property."""
        skill = MockSkill()
        metadata = skill.metadata

        assert metadata.name == "mock-skill"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Mock skill for testing"
        assert "test" in metadata.tags

    def test_validate_input_success(self):
        """Test successful input validation."""
        skill = MockSkill()
        is_valid, message = skill.validate_input(required_param="test")

        assert is_valid is True
        assert message == ""

    def test_validate_input_failure(self):
        """Test failed input validation."""
        skill = MockSkill()
        is_valid, message = skill.validate_input()

        assert is_valid is False
        assert "required_param" in message

    def test_execute_success(self):
        """Test successful skill execution."""
        skill = MockSkill()
        result = skill.execute(required_param="test-value")

        assert result.ok is True
        assert "test-value" in result.output
        assert result.metadata["input"] == "test-value"

    def test_get_schema(self):
        """Test getting parameter schema."""
        skill = MockSkill()
        schema = skill.get_schema()

        assert schema["type"] == "object"
        assert "required_param" in schema["properties"]
        assert schema["required"] == ["required_param"]
