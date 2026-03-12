"""Tests for SSH helper behavior."""

from e_cli.tools.ssh_tool import SshTool


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "ok", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_ssh_run_executes_command(monkeypatch) -> None:
    """Ensures SSH helper builds command and returns structured output."""

    monkeypatch.setattr(
        "e_cli.tools.ssh_tool.subprocess.run",
        lambda cmd_parts, capture_output, text, timeout, check: _FakeCompleted(returncode=0, stdout="linux"),
    )
    result = SshTool.run(host="server.local", remote_command="uname -a", timeout_seconds=3)
    assert result.ok is True
    assert result.exitCode == 0
    assert "linux" in result.output


def test_ssh_run_requires_host_and_command() -> None:
    """Ensures SSH helper validates required fields."""

    missing_host = SshTool.run(host="", remote_command="uname -a", timeout_seconds=3)
    missing_command = SshTool.run(host="server.local", remote_command="", timeout_seconds=3)
    assert missing_host.ok is False
    assert missing_command.ok is False
