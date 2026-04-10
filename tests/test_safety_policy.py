"""Tests for safe mode and approval policy decisions."""

from e_cli.agent.protocol import ToolCall
from e_cli.safety.policy import SafetyPolicy


def test_trusted_shell_command_auto_allowed() -> None:
    """Ensures read-only trusted shell commands do not require manual approval."""

    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo", "dir"))
    decision = policy.evaluate(ToolCall(tool="shell", command="echo hello"))
    assert decision.allowed is True
    assert decision.requiresApproval is False


def test_file_write_requires_approval_in_safe_mode() -> None:
    """Ensures mutation actions require explicit approval in safe mode."""

    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))
    decision = policy.evaluate(ToolCall(tool="file.write", path="x.txt", content="hello"))
    assert decision.allowed is True
    assert decision.requiresApproval is True


def test_blocked_shell_pattern_denied_in_safe_mode() -> None:
    """Ensures dangerous shell patterns are denied without approval."""

    policy = SafetyPolicy(
        safeMode=True,
        trustedReadCommands=("echo",),
        blockedShellPatterns=("rm -rf /",),
    )
    decision = policy.evaluate(ToolCall(tool="shell", command="sudo rm -rf / --no-preserve-root"))
    assert decision.allowed is False
    assert decision.requiresApproval is False


def test_blocked_shell_pattern_ignored_when_safe_mode_disabled() -> None:
    """Ensures disabling safe mode allows command execution policy bypass."""

    policy = SafetyPolicy(
        safeMode=False,
        trustedReadCommands=("echo",),
        blockedShellPatterns=("rm -rf /",),
    )
    decision = policy.evaluate(ToolCall(tool="shell", command="rm -rf /"))
    assert decision.allowed is True
    assert decision.requiresApproval is False


def test_read_only_native_tools_auto_allowed() -> None:
    """Ensures git diff and HTTP GET remain auto-allowed in safe mode."""

    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))
    gitDecision = policy.evaluate(ToolCall(tool="git.diff", path="README.md"))
    httpDecision = policy.evaluate(ToolCall(tool="http.get", url="https://example.com"))

    assert gitDecision.allowed is True
    assert gitDecision.requiresApproval is False
    assert httpDecision.allowed is True
    assert httpDecision.requiresApproval is False


def test_browser_auto_allowed_in_safe_mode() -> None:
    """Ensures browser read-style action remains auto-allowed in safe mode."""

    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))
    decision = policy.evaluate(ToolCall(tool="browser", url="https://example.com"))
    assert decision.allowed is True
    assert decision.requiresApproval is False


def test_ssh_requires_approval_and_host() -> None:
    """Ensures SSH requires approval and validates required fields."""

    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))

    missing_host = policy.evaluate(ToolCall(tool="ssh", command="uname -a"))
    assert missing_host.allowed is False

    decision = policy.evaluate(ToolCall(tool="ssh", host="server.local", command="uname -a"))
    assert decision.allowed is True
    assert decision.requiresApproval is True


def test_curl_method_based_approval() -> None:
    """Ensures read-like curl methods are auto-allowed while mutating methods require approval."""

    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))
    read_decision = policy.evaluate(ToolCall(tool="curl", url="https://example.com", method="GET"))
    write_decision = policy.evaluate(ToolCall(tool="curl", url="https://example.com", method="POST"))

    assert read_decision.allowed is True
    assert read_decision.requiresApproval is False
    assert write_decision.allowed is True
    assert write_decision.requiresApproval is True


def test_rag_search_auto_allowed_in_safe_mode() -> None:
    """Ensures rag.search is treated as read-only and does not require approval."""

    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))
    decision = policy.evaluate(ToolCall(tool="rag.search", query="router dispatch", corpus="combined"))
    assert decision.allowed is True
    assert decision.requiresApproval is False


def test_rag_search_requires_query() -> None:
    """Ensures rag.search without a query is blocked by policy validation."""

    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))
    decision = policy.evaluate(ToolCall(tool="rag.search", query=""))
    assert decision.allowed is False


# ---------------------------------------------------------------------------
# approval.py tests
# ---------------------------------------------------------------------------

from e_cli.safety.approval import requestApproval, requestApprovalWithMode


def test_request_approval_with_mode_auto_approve(monkeypatch) -> None:
    """auto-approve mode always returns True without prompting."""
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(AssertionError("should not prompt")))
    result = requestApprovalWithMode(ToolCall(tool="shell", command="ls"), "test", "auto-approve")
    assert result is True


def test_request_approval_with_mode_deny(monkeypatch) -> None:
    """deny mode always returns False without prompting."""
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(AssertionError("should not prompt")))
    result = requestApprovalWithMode(ToolCall(tool="shell", command="ls"), "test", "deny")
    assert result is False


def test_request_approval_with_mode_interactive_yes(monkeypatch) -> None:
    """interactive mode delegates to requestApproval and returns True for 'y'."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = requestApprovalWithMode(ToolCall(tool="shell", command="ls"), "test", "interactive")
    assert result is True


def test_request_approval_with_mode_interactive_no(monkeypatch) -> None:
    """interactive mode delegates to requestApproval and returns False for 'n'."""
    monkeypatch.setattr("builtins.input", lambda _: "n")
    result = requestApprovalWithMode(ToolCall(tool="shell", command="ls"), "test", "interactive")
    assert result is False


def test_request_approval_file_write_path(monkeypatch) -> None:
    """requestApproval prints file path for file.write tool calls."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = requestApproval(ToolCall(tool="file.write", path="out.txt", content="data"), "write test")
    assert result is True


def test_request_approval_file_read_path(monkeypatch) -> None:
    """requestApproval prints file path for file.read tool calls."""
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    result = requestApproval(ToolCall(tool="file.read", path="in.txt"), "read test")
    assert result is True


def test_request_approval_browser_url(monkeypatch) -> None:
    """requestApproval prints URL for browser tool calls."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = requestApproval(ToolCall(tool="browser", url="https://example.com"), "browser test")
    assert result is True


def test_request_approval_ssh_with_user(monkeypatch) -> None:
    """requestApproval prints user@host for SSH tool calls with user."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = requestApproval(
        ToolCall(tool="ssh", host="server.local", command="ls", user="admin"),
        "ssh test",
    )
    assert result is True


def test_request_approval_ssh_without_user(monkeypatch) -> None:
    """requestApproval prints host for SSH tool calls without user."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = requestApproval(
        ToolCall(tool="ssh", host="server.local", command="ls"),
        "ssh test",
    )
    assert result is True


def test_request_approval_curl(monkeypatch) -> None:
    """requestApproval prints method and URL for curl tool calls."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = requestApproval(
        ToolCall(tool="curl", url="https://api.example.com", method="POST"),
        "curl test",
    )
    assert result is True


def test_request_approval_with_mode_exception_returns_false(monkeypatch) -> None:
    """requestApprovalWithMode returns False when an exception occurs."""
    def raise_exc(*args, **kwargs):
        raise RuntimeError("broken")
    monkeypatch.setattr("e_cli.safety.approval.printInfo", raise_exc)
    result = requestApprovalWithMode(ToolCall(tool="shell", command="ls"), "test", "auto-approve")
    assert result is False
