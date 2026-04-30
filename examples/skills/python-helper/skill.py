"""Python helper skill implementation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from e_cli.skills.base import BaseSkill, SkillMetadata, SkillResult


@dataclass
class PythonHelperSkill(BaseSkill):
    """Python development helper utilities."""

    @property
    def metadata(self) -> SkillMetadata:
        """Get skill metadata."""
        return SkillMetadata(
            name="python-helper",
            version="1.0.0",
            description="Python development helper utilities",
            author="E-CLI Team",
            category="development",
            tags=["python", "development", "programming", "pip"],
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters."""
        operation = kwargs.get("operation")

        if not operation:
            return False, "operation parameter is required"

        valid_operations = ["version", "packages", "install", "venv", "run"]
        if operation not in valid_operations:
            return False, f"Invalid operation: {operation}. Must be one of: {', '.join(valid_operations)}"

        # Validate operation-specific requirements
        if operation == "install" and not kwargs.get("package"):
            return False, "package parameter required for install operation"

        if operation == "run" and not kwargs.get("script"):
            return False, "script parameter required for run operation"

        return True, ""

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute python operation."""
        operation = kwargs["operation"]
        package = kwargs.get("package")
        script = kwargs.get("script")
        venv_path = kwargs.get("venv_path")

        # Build command based on operation
        if operation == "version":
            cmd = ["python3", "--version"]
        elif operation == "packages":
            cmd = ["pip", "list"]
        elif operation == "install":
            cmd = ["pip", "install", package]
        elif operation == "venv":
            path = venv_path or "venv"
            cmd = ["python3", "-m", "venv", path]
        elif operation == "run":
            cmd = ["python3", script]
        else:
            return SkillResult(
                ok=False,
                output="",
                error=f"Unknown operation: {operation}",
            )

        # Execute command
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            output = result.stdout if result.stdout else result.stderr
            if not output:
                output = f"Operation '{operation}' completed successfully"

            return SkillResult(
                ok=True,
                output=output,
                metadata={"operation": operation},
            )

        except subprocess.CalledProcessError as e:
            return SkillResult(
                ok=False,
                output="",
                error=f"Python command failed: {e.stderr}",
            )
        except subprocess.TimeoutExpired:
            return SkillResult(
                ok=False,
                output="",
                error="Python command timed out after 60 seconds",
            )
        except FileNotFoundError:
            return SkillResult(
                ok=False,
                output="",
                error="Python command not found. Is Python installed?",
            )

    def get_schema(self) -> dict[str, Any]:
        """Get JSON schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["version", "packages", "install", "venv", "run"],
                    "description": "Python operation to perform",
                },
                "package": {
                    "type": "string",
                    "description": "Package name for install operation",
                },
                "script": {
                    "type": "string",
                    "description": "Python script to run",
                },
                "venv_path": {
                    "type": "string",
                    "description": "Virtual environment path",
                },
            },
            "required": ["operation"],
        }


# Export the skill instance
skill = PythonHelperSkill()
