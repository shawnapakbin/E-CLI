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
