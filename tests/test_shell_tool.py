"""Tests for shell tool execution behavior."""

from e_cli.tools.shell_tool import ShellTool


def test_shell_tool_success() -> None:
    """Ensures shell tool executes a simple command successfully."""

    result = ShellTool.run("echo hello", timeout_seconds=5)
    assert result.ok is True
    assert result.exitCode == 0


def test_shell_tool_timeout() -> None:
    """Ensures timeout path returns expected exit code and error state."""

    # Uses a cross-platform Python sleep command to force timeout.
    result = ShellTool.run('python -c "import time; time.sleep(2)"', timeout_seconds=1)
    assert result.ok is False
    assert result.exitCode == 124
