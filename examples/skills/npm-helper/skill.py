"""NPM helper skill implementation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from e_cli.skills.base import BaseSkill, SkillMetadata, SkillResult


@dataclass
class NpmHelperSkill(BaseSkill):
    """NPM and Node.js development helper."""

    @property
    def metadata(self) -> SkillMetadata:
        """Get skill metadata."""
        return SkillMetadata(
            name="npm-helper",
            version="1.0.0",
            description="NPM and Node.js development helper",
            author="E-CLI Team",
            category="development",
            tags=["npm", "nodejs", "javascript", "development"],
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters."""
        operation = kwargs.get("operation")

        if not operation:
            return False, "operation parameter is required"

        valid_operations = ["init", "install", "uninstall", "list", "run", "version", "outdated"]
        if operation not in valid_operations:
            return False, f"Invalid operation: {operation}. Must be one of: {', '.join(valid_operations)}"

        # Validate operation-specific requirements
        if operation in ["install", "uninstall"] and not kwargs.get("package"):
            if operation == "install":
                # npm install without package is valid (installs from package.json)
                pass
            else:
                return False, f"package parameter required for {operation} operation"

        if operation == "run" and not kwargs.get("script"):
            return False, "script parameter required for run operation"

        return True, ""

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute npm operation."""
        operation = kwargs["operation"]
        package = kwargs.get("package")
        script = kwargs.get("script")
        is_global = kwargs.get("global", False)

        # Build command based on operation
        if operation == "init":
            cmd = ["npm", "init", "-y"]
        elif operation == "install":
            cmd = ["npm", "install"]
            if is_global:
                cmd.append("-g")
            if package:
                cmd.append(package)
        elif operation == "uninstall":
            cmd = ["npm", "uninstall"]
            if is_global:
                cmd.append("-g")
            cmd.append(package)
        elif operation == "list":
            cmd = ["npm", "list"]
            if is_global:
                cmd.extend(["-g", "--depth=0"])
        elif operation == "run":
            cmd = ["npm", "run", script]
        elif operation == "version":
            cmd = ["npm", "--version"]
        elif operation == "outdated":
            cmd = ["npm", "outdated"]
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
                timeout=120,
            )

            output = result.stdout if result.stdout else "(no output)"

            return SkillResult(
                ok=True,
                output=output,
                metadata={"operation": operation, "package": package},
            )

        except subprocess.CalledProcessError as e:
            # npm outdated returns non-zero if packages are outdated, which is not an error
            if operation == "outdated" and e.stdout:
                return SkillResult(
                    ok=True,
                    output=e.stdout,
                    metadata={"operation": operation},
                )

            return SkillResult(
                ok=False,
                output="",
                error=f"NPM command failed: {e.stderr}",
            )
        except subprocess.TimeoutExpired:
            return SkillResult(
                ok=False,
                output="",
                error="NPM command timed out after 120 seconds",
            )
        except FileNotFoundError:
            return SkillResult(
                ok=False,
                output="",
                error="NPM command not found. Is Node.js/NPM installed?",
            )

    def get_schema(self) -> dict[str, Any]:
        """Get JSON schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["init", "install", "uninstall", "list", "run", "version", "outdated"],
                    "description": "NPM operation to perform",
                },
                "package": {
                    "type": "string",
                    "description": "Package name for install/uninstall",
                },
                "script": {
                    "type": "string",
                    "description": "Script name to run",
                },
                "global": {
                    "type": "boolean",
                    "description": "Install globally",
                    "default": False,
                },
            },
            "required": ["operation"],
        }


# Export the skill instance
skill = NpmHelperSkill()
