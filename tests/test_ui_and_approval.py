"""Tests for UI messaging wrappers and approval interaction."""

import pytest

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


def test_print_warning(monkeypatch) -> None:
    """Ensures printWarning delegates to the console."""

    captured: list[str] = []

    class FakeConsole:
        def print(self, text: str = "", **kwargs: object) -> None:
            _ = kwargs
            captured.append(text)

    monkeypatch.setattr(messages, "console", FakeConsole())
    messages.printWarning("something went wrong")
    assert any("something went wrong" in line for line in captured)


@pytest.mark.parametrize("fn,arg", [
    (messages.info, "i"),
    (messages.warn, "w"),
    (messages.error, "e"),
    (messages.quick_tip, "t"),
    (messages.stream, "s"),
])
def test_message_functions_raise_on_console_failure(monkeypatch, fn, arg) -> None:
    """Ensures primitive message functions re-raise when console.print fails."""

    class BrokenConsole:
        def print(self, *args: object, **kwargs: object) -> None:
            raise OSError("console broken")

    monkeypatch.setattr(messages, "console", BrokenConsole())
    with pytest.raises(RuntimeError):
        fn(arg)


def test_stream_break_raises_on_console_failure(monkeypatch) -> None:
    """Ensures streamBreak re-raises when console.print fails."""

    class BrokenConsole:
        def print(self, *args: object, **kwargs: object) -> None:
            raise OSError("console broken")

    monkeypatch.setattr(messages, "console", BrokenConsole())
    with pytest.raises(RuntimeError):
        messages.streamBreak()


@pytest.mark.parametrize("fn,arg", [
    (messages.printQuickTip, "tip"),
    (messages.printInfo, "info"),
    (messages.printError, "err"),
    (messages.printStream, "stream"),
    (messages.printWarning, "warn"),
])
def test_wrapper_functions_raise_on_console_failure(monkeypatch, fn, arg) -> None:
    """Ensures all compatibility wrapper functions propagate console failures."""

    class BrokenConsole:
        def print(self, *args: object, **kwargs: object) -> None:
            raise OSError("console broken")

    monkeypatch.setattr(messages, "console", BrokenConsole())
    with pytest.raises(RuntimeError):
        fn(arg)


def test_print_stream_break_raises_on_console_failure(monkeypatch) -> None:
    """Ensures printStreamBreak raises when the underlying console call fails."""

    class BrokenConsole:
        def print(self, *args: object, **kwargs: object) -> None:
            raise OSError("console broken")

    monkeypatch.setattr(messages, "console", BrokenConsole())
    with pytest.raises(RuntimeError):
        messages.printStreamBreak()


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
