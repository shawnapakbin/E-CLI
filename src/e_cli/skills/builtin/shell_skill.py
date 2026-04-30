"""Shell execution skill - converted from shell_tool."""

from __future__ import annotations

from typing import Any

from e_cli.skills.base import PythonSkill, SkillMetadata, SkillResult
from e_cli.tools.shell_tool import ShellTool


class ShellSkill(PythonSkill):
    """Execute shell commands safely."""

    @property
    def metadata(self) -> SkillMetadata:
        """Return skill metadata."""
        return SkillMetadata(
            name="shell",
            version="1.0.0",
            description="Execute shell commands with configurable safety checks",
            author="e-cli-core",
            category="core",
            tags=["shell", "command", "execution"],
            permissions=["shell.execute"],
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters."""
        if "command" not in kwargs:
            return False, "Missing required parameter: command"

        command = kwargs.get("command")
        if not isinstance(command, str):
            return False, "Parameter 'command' must be a string"

        if not command.strip():
            return False, "Command cannot be empty"

        return True, ""

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute the shell command."""
        command = kwargs.get("command", "")
        timeout_seconds = kwargs.get("timeout_seconds", 60)

        try:
            result = ShellTool.run(command=command, timeout_seconds=timeout_seconds)

            output = f"exitCode={result.exitCode}\n{result.output}"

            return SkillResult(
                ok=result.ok,
                output=output,
                data={"exit_code": result.exitCode},
            )

        except Exception as e:
            return self._error(f"Shell execution failed: {e}")

    def get_schema(self) -> dict[str, Any]:
        """Return JSON schema for skill parameters."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 60,
                },
            },
            "required": ["command"],
        }
