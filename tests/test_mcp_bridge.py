"""Unit tests for MCPBridge — mocking subprocess stdio."""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from e_cli.config import MCPServerConfig
from e_cli.mcp.bridge import MCPBridge, ToolDefinition, _ServerState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(name: str = "test-server", command: str = "echo", args: list[str] | None = None) -> MCPServerConfig:
    return MCPServerConfig(name=name, command=command, args=args or [])


def _make_tools_list_response(tools: list[dict[str, Any]], req_id: int = 1) -> bytes:
    resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
    return (json.dumps(resp) + "\n").encode()


def _make_call_response(content: str, req_id: int = 2) -> bytes:
    resp = {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"content": [{"type": "text", "text": content}]},
    }
    return (json.dumps(resp) + "\n").encode()


def _make_error_response(message: str, req_id: int = 2) -> bytes:
    resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": message}}
    return (json.dumps(resp) + "\n").encode()


def _mock_process(responses: list[bytes]) -> MagicMock:
    """Build a mock asyncio.subprocess.Process that returns responses in order."""
    process = MagicMock()
    process.returncode = None

    # stdin
    stdin = MagicMock()
    stdin.write = MagicMock()
    stdin.drain = AsyncMock()
    stdin.close = MagicMock()
    stdin.is_closing = MagicMock(return_value=False)
    process.stdin = stdin

    # stdout — readline returns each response in sequence then b""
    response_iter = iter(responses + [b""])
    async def readline():
        return next(response_iter, b"")
    process.stdout = MagicMock()
    process.stdout.readline = readline

    # wait — returns immediately
    process.wait = AsyncMock(return_value=0)
    process.kill = MagicMock()
    return process


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

class TestToolRegistration:
    """Tests for tools/list on startup and registered_tools()."""

    @pytest.mark.asyncio
    async def test_registers_tools_from_server(self):
        """Tools returned by tools/list are registered and accessible."""
        raw_tools = [
            {
                "name": "my_tool",
                "description": "Does something",
                "inputSchema": {"type": "object", "safetyClass": "read-only"},
            }
        ]
        process = _mock_process([_make_tools_list_response(raw_tools)])

        bridge = MCPBridge([_make_config()])
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            await bridge.start_servers()

        tools = bridge.registered_tools()
        assert len(tools) == 1
        assert tools[0].name == "my_tool"
        assert tools[0].safety_class == "read-only"
        assert tools[0].server_name == "test-server"

    @pytest.mark.asyncio
    async def test_no_tools_when_server_fails_to_start(self):
        """If subprocess creation raises, no tools are registered."""
        bridge = MCPBridge([_make_config()])
        with patch("asyncio.create_subprocess_exec", AsyncMock(side_effect=OSError("not found"))):
            await bridge.start_servers()

        assert bridge.registered_tools() == []

    @pytest.mark.asyncio
    async def test_startup_timeout_skips_server(self):
        """If tools/list takes longer than 5 s, server is skipped."""
        process = MagicMock()
        process.stdin = MagicMock()
        process.stdin.write = MagicMock()
        process.stdin.drain = AsyncMock()
        process.stdin.is_closing = MagicMock(return_value=False)
        process.stdout = MagicMock()

        async def slow_readline():
            await asyncio.sleep(10)
            return b""

        process.stdout.readline = slow_readline
        process.kill = MagicMock()
        process.wait = AsyncMock(return_value=0)

        bridge = MCPBridge([_make_config()])
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            await bridge.start_servers()

        assert bridge.registered_tools() == []

    @pytest.mark.asyncio
    async def test_default_safety_class_is_mutating(self):
        """Tools without safetyClass in schema default to 'mutating'."""
        raw_tools = [
            {
                "name": "unsafe_tool",
                "description": "No safety class declared",
                "inputSchema": {"type": "object"},
            }
        ]
        process = _mock_process([_make_tools_list_response(raw_tools)])

        bridge = MCPBridge([_make_config()])
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            await bridge.start_servers()

        tools = bridge.registered_tools()
        assert tools[0].safety_class == "mutating"

    @pytest.mark.asyncio
    async def test_multiple_servers_aggregate_tools(self):
        """Tools from multiple servers are all returned by registered_tools()."""
        raw_a = [{"name": "tool_a", "description": "", "inputSchema": {}}]
        raw_b = [{"name": "tool_b", "description": "", "inputSchema": {}}]

        proc_a = _mock_process([_make_tools_list_response(raw_a, req_id=1)])
        proc_b = _mock_process([_make_tools_list_response(raw_b, req_id=1)])

        configs = [_make_config("server-a"), _make_config("server-b")]
        bridge = MCPBridge(configs)

        call_count = 0
        procs = [proc_a, proc_b]

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            p = procs[call_count]
            call_count += 1
            return p

        with patch("asyncio.create_subprocess_exec", fake_exec):
            await bridge.start_servers()

        names = {t.name for t in bridge.registered_tools()}
        assert "tool_a" in names
        assert "tool_b" in names


# ---------------------------------------------------------------------------
# Tool call forwarding
# ---------------------------------------------------------------------------

class TestToolCallForwarding:
    """Tests for call_tool() forwarding to MCP server."""

    @pytest.mark.asyncio
    async def test_successful_tool_call(self):
        """A successful tools/call returns ToolResult(ok=True)."""
        raw_tools = [{"name": "greet", "description": "", "inputSchema": {}}]
        process = _mock_process([
            _make_tools_list_response(raw_tools, req_id=1),
            _make_call_response("Hello!", req_id=2),
        ])

        bridge = MCPBridge([_make_config()])
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            await bridge.start_servers()

        result = await bridge.call_tool("greet", {"name": "world"})
        assert result.ok is True
        assert "Hello!" in result.output

    @pytest.mark.asyncio
    async def test_error_response_returns_ok_false(self):
        """An error field in the JSON-RPC response yields ToolResult(ok=False)."""
        raw_tools = [{"name": "bad_tool", "description": "", "inputSchema": {}}]
        process = _mock_process([
            _make_tools_list_response(raw_tools, req_id=1),
            _make_error_response("Something went wrong", req_id=2),
        ])

        bridge = MCPBridge([_make_config()])
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            await bridge.start_servers()

        result = await bridge.call_tool("bad_tool", {})
        assert result.ok is False
        assert "Something went wrong" in result.output

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_ok_false(self):
        """Calling a tool that was never registered returns ToolResult(ok=False)."""
        bridge = MCPBridge([])
        result = await bridge.call_tool("nonexistent", {})
        assert result.ok is False
        assert "not available" in result.output

    @pytest.mark.asyncio
    async def test_unavailable_server_returns_ok_false(self):
        """Calling a tool whose server is marked unavailable returns ToolResult(ok=False)."""
        bridge = MCPBridge([_make_config()])
        # Manually inject a state with a tool but unavailable=False
        state = _ServerState(config=_make_config())
        state.tools = [ToolDefinition("my_tool", "", {}, "mutating", "test-server")]
        state.available = False
        bridge._servers["test-server"] = state

        result = await bridge.call_tool("my_tool", {})
        assert result.ok is False


# ---------------------------------------------------------------------------
# Unexpected-exit restart logic
# ---------------------------------------------------------------------------

class TestRestartLogic:
    """Tests for _restart_server() one-restart behaviour."""

    @pytest.mark.asyncio
    async def test_restart_succeeds_tools_available(self):
        """After a successful restart, tools become available again."""
        raw_tools = [{"name": "tool_x", "description": "", "inputSchema": {}}]
        # First launch (startup): tools/list response
        proc1 = _mock_process([_make_tools_list_response(raw_tools, req_id=1)])
        # Restart launch: tools/list response again
        proc2 = _mock_process([_make_tools_list_response(raw_tools, req_id=1)])

        bridge = MCPBridge([_make_config()])
        call_count = 0
        procs = [proc1, proc2]

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            p = procs[call_count]
            call_count += 1
            return p

        with patch("asyncio.create_subprocess_exec", fake_exec):
            await bridge.start_servers()
            # Simulate unexpected exit
            bridge._servers["test-server"].available = False
            bridge._servers["test-server"].process = None
            bridge._servers["test-server"].tools = []
            await bridge._restart_server("test-server")

        assert bridge._servers["test-server"].available is True
        assert len(bridge._servers["test-server"].tools) == 1

    @pytest.mark.asyncio
    async def test_restart_fails_tools_unavailable(self):
        """If restart fails, the server's tools remain unavailable."""
        raw_tools = [{"name": "tool_y", "description": "", "inputSchema": {}}]
        proc1 = _mock_process([_make_tools_list_response(raw_tools, req_id=1)])

        bridge = MCPBridge([_make_config()])
        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return proc1
            raise OSError("cannot restart")

        with patch("asyncio.create_subprocess_exec", fake_exec):
            await bridge.start_servers()
            bridge._servers["test-server"].available = False
            bridge._servers["test-server"].process = None
            bridge._servers["test-server"].tools = []
            await bridge._restart_server("test-server")

        assert bridge._servers["test-server"].available is False
        assert bridge.registered_tools() == []

    @pytest.mark.asyncio
    async def test_restart_unknown_server_is_noop(self):
        """Restarting a server name that doesn't exist does nothing."""
        bridge = MCPBridge([])
        # Should not raise
        await bridge._restart_server("ghost-server")


# ---------------------------------------------------------------------------
# Shutdown sequencing
# ---------------------------------------------------------------------------

class TestShutdownSequencing:
    """Tests for stop_servers() shutdown notification and termination."""

    @pytest.mark.asyncio
    async def test_shutdown_sends_notification_and_waits(self):
        """stop_servers sends a shutdown notification and waits for process exit."""
        raw_tools = [{"name": "t", "description": "", "inputSchema": {}}]
        process = _mock_process([_make_tools_list_response(raw_tools, req_id=1)])

        bridge = MCPBridge([_make_config()])
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            await bridge.start_servers()

        await bridge.stop_servers()

        # stdin.write should have been called at least twice:
        # once for tools/list and once for shutdown notification
        assert process.stdin.write.call_count >= 2

        # After shutdown, server should be marked unavailable
        assert bridge._servers["test-server"].available is False

    @pytest.mark.asyncio
    async def test_shutdown_kills_if_process_hangs(self):
        """If the process doesn't exit within 3 s, it is killed."""
        raw_tools = [{"name": "t", "description": "", "inputSchema": {}}]
        process = _mock_process([_make_tools_list_response(raw_tools, req_id=1)])

        # Override wait to simulate a hanging process
        async def hanging_wait():
            await asyncio.sleep(10)
            return 0

        process.wait = hanging_wait

        bridge = MCPBridge([_make_config()])
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            await bridge.start_servers()

        await bridge.stop_servers()

        process.kill.assert_called()

    @pytest.mark.asyncio
    async def test_stop_servers_no_servers_is_noop(self):
        """stop_servers with no configured servers completes without error."""
        bridge = MCPBridge([])
        await bridge.stop_servers()  # should not raise


# ---------------------------------------------------------------------------
# native_schemas.py tests
# ---------------------------------------------------------------------------

class TestNativeSchemas:
    """Tests for NATIVE_TOOL_SCHEMAS and get_native_schema()."""

    def test_all_nine_tools_present(self):
        from e_cli.mcp.native_schemas import NATIVE_TOOL_SCHEMAS
        expected = {"shell", "file.read", "file.write", "git.diff", "http.get",
                    "browser", "ssh", "curl", "rag.search"}
        assert set(NATIVE_TOOL_SCHEMAS.keys()) == expected

    def test_shell_is_mutating(self):
        from e_cli.mcp.native_schemas import NATIVE_TOOL_SCHEMAS
        assert NATIVE_TOOL_SCHEMAS["shell"]["safetyClass"] == "mutating"

    def test_file_read_is_read_only(self):
        from e_cli.mcp.native_schemas import NATIVE_TOOL_SCHEMAS
        assert NATIVE_TOOL_SCHEMAS["file.read"]["safetyClass"] == "read-only"

    def test_ssh_is_elevated(self):
        from e_cli.mcp.native_schemas import NATIVE_TOOL_SCHEMAS
        assert NATIVE_TOOL_SCHEMAS["ssh"]["safetyClass"] == "elevated"

    def test_get_native_schema_returns_dict_for_known_tool(self):
        from e_cli.mcp.native_schemas import get_native_schema
        schema = get_native_schema("shell")
        assert schema is not None
        assert "inputSchema" in schema
        assert "description" in schema

    def test_get_native_schema_returns_none_for_unknown_tool(self):
        from e_cli.mcp.native_schemas import get_native_schema
        assert get_native_schema("nonexistent_tool") is None

    def test_each_schema_has_required_keys(self):
        from e_cli.mcp.native_schemas import NATIVE_TOOL_SCHEMAS
        for name, schema in NATIVE_TOOL_SCHEMAS.items():
            assert "description" in schema, f"{name} missing description"
            assert "safetyClass" in schema, f"{name} missing safetyClass"
            assert "inputSchema" in schema, f"{name} missing inputSchema"

    def test_rag_search_schema_has_query_required(self):
        from e_cli.mcp.native_schemas import get_native_schema
        schema = get_native_schema("rag.search")
        assert schema is not None
        assert "query" in schema["inputSchema"]["required"]
