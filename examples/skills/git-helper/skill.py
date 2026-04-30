"""Git helper skill implementation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from e_cli.skills.base import BaseSkill, SkillMetadata, SkillResult


@dataclass
class GitHelperSkill(BaseSkill):
    """Git repository helper utilities."""

    @property
    def metadata(self) -> SkillMetadata:
        """Get skill metadata."""
        return SkillMetadata(
            name="git-helper",
            version="1.0.0",
            description="Git repository helper utilities for common operations",
            author="E-CLI Team",
            category="development",
            tags=["git", "vcs", "development", "scm"],
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters."""
        operation = kwargs.get("operation")

        if not operation:
            return False, "operation parameter is required"

        valid_operations = ["status", "log", "diff", "branch", "remote"]
        if operation not in valid_operations:
            return False, f"Invalid operation: {operation}. Must be one of: {', '.join(valid_operations)}"

        return True, ""

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute git operation."""
        operation = kwargs["operation"]
        branch = kwargs.get("branch")
        limit = kwargs.get("limit", 10)

        # Build git command based on operation
        if operation == "status":
            cmd = ["git", "status", "--short"]
        elif operation == "log":
            cmd = ["git", "log", f"--oneline", f"-n{limit}"]
            if branch:
                cmd.append(branch)
        elif operation == "diff":
            cmd = ["git", "diff"]
            if branch:
                cmd.append(branch)
            else:
                cmd.append("HEAD")
        elif operation == "branch":
            cmd = ["git", "branch", "-vv"]
        elif operation == "remote":
            cmd = ["git", "remote", "-v"]
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

            return SkillResult(
                ok=True,
                output=result.stdout if result.stdout else "(no output)",
                metadata={"operation": operation, "branch": branch},
            )

        except subprocess.CalledProcessError as e:
            return SkillResult(
                ok=False,
                output="",
                error=f"Git command failed: {e.stderr}",
            )
        except subprocess.TimeoutExpired:
            return SkillResult(
                ok=False,
                output="",
                error="Git command timed out after 30 seconds",
            )
        except FileNotFoundError:
            return SkillResult(
                ok=False,
                output="",
                error="Git command not found. Is git installed?",
            )

    def get_schema(self) -> dict[str, Any]:
        """Get JSON schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["status", "log", "diff", "branch", "remote"],
                    "description": "Git operation to perform",
                },
                "branch": {
                    "type": "string",
                    "description": "Optional branch name for log/diff operations",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of log entries to show",
                    "default": 10,
                },
            },
            "required": ["operation"],
        }


# Export the skill instance
skill = GitHelperSkill()
