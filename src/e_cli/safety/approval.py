"""Interactive approval flow for potentially mutating operations."""

from __future__ import annotations

from e_cli.config import ApprovalMode
from e_cli.agent.protocol import ToolCall
from e_cli.ui.messages import printInfo


def requestApprovalWithMode(toolCall: ToolCall, reason: str, approvalMode: ApprovalMode) -> bool:
    """Apply configured approval mode and return action authorization outcome."""

    try:
        if approvalMode == "auto-approve":
            printInfo("Approval mode is auto-approve; action allowed.")
            return True
        if approvalMode == "deny":
            printInfo("Approval mode is deny; action blocked.")
            return False
        return requestApproval(toolCall, reason)
    except Exception:
        return False


def requestApproval(toolCall: ToolCall, reason: str) -> bool:
    """Prompt for user confirmation and return decision outcome."""

    try:
        printInfo(f"Approval required: {reason}")
        if toolCall.tool == "shell":
            printInfo(f"Shell command: {toolCall.command}")
        elif toolCall.tool in {"file.read", "file.write"}:
            printInfo(f"File path: {toolCall.path}")

        userInput = input("Allow this action? [y/N]: ").strip().lower()
        return userInput in {"y", "yes"}
    except Exception:
        return False
