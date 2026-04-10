"""Allowlist_Router — wraps ToolRouter and enforces per-task tool allowlist.

Sub-agents are restricted to the tools declared in their Task_Envelope.
Any tool not in the allowlist is blocked before reaching SafetyPolicy.
Recursive sub-agent spawning (sub_agent.assign) is unconditionally blocked.
Passing calls are delegated to _ScopedToolRouter for SafetyPolicy enforcement.
"""
from __future__ import annotations

from e_cli.agent.protocol import ToolCall, ToolResult
from e_cli.safety.policy import SafetyPolicy
from e_cli.skills.executor import _ScopedToolRouter

# The tool name used for recursive sub-agent spawning — always blocked.
_RECURSIVE_SPAWN_TOOL = "sub_agent.assign"

_BLOCKED_OUTPUT = "Tool not permitted for this sub-task"
_RECURSIVE_OUTPUT = "Recursive sub-agent spawning is not permitted"


class Allowlist_Router:
    """Wraps ToolRouter and enforces a per-task tool allowlist.

    Execution order for every call:
    1. Block ``sub_agent.assign`` unconditionally (recursive spawning guard).
    2. Block any tool not present in ``tool_allowlist``.
    3. Delegate to ``_ScopedToolRouter`` which applies ``SafetyPolicy``.
    """

    def __init__(
        self,
        scoped_router: _ScopedToolRouter,
        tool_allowlist: list[str],
    ) -> None:
        self._scoped_router = scoped_router
        self._tool_allowlist: frozenset[str] = frozenset(tool_allowlist)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, tool_call: ToolCall, timeout_seconds: int = 30) -> ToolResult:
        """Execute *tool_call* subject to allowlist and safety policy checks."""
        tool_name: str = tool_call.tool

        # Gate 1: unconditionally block recursive sub-agent spawning.
        if tool_name == _RECURSIVE_SPAWN_TOOL:
            return ToolResult(ok=False, output=_RECURSIVE_OUTPUT)

        # Gate 2: allowlist check.
        if tool_name not in self._tool_allowlist:
            return ToolResult(ok=False, output=_BLOCKED_OUTPUT)

        # Gate 3: delegate to _ScopedToolRouter for SafetyPolicy enforcement.
        return self._scoped_router.execute(tool_call, timeout_seconds)
