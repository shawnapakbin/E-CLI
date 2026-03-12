"""Tests for UI messaging wrappers and approval interaction."""

from e_cli.agent.protocol import ToolCall
from e_cli.safety.approval import requestApproval
from e_cli.ui import messages


def test_message_wrappers(monkeypatch) -> None:
    """Ensures wrapper methods invoke underlying console output calls."""

    captured: list[str] = []

    class FakeConsole:
        def print(self, text: str = "", **kwargs: object) -> None:
            _ = kwargs
            captured.append(text)

    monkeypatch.setattr(messages, "console", FakeConsole())
    messages.printInfo("info")
    messages.printError("error")
    messages.printQuickTip("tip")
    messages.printStream("stream")
    messages.printStreamBreak()

    assert any("info" in line for line in captured)
    assert any("error" in line for line in captured)
    assert any("tip" in line for line in captured)
    assert any("stream" in line for line in captured)


def test_request_approval_yes(monkeypatch) -> None:
    """Ensures approval helper returns true for explicit yes input."""

    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    allowed = requestApproval(ToolCall(tool="shell", command="echo hi"), "test")
    assert allowed is True


def test_request_approval_exception(monkeypatch) -> None:
    """Ensures approval helper fails closed when prompt read fails."""

    def raiseInput(_prompt: str) -> str:
        raise RuntimeError("broken")

    monkeypatch.setattr("builtins.input", raiseInput)
    allowed = requestApproval(ToolCall(tool="file.write", path="x", content="y"), "test")
    assert allowed is False
