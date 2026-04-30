"""Docker helper skill implementation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from e_cli.skills.base import BaseSkill, SkillMetadata, SkillResult


@dataclass
class DockerHelperSkill(BaseSkill):
    """Docker container and image management utilities."""

    @property
    def metadata(self) -> SkillMetadata:
        """Get skill metadata."""
        return SkillMetadata(
            name="docker-helper",
            version="1.0.0",
            description="Docker container and image management utilities",
            author="E-CLI Team",
            category="devops",
            tags=["docker", "containers", "devops", "deployment"],
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters."""
        operation = kwargs.get("operation")

        if not operation:
            return False, "operation parameter is required"

        valid_operations = ["ps", "images", "inspect", "logs", "stats"]
        if operation not in valid_operations:
            return False, f"Invalid operation: {operation}. Must be one of: {', '.join(valid_operations)}"

        # Validate container param for operations that need it
        if operation in ["inspect", "logs"] and not kwargs.get("container"):
            return False, f"container parameter required for {operation} operation"

        return True, ""

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute docker operation."""
        operation = kwargs["operation"]
        container = kwargs.get("container")
        lines = kwargs.get("lines", 50)
        show_all = kwargs.get("all", False)

        # Build docker command based on operation
        if operation == "ps":
            cmd = ["docker", "ps"]
            if show_all:
                cmd.append("-a")
        elif operation == "images":
            cmd = ["docker", "images"]
            if show_all:
                cmd.append("-a")
        elif operation == "inspect":
            cmd = ["docker", "inspect", container]
        elif operation == "logs":
            cmd = ["docker", "logs", "--tail", str(lines), container]
        elif operation == "stats":
            cmd = ["docker", "stats", "--no-stream"]
            if not show_all:
                cmd.append("--all=false")
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
                timeout=30,
            )

            output = result.stdout if result.stdout else "(no output)"

            return SkillResult(
                ok=True,
                output=output,
                metadata={"operation": operation, "container": container},
            )

        except subprocess.CalledProcessError as e:
            return SkillResult(
                ok=False,
                output="",
                error=f"Docker command failed: {e.stderr}",
            )
        except subprocess.TimeoutExpired:
            return SkillResult(
                ok=False,
                output="",
                error="Docker command timed out after 30 seconds",
            )
        except FileNotFoundError:
            return SkillResult(
                ok=False,
                output="",
                error="Docker command not found. Is docker installed?",
            )

    def get_schema(self) -> dict[str, Any]:
        """Get JSON schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["ps", "images", "inspect", "logs", "stats"],
                    "description": "Docker operation to perform",
                },
                "container": {
                    "type": "string",
                    "description": "Container name or ID for inspect/logs operations",
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of log lines to show",
                    "default": 50,
                },
                "all": {
                    "type": "boolean",
                    "description": "Show all containers/images (including stopped)",
                    "default": False,
                },
            },
            "required": ["operation"],
        }


# Export the skill instance
skill = DockerHelperSkill()
