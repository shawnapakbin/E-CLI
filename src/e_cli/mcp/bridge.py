"""MCPBridge: manages MCP stdio server subprocesses and translates JSON-RPC 2.0 tool calls."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from e_cli.agent.protocol import ToolResult
from e_cli.config import MCPServerConfig

logger = logging.getLogger(__name__)

_STARTUP_TIMEOUT = 5.0   # seconds to wait for tools/list response
_SHUTDOWN_TIMEOUT = 3.0  # seconds to wait for graceful shutdown


@dataclass
class ToolDefinition:
    """Minimal tool definition registered from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    safety_class: str
    server_name: str


@dataclass
class _ServerState:
    """Runtime state for one managed MCP server subprocess."""

    config: MCPServerConfig
    process: asyncio.subprocess.Process | None = None
    tools: list[ToolDefinition] = field(default_factory=list)
    available: bool = False
    _next_id: int = 1

    def next_id(self) -> int:
        current = self._next_id
        self._next_id += 1
        return current


class MCPBridge:
    """Manages MCP server subprocesses and routes tool calls via JSON-RPC 2.0 over stdio."""

    def __init__(self, server_configs: list[MCPServerConfig]) -> None:
        self._configs = server_configs
        self._servers: dict[str, _ServerState] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_servers(self) -> None:
        """Launch all configured MCP servers and register their tools."""
        for cfg in self._configs:
            state = _ServerState(config=cfg)
            self._servers[cfg.name] = state
            await self._launch_server(state)

    async def stop_servers(self) -> None:
        """Send shutdown notification to each server and terminate within 3 seconds."""
        for state in self._servers.values():
            await self._shutdown_server(state)

    def registered_tools(self) -> list[ToolDefinition]:
        """Return all currently available tool definitions across all servers."""
        tools: list[ToolDefinition] = []
        for state in self._servers.values():
            if state.available:
                tools.extend(state.tools)
        return tools

    async def call_tool(self, name: str, args: dict[str, Any]) -> ToolResult:
        """Forward a tool call to the appropriate MCP server and return a ToolResult."""
        state = self._find_server_for_tool(name)
        if state is None:
            return ToolResult(ok=False, output=f"MCP tool '{name}' not available.")
        if not state.available or state.process is None:
            return ToolResult(ok=False, output=f"MCP server '{state.config.name}' is unavailable.")

        request = {
            "jsonrpc": "2.0",
            "id": state.next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
        try:
            response = await self._send_request(state, request)
        except Exception as exc:
            logger.error("MCP tool call failed for '%s': %s", name, exc)
            return ToolResult(ok=False, output=f"MCP call error: {exc}")

        if response is None:
            return ToolResult(ok=False, output="No response from MCP server.")

        if "error" in response:
            err = response["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return ToolResult(ok=False, output=f"MCP error: {msg}")

        result = response.get("result", {})
        content = result.get("content", [])
        if isinstance(content, list):
            parts = [c.get("text", "") for c in content if isinstance(c, dict)]
            output = "\n".join(parts)
        else:
            output = str(content)

        return ToolResult(ok=True, output=output)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _launch_server(self, state: _ServerState) -> None:
        """Start the subprocess for one server and call tools/list with a 5s timeout."""
        cfg = state.config
        env = {**os.environ, **cfg.env} if cfg.env else None
        try:
            process = await asyncio.create_subprocess_exec(
                cfg.command,
                *cfg.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            state.process = process
        except Exception as exc:
            logger.error("Failed to start MCP server '%s': %s", cfg.name, exc)
            return

        # Perform tools/list with startup timeout
        try:
            tools = await asyncio.wait_for(self._fetch_tools(state), timeout=_STARTUP_TIMEOUT)
            state.tools = tools
            state.available = True
            logger.info("MCP server '%s' started with %d tool(s).", cfg.name, len(tools))
        except asyncio.TimeoutError:
            logger.error(
                "MCP server '%s' did not respond to tools/list within %ss; skipping.",
                cfg.name,
                _STARTUP_TIMEOUT,
            )
            await self._kill_process(state.process)
            state.process = None
        except Exception as exc:
            logger.error("MCP server '%s' tools/list failed: %s", cfg.name, exc)
            await self._kill_process(state.process)
            state.process = None

    async def _fetch_tools(self, state: _ServerState) -> list[ToolDefinition]:
        """Send tools/list and parse the returned tool definitions."""
        request = {
            "jsonrpc": "2.0",
            "id": state.next_id(),
            "method": "tools/list",
            "params": {},
        }
        response = await self._send_request(state, request)
        if response is None or "error" in response:
            return []

        raw_tools = response.get("result", {}).get("tools", [])
        definitions: list[ToolDefinition] = []
        for t in raw_tools:
            if not isinstance(t, dict):
                continue
            schema = t.get("inputSchema", {})
            safety = schema.get("safetyClass", "mutating")
            definitions.append(
                ToolDefinition(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    input_schema=schema,
                    safety_class=safety,
                    server_name=state.config.name,
                )
            )
        return definitions

    async def _send_request(
        self, state: _ServerState, request: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Write a JSON-RPC request line and read the response line."""
        if state.process is None or state.process.stdin is None or state.process.stdout is None:
            return None

        line = json.dumps(request) + "\n"
        state.process.stdin.write(line.encode())
        await state.process.stdin.drain()

        raw = await state.process.stdout.readline()
        if not raw:
            return None
        return json.loads(raw.decode().strip())

    async def _shutdown_server(self, state: _ServerState) -> None:
        """Send shutdown notification and terminate the process within 3 seconds."""
        if state.process is None:
            return

        # Send shutdown notification (no response expected)
        notification = {"jsonrpc": "2.0", "method": "shutdown", "params": {}}
        try:
            if state.process.stdin and not state.process.stdin.is_closing():
                line = json.dumps(notification) + "\n"
                state.process.stdin.write(line.encode())
                await state.process.stdin.drain()
                state.process.stdin.close()
        except Exception:
            pass

        # Wait up to 3 seconds for graceful exit
        try:
            await asyncio.wait_for(state.process.wait(), timeout=_SHUTDOWN_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("MCP server '%s' did not exit; terminating.", state.config.name)
            await self._kill_process(state.process)

        state.available = False

    async def _restart_server(self, name: str) -> None:
        """Attempt one restart of the named server; mark tools unavailable if it fails."""
        state = self._servers.get(name)
        if state is None:
            return

        logger.warning("MCP server '%s' exited unexpectedly; attempting restart.", name)
        state.available = False
        state.tools = []
        state.process = None

        await self._launch_server(state)
        if not state.available:
            logger.error(
                "MCP server '%s' failed to restart; its tools are now unavailable.", name
            )

    def _find_server_for_tool(self, tool_name: str) -> _ServerState | None:
        """Return the server state that owns the given tool name."""
        for state in self._servers.values():
            if state.available and any(t.name == tool_name for t in state.tools):
                return state
        return None

    @staticmethod
    async def _kill_process(process: asyncio.subprocess.Process | None) -> None:
        """Forcefully terminate a subprocess if it is still running."""
        if process is None:
            return
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
