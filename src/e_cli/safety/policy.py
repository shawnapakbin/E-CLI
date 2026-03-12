"""Safety policy checks for shell and file operations."""

from __future__ import annotations

from dataclasses import dataclass

from e_cli.agent.protocol import ToolCall


@dataclass(frozen=True)
class SafetyDecision:
    """Represents policy output for a requested tool call."""

    allowed: bool
    requiresApproval: bool
    reason: str


class SafetyPolicy:
    """Evaluates tool calls against safe mode and trusted command rules."""

    def __init__(
        self,
        safeMode: bool,
        trustedReadCommands: tuple[str, ...],
        blockedShellPatterns: tuple[str, ...] = (),
    ) -> None:
        """Stores runtime safety toggles and trusted shell command prefixes."""

        self.safeMode = safeMode
        self.trustedReadCommands = trustedReadCommands
        self.blockedShellPatterns = blockedShellPatterns

    def evaluate(self, toolCall: ToolCall) -> SafetyDecision:
        """Returns policy decision for a tool request."""

        try:
            if not self.safeMode:
                return SafetyDecision(allowed=True, requiresApproval=False, reason="safe-mode disabled")

            if toolCall.tool == "done":
                return SafetyDecision(allowed=True, requiresApproval=False, reason="completion event")

            if toolCall.tool == "file.read":
                return SafetyDecision(allowed=True, requiresApproval=False, reason="read-only file action")

            if toolCall.tool == "git.diff":
                return SafetyDecision(allowed=True, requiresApproval=False, reason="read-only git action")

            if toolCall.tool == "http.get":
                return SafetyDecision(allowed=True, requiresApproval=False, reason="read-only http action")

            if toolCall.tool == "browser":
                return SafetyDecision(allowed=True, requiresApproval=False, reason="read-only browser action")

            if toolCall.tool == "rag.search":
                if not (toolCall.query or "").strip():
                    return SafetyDecision(allowed=False, requiresApproval=False, reason="missing rag query")
                return SafetyDecision(allowed=True, requiresApproval=False, reason="read-only rag action")

            if toolCall.tool == "curl":
                method = (toolCall.method or "GET").strip().upper()
                if method in {"GET", "HEAD", "OPTIONS"}:
                    return SafetyDecision(allowed=True, requiresApproval=False, reason="read-like curl action")
                return SafetyDecision(
                    allowed=True,
                    requiresApproval=True,
                    reason="mutating curl action requires approval in safe mode",
                )

            if toolCall.tool == "ssh":
                if not toolCall.host:
                    return SafetyDecision(allowed=False, requiresApproval=False, reason="missing ssh host")
                if not toolCall.command:
                    return SafetyDecision(allowed=False, requiresApproval=False, reason="missing ssh command")
                return SafetyDecision(
                    allowed=True,
                    requiresApproval=True,
                    reason="ssh command requires approval in safe mode",
                )

            if toolCall.tool == "shell":
                if not toolCall.command:
                    return SafetyDecision(allowed=False, requiresApproval=False, reason="missing command")

                commandLower = toolCall.command.strip().lower()
                blockedMatch = any(pattern.lower() in commandLower for pattern in self.blockedShellPatterns)
                if blockedMatch:
                    return SafetyDecision(
                        allowed=False,
                        requiresApproval=False,
                        reason="command blocked by safety policy",
                    )

                trustedMatch = any(
                    commandLower.startswith(trustedPrefix.lower())
                    for trustedPrefix in self.trustedReadCommands
                )
                if trustedMatch:
                    return SafetyDecision(allowed=True, requiresApproval=False, reason="trusted read command")
                return SafetyDecision(
                    allowed=True,
                    requiresApproval=True,
                    reason="shell command requires approval in safe mode",
                )

            if toolCall.tool == "file.write":
                return SafetyDecision(
                    allowed=True,
                    requiresApproval=True,
                    reason="file write requires approval in safe mode",
                )

            return SafetyDecision(allowed=False, requiresApproval=False, reason="unknown tool")
        except Exception as exc:
            return SafetyDecision(allowed=False, requiresApproval=False, reason=f"policy error: {exc}")
