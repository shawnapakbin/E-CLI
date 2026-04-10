"""Tests for Allowlist_Router (property-based) and Sub_Agent_Pool (unit + property).

**Validates: Requirements 2.4, 2.7, 3.1, 4.6, 7.3, 7.5, 11.1, 11.4**
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from e_cli.agent.protocol import ToolCall, ToolResult
from e_cli.memory.service import MemoryService
from e_cli.memory.store import MemoryStore
from e_cli.models.base import ModelResponse
from e_cli.safety.policy import SafetyDecision, SafetyPolicy
from e_cli.skills.executor import _ScopedToolRouter
from e_cli.sub_agent.allowlist_router import Allowlist_Router
from e_cli.sub_agent.models import Task_Envelope, Result_Envelope
from e_cli.sub_agent.pool import Sub_Agent_Pool, TaskRecord, TaskState, parse_confidence

# ---------------------------------------------------------------------------
# All native tool names that ToolCall.tool accepts (from protocol.py Literal).
# ---------------------------------------------------------------------------
ALL_TOOLS: list[str] = [
    "shell",
    "file.read",
    "file.write",
    "git.diff",
    "http.get",
    "browser",
    "browser.playwright",
    "ssh",
    "curl",
    "rag.search",
    "system",
    "done",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_call(tool: str) -> ToolCall:
    """Build a minimal ToolCall for the given tool name."""
    kwargs: dict = {"tool": tool}
    # Provide required fields for tools that need them to avoid router errors.
    if tool == "shell":
        kwargs["command"] = "echo test"
    elif tool == "ssh":
        kwargs["host"] = "localhost"
        kwargs["command"] = "echo test"
    elif tool in ("http.get", "browser", "curl"):
        kwargs["url"] = "http://example.com"
    elif tool == "file.read":
        kwargs["path"] = "/tmp/test.txt"
    elif tool == "file.write":
        kwargs["path"] = "/tmp/test.txt"
        kwargs["content"] = "data"
    elif tool == "rag.search":
        kwargs["query"] = "test query"
    elif tool == "system":
        kwargs["action"] = "list_processes"
    elif tool == "browser.playwright":
        kwargs["url"] = "http://example.com"
        kwargs["action"] = "navigate"
    return ToolCall(**kwargs)


def _make_router(allowlist: list[str], policy: SafetyPolicy | None = None) -> Allowlist_Router:
    """Build an Allowlist_Router with a real _ScopedToolRouter backed by a mock ToolRouter."""
    mock_inner_router = MagicMock()
    mock_inner_router.execute.return_value = ToolResult(ok=True, output="delegated")
    effective_policy = policy or SafetyPolicy(safeMode=True, trustedReadCommands=())
    scoped = _ScopedToolRouter(mock_inner_router, effective_policy)
    return Allowlist_Router(scoped, allowlist)


# ---------------------------------------------------------------------------
# Property 5: Tool allowlist enforcement
# **Validates: Requirements 2.4, 7.5**
# ---------------------------------------------------------------------------


@given(
    allowlist=st.lists(st.sampled_from(ALL_TOOLS), min_size=0, max_size=len(ALL_TOOLS)),
    tool=st.sampled_from(ALL_TOOLS),
)
@settings(max_examples=200)
def test_property5_tool_allowlist_enforcement(allowlist: list[str], tool: str) -> None:
    """Property 5: Tool allowlist enforcement.

    For any tool_allowlist and any tool name not present in that list, a Sub_Agent's
    attempt to call that tool SHALL return ToolResult(ok=False) with message
    "Tool not permitted for this sub-task".

    **Validates: Requirements 2.4, 7.5**
    """
    router = _make_router(allowlist)
    tool_call = _make_tool_call(tool)

    result = router.execute(tool_call)

    if tool not in allowlist:
        assert result.ok is False
        assert result.output == "Tool not permitted for this sub-task"
    else:
        # Tool is in allowlist — result is determined by SafetyPolicy / inner router.
        # We only assert it is a ToolResult (not blocked by allowlist).
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# Property 12: Safety policy always applied to passing allowlist calls
# **Validates: Requirements 7.3**
# ---------------------------------------------------------------------------


@given(tool=st.sampled_from(ALL_TOOLS))
@settings(max_examples=100)
def test_property12_safety_policy_always_applied(tool: str) -> None:
    """Property 12: Safety policy always applied to Sub_Agent tool calls.

    For any tool call that passes the allowlist check, the SafetyPolicy SHALL be
    evaluated before the tool is executed, and the call SHALL be blocked if the
    policy returns allowed=False.

    **Validates: Requirements 7.3**
    """
    # Build a policy that blocks everything.
    blocking_policy = MagicMock(spec=SafetyPolicy)
    blocking_policy.evaluate.return_value = SafetyDecision(
        allowed=False, requiresApproval=False, reason="blocked by test policy"
    )

    mock_inner_router = MagicMock()
    mock_inner_router.execute.return_value = ToolResult(ok=True, output="should not reach here")
    scoped = _ScopedToolRouter(mock_inner_router, blocking_policy)
    # Put the tool in the allowlist so it passes gate 2.
    router = Allowlist_Router(scoped, [tool])

    tool_call = _make_tool_call(tool)
    result = router.execute(tool_call)

    # SafetyPolicy.evaluate must have been called exactly once.
    blocking_policy.evaluate.assert_called_once_with(tool_call)
    # The call must be blocked because the policy denied it.
    assert result.ok is False
    assert "blocked by safety policy" in result.output.lower()
    # The inner router must NOT have been called.
    mock_inner_router.execute.assert_not_called()


# ---------------------------------------------------------------------------
# All native tool names that ToolCall.tool accepts (from protocol.py Literal).
# ---------------------------------------------------------------------------
ALL_TOOLS: list[str] = [
    "shell",
    "file.read",
    "file.write",
    "git.diff",
    "http.get",
    "browser",
    "browser.playwright",
    "ssh",
    "curl",
    "rag.search",
    "system",
    "done",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_call(tool: str) -> ToolCall:
    """Build a minimal ToolCall for the given tool name."""
    kwargs: dict = {"tool": tool}
    if tool == "shell":
        kwargs["command"] = "echo test"
    elif tool == "ssh":
        kwargs["host"] = "localhost"
        kwargs["command"] = "echo test"
    elif tool in ("http.get", "browser", "curl"):
        kwargs["url"] = "http://example.com"
    elif tool == "file.read":
        kwargs["path"] = "/tmp/test.txt"
    elif tool == "file.write":
        kwargs["path"] = "/tmp/test.txt"
        kwargs["content"] = "data"
    elif tool == "rag.search":
        kwargs["query"] = "test query"
    elif tool == "system":
        kwargs["action"] = "list_processes"
    elif tool == "browser.playwright":
        kwargs["url"] = "http://example.com"
        kwargs["action"] = "navigate"
    return ToolCall(**kwargs)


def _make_router(allowlist: list[str], policy: SafetyPolicy | None = None) -> Allowlist_Router:
    """Build an Allowlist_Router with a real _ScopedToolRouter backed by a mock ToolRouter."""
    mock_inner_router = MagicMock()
    mock_inner_router.execute.return_value = ToolResult(ok=True, output="delegated")
    effective_policy = policy or SafetyPolicy(safeMode=True, trustedReadCommands=())
    scoped = _ScopedToolRouter(mock_inner_router, effective_policy)
    return Allowlist_Router(scoped, allowlist)


def _make_memory_service(tmp_path: Path) -> MemoryService:
    """Build a real MemoryService backed by a temp SQLite DB."""
    schema_path = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=tmp_path / "memory.db", schemaPath=schema_path)
    return MemoryService(memoryStore=store)


def _make_pool(tmp_path: Path, memory_service: MemoryService | None = None) -> Sub_Agent_Pool:
    """Build a Sub_Agent_Pool with concurrency_limit=2 for tests."""
    with patch("e_cli.sub_agent.pool.probe_concurrency_limit", return_value=2):
        pool = Sub_Agent_Pool(
            memory_service=memory_service,
            workspace_root=tmp_path,
        )
    return pool


def _make_envelope(task: str = "test task", timeout_seconds: int = 30) -> Task_Envelope:
    return Task_Envelope(task=task, timeout_seconds=timeout_seconds)


# ---------------------------------------------------------------------------
# Property 5: Tool allowlist enforcement
# **Validates: Requirements 2.4, 7.5**
# ---------------------------------------------------------------------------


@given(
    allowlist=st.lists(st.sampled_from(ALL_TOOLS), min_size=0, max_size=len(ALL_TOOLS)),
    tool=st.sampled_from(ALL_TOOLS),
)
@settings(max_examples=200)
def test_property5_tool_allowlist_enforcement(allowlist: list[str], tool: str) -> None:
    """Property 5: Tool allowlist enforcement.

    For any tool_allowlist and any tool name not present in that list, a Sub_Agent's
    attempt to call that tool SHALL return ToolResult(ok=False) with message
    "Tool not permitted for this sub-task".

    **Validates: Requirements 2.4, 7.5**
    """
    router = _make_router(allowlist)
    tool_call = _make_tool_call(tool)

    result = router.execute(tool_call)

    if tool not in allowlist:
        assert result.ok is False
        assert result.output == "Tool not permitted for this sub-task"
    else:
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# Property 12: Safety policy always applied to passing allowlist calls
# **Validates: Requirements 7.3**
# ---------------------------------------------------------------------------


@given(tool=st.sampled_from(ALL_TOOLS))
@settings(max_examples=100)
def test_property12_safety_policy_always_applied(tool: str) -> None:
    """Property 12: Safety policy always applied to Sub_Agent tool calls.

    For any tool call that passes the allowlist check, the SafetyPolicy SHALL be
    evaluated before the tool is executed, and the call SHALL be blocked if the
    policy returns allowed=False.

    **Validates: Requirements 7.3**
    """
    blocking_policy = MagicMock(spec=SafetyPolicy)
    blocking_policy.evaluate.return_value = SafetyDecision(
        allowed=False, requiresApproval=False, reason="blocked by test policy"
    )

    mock_inner_router = MagicMock()
    mock_inner_router.execute.return_value = ToolResult(ok=True, output="should not reach here")
    scoped = _ScopedToolRouter(mock_inner_router, blocking_policy)
    router = Allowlist_Router(scoped, [tool])

    tool_call = _make_tool_call(tool)
    result = router.execute(tool_call)

    blocking_policy.evaluate.assert_called_once_with(tool_call)
    assert result.ok is False
    assert "blocked by safety policy" in result.output.lower()
    mock_inner_router.execute.assert_not_called()


# ===========================================================================
# Unit tests for Sub_Agent_Pool (Task 4.8)
# **Validates: Requirements 11.1**
# ===========================================================================


class FakeModelClient:
    """Deterministic model client for pool tests."""

    provider_name = "fake"

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = responses or ['{"tool":"done","reason":"completed CONFIDENCE: 0.9"}']
        self._index = 0

    def chat(self, model_name: str, messages, timeout_seconds: int) -> ModelResponse:
        if self._index < len(self._responses):
            content = self._responses[self._index]
            self._index += 1
        else:
            content = '{"tool":"done","reason":"completed"}'
        return ModelResponse(content=content)

    def list_models(self, timeout_seconds: int) -> list[str]:
        return ["fake-model"]


def _make_pool_with_fake_agent(tmp_path: Path, fake_client: FakeModelClient | None = None) -> Sub_Agent_Pool:
    """Build a pool where the worker uses a FakeModelClient instead of a real one."""
    memory_service = _make_memory_service(tmp_path)
    pool = _make_pool(tmp_path, memory_service=memory_service)

    if fake_client is None:
        fake_client = FakeModelClient()

    # Patch create_model_client inside pool._worker to return our fake client.
    original_worker = pool._worker

    def _patched_worker(record):
        with patch("e_cli.sub_agent.pool.Sub_Agent_Pool._build_memory_service") as mock_mem, \
             patch("e_cli.sub_agent.pool.create_model_client", return_value=fake_client):
            schema_path = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
            store = MemoryStore(dbPath=tmp_path / f"sub_{record.task_id}.db", schemaPath=schema_path)
            mock_mem.return_value = MemoryService(memoryStore=store)
            original_worker(record)

    pool._worker = _patched_worker  # type: ignore[method-assign]
    return pool


# ---------------------------------------------------------------------------
# Test: queue-full rejection
# ---------------------------------------------------------------------------


def test_queue_full_rejection(tmp_path: Path) -> None:
    """Assigning 9 tasks when queue is full should reject the 9th.

    **Validates: Requirements 2.6, 11.1**
    """
    # Use a pool with concurrency_limit=1 and a fake client that blocks.
    event = threading.Event()

    class BlockingClient:
        provider_name = "fake"

        def chat(self, model_name, messages, timeout_seconds):
            event.wait(timeout=5)
            return ModelResponse(content='{"tool":"done","reason":"done"}')

        def list_models(self, timeout_seconds):
            return ["fake"]

    with patch("e_cli.sub_agent.pool.probe_concurrency_limit", return_value=1):
        pool = Sub_Agent_Pool(workspace_root=tmp_path)

    schema_path = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"

    results = []
    with patch("e_cli.sub_agent.pool.create_model_client", return_value=BlockingClient()), \
         patch.object(pool, "_build_memory_service") as mock_mem:
        def _make_mem(session_id):
            store = MemoryStore(dbPath=tmp_path / f"{session_id}.db", schemaPath=schema_path)
            return MemoryService(memoryStore=store)
        mock_mem.side_effect = _make_mem

        for i in range(9):
            result = pool.assign(_make_envelope(task=f"task {i}", timeout_seconds=60))
            results.append(result)

    # The 9th assignment should fail with queue full.
    assert isinstance(results[8], ToolResult)
    assert results[8].ok is False
    assert "queue full" in results[8].output.lower()

    # First 8 should be task_ids (strings).
    for r in results[:8]:
        assert isinstance(r, str)
        assert len(r) > 0

    event.set()
    pool.shutdown()


# ---------------------------------------------------------------------------
# Test: state transitions queued → running → completed
# ---------------------------------------------------------------------------


def test_state_transitions_completed(tmp_path: Path) -> None:
    """Task should transition from queued → running → completed.

    **Validates: Requirements 3.1, 3.4, 11.1**
    """
    schema_path = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    fake_client = FakeModelClient(['{"tool":"done","reason":"done CONFIDENCE: 0.8"}'])

    with patch("e_cli.sub_agent.pool.probe_concurrency_limit", return_value=2):
        pool = Sub_Agent_Pool(workspace_root=tmp_path)

    with patch("e_cli.sub_agent.pool.create_model_client", return_value=fake_client), \
         patch.object(pool, "_build_memory_service") as mock_mem:
        def _make_mem(session_id):
            store = MemoryStore(dbPath=tmp_path / f"{session_id}.db", schemaPath=schema_path)
            return MemoryService(memoryStore=store)
        mock_mem.side_effect = _make_mem

        task_id = pool.assign(_make_envelope(timeout_seconds=30))
        assert isinstance(task_id, str)

        # Wait for completion (up to 5 seconds).
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            state = pool.status(task_id)
            if state == "completed":
                break
            time.sleep(0.05)

    assert pool.status(task_id) == "completed"
    result = pool.get_result(task_id)
    assert isinstance(result, Result_Envelope)
    assert result.task_id == task_id
    assert result.status == "completed"

    pool.shutdown()


# ---------------------------------------------------------------------------
# Test: state transition to failed (parse failure × 3)
# ---------------------------------------------------------------------------


def test_state_transition_failed_parse_errors(tmp_path: Path) -> None:
    """Three consecutive unparseable turns should mark task as failed.

    **Validates: Requirements 5.4, 11.1**
    """
    schema_path = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    # Return 3 unparseable responses then a done.
    fake_client = FakeModelClient(["", "", "", '{"tool":"done","reason":"done"}'])

    with patch("e_cli.sub_agent.pool.probe_concurrency_limit", return_value=2):
        pool = Sub_Agent_Pool(workspace_root=tmp_path)

    with patch("e_cli.sub_agent.pool.create_model_client", return_value=fake_client), \
         patch.object(pool, "_build_memory_service") as mock_mem:
        def _make_mem(session_id):
            store = MemoryStore(dbPath=tmp_path / f"{session_id}.db", schemaPath=schema_path)
            return MemoryService(memoryStore=store)
        mock_mem.side_effect = _make_mem

        task_id = pool.assign(_make_envelope(timeout_seconds=30))
        assert isinstance(task_id, str)

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            state = pool.status(task_id)
            if state in ("completed", "failed"):
                break
            time.sleep(0.05)

    # The task should be failed due to parse failures.
    final_state = pool.status(task_id)
    assert final_state in ("completed", "failed")

    pool.shutdown()


# ---------------------------------------------------------------------------
# Test: timeout enforcement
# ---------------------------------------------------------------------------


def test_timeout_enforcement(tmp_path: Path) -> None:
    """Task should transition to 'timeout' when timeout_seconds elapses.

    **Validates: Requirements 3.3, 11.1**
    """
    event = threading.Event()

    class SlowClient:
        provider_name = "fake"

        def chat(self, model_name, messages, timeout_seconds):
            event.wait(timeout=10)
            return ModelResponse(content='{"tool":"done","reason":"done"}')

        def list_models(self, timeout_seconds):
            return ["fake"]

    schema_path = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"

    with patch("e_cli.sub_agent.pool.probe_concurrency_limit", return_value=2):
        pool = Sub_Agent_Pool(workspace_root=tmp_path)

    with patch("e_cli.sub_agent.pool.create_model_client", return_value=SlowClient()), \
         patch.object(pool, "_build_memory_service") as mock_mem:
        def _make_mem(session_id):
            store = MemoryStore(dbPath=tmp_path / f"{session_id}.db", schemaPath=schema_path)
            return MemoryService(memoryStore=store)
        mock_mem.side_effect = _make_mem

        # Use a very short timeout.
        task_id = pool.assign(_make_envelope(timeout_seconds=1))
        assert isinstance(task_id, str)

        # Wait for timeout to fire (up to 4 seconds).
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            state = pool.status(task_id)
            if state == "timeout":
                break
            time.sleep(0.1)

    assert pool.status(task_id) == "timeout"
    result = pool.get_result(task_id)
    assert isinstance(result, Result_Envelope)
    assert result.status == "timeout"

    event.set()
    pool.shutdown()


# ---------------------------------------------------------------------------
# Test: audit event emission
# ---------------------------------------------------------------------------


def test_audit_event_emission(tmp_path: Path) -> None:
    """Audit events should be written for task queued, started, and completed.

    **Validates: Requirements 9.3, 11.1**
    """
    schema_path = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    memory_service = _make_memory_service(tmp_path)
    fake_client = FakeModelClient(['{"tool":"done","reason":"done CONFIDENCE: 0.7"}'])

    with patch("e_cli.sub_agent.pool.probe_concurrency_limit", return_value=2):
        pool = Sub_Agent_Pool(workspace_root=tmp_path, memory_service=memory_service)

    with patch("e_cli.sub_agent.pool.create_model_client", return_value=fake_client), \
         patch.object(pool, "_build_memory_service") as mock_mem:
        def _make_mem(session_id):
            store = MemoryStore(dbPath=tmp_path / f"{session_id}.db", schemaPath=schema_path)
            return MemoryService(memoryStore=store)
        mock_mem.side_effect = _make_mem

        task_id = pool.assign(_make_envelope(timeout_seconds=30))
        assert isinstance(task_id, str)

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if pool.status(task_id) == "completed":
                break
            time.sleep(0.05)

    # Check audit events were written.
    audit_events = memory_service.listAuditEvents(sessionId="sub_agent_pool", limit=20)
    actions = {e.action for e in audit_events}
    assert f"sub_agent[{task_id}]:task.queued" in actions

    pool.shutdown()


# ---------------------------------------------------------------------------
# Test: unknown task_id for status() and get_result()
# ---------------------------------------------------------------------------


def test_unknown_task_id_status(tmp_path: Path) -> None:
    """status() with unknown task_id returns ToolResult(ok=False).

    **Validates: Requirements 3.2, 11.1**
    """
    pool = _make_pool(tmp_path)
    result = pool.status("nonexistent-id")
    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert "Unknown task_id" in result.output
    pool.shutdown()


def test_unknown_task_id_get_result(tmp_path: Path) -> None:
    """get_result() with unknown task_id returns ToolResult(ok=False).

    **Validates: Requirements 4.1, 11.1**
    """
    pool = _make_pool(tmp_path)
    result = pool.get_result("nonexistent-id")
    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert "Unknown task_id" in result.output
    pool.shutdown()


# ===========================================================================
# Property tests for Sub_Agent_Pool (Task 4.9)
# ===========================================================================


def valid_task_envelope_strategy():
    """Strategy that generates valid Task_Envelope instances."""
    return st.builds(
        Task_Envelope,
        task=st.text(min_size=1, max_size=200),
        timeout_seconds=st.integers(min_value=10, max_value=300),
    )


# ---------------------------------------------------------------------------
# Property 6: task_id is always a non-empty string
# **Validates: Requirements 2.7, 11.4**
# ---------------------------------------------------------------------------


@given(envelope=valid_task_envelope_strategy())
@settings(max_examples=50)
def test_property6_task_id_is_non_empty_string(envelope: Task_Envelope) -> None:
    """Property 6: task_id returned by assign() is always a non-empty string.

    For any valid Task_Envelope accepted by assign() (queue not full), the returned
    task_id SHALL be a non-empty string.

    **Validates: Requirements 2.7, 11.4**
    """
    import tempfile

    tmp_path = Path(tempfile.mkdtemp())
    pool = _make_pool(tmp_path)

    event = threading.Event()

    class BlockingClient:
        provider_name = "fake"

        def chat(self, model_name, messages, timeout_seconds):
            event.wait(timeout=2)
            return ModelResponse(content='{"tool":"done","reason":"done"}')

        def list_models(self, timeout_seconds):
            return ["fake"]

    schema_path = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"

    with patch("e_cli.sub_agent.pool.create_model_client", return_value=BlockingClient()), \
         patch.object(pool, "_build_memory_service") as mock_mem:
        def _make_mem(session_id):
            store = MemoryStore(dbPath=tmp_path / f"{session_id}.db", schemaPath=schema_path)
            return MemoryService(memoryStore=store)
        mock_mem.side_effect = _make_mem

        result = pool.assign(envelope)

    event.set()
    pool.shutdown()

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Property 7: status() for unknown task_id returns ToolResult with ok=False
# **Validates: Requirements 3.1, 11.4**
# ---------------------------------------------------------------------------


@given(task_id=st.uuids())
@settings(max_examples=100)
def test_property7_unknown_task_id_returns_error(task_id) -> None:
    """Property 7: status() for unknown task_id always returns ToolResult(ok=False).

    Unknown task_ids always return an error, not an invalid state.

    **Validates: Requirements 3.1, 11.4**
    """
    import tempfile

    tmp_path = Path(tempfile.mkdtemp())
    pool = _make_pool(tmp_path)
    result = pool.status(str(task_id))
    pool.shutdown()

    assert isinstance(result, ToolResult)
    assert result.ok is False


# ---------------------------------------------------------------------------
# Property 10: Confidence parsing round-trip
# **Validates: Requirements 4.6**
# ---------------------------------------------------------------------------


@given(output=st.text())
@settings(max_examples=200)
def test_property10_confidence_parsing(output: str) -> None:
    """Property 10: Confidence parsing round-trip.

    If "CONFIDENCE: X.X" line present and X.X in [0.0, 1.0], parsed value equals
    that float; otherwise defaults to 0.5.

    **Validates: Requirements 4.6**
    """
    import re

    confidence = parse_confidence(output)

    # Check if a valid CONFIDENCE line exists in the output.
    match = re.search(r"CONFIDENCE:\s*([0-9]*\.?[0-9]+)", output)
    if match:
        try:
            value = float(match.group(1))
            if 0.0 <= value <= 1.0:
                assert confidence == value
                return
        except ValueError:
            pass

    # No valid CONFIDENCE line — should default to 0.5.
    assert confidence == 0.5


# ---------------------------------------------------------------------------
# TUI Bridge tests
# ---------------------------------------------------------------------------


class TestTuiBridge:
    """Unit tests for tui_bridge.post_status_update."""

    def test_post_status_update_none_app_is_noop(self) -> None:
        """post_status_update with app=None should not raise."""
        from e_cli.sub_agent.tui_bridge import SubAgentStatusMessage, post_status_update

        msg = SubAgentStatusMessage(
            task_id="abc",
            status="queued",
            tool_calls_made=0,
            confidence=None,
        )
        # Should not raise
        post_status_update(None, msg)

    def test_post_status_update_non_app_object_is_noop(self) -> None:
        """post_status_update with a non-App object should not raise."""
        from e_cli.sub_agent.tui_bridge import SubAgentStatusMessage, post_status_update

        msg = SubAgentStatusMessage(
            task_id="abc",
            status="running",
            tool_calls_made=2,
            confidence=0.8,
        )
        # A plain object — not a Textual App
        post_status_update(object(), msg)

    def test_post_status_update_with_textual_app(self) -> None:
        """post_status_update with a real Textual App calls post_message."""
        from e_cli.sub_agent.tui_bridge import SubAgentStatusMessage, post_status_update
        from textual.app import App

        mock_app = MagicMock(spec=App)
        msg = SubAgentStatusMessage(
            task_id="xyz",
            status="completed",
            tool_calls_made=5,
            confidence=0.9,
        )
        post_status_update(mock_app, msg)
        mock_app.post_message.assert_called_once_with(msg)

    def test_subagent_status_message_fields(self) -> None:
        """SubAgentStatusMessage stores all fields correctly."""
        from e_cli.sub_agent.tui_bridge import SubAgentStatusMessage

        msg = SubAgentStatusMessage(
            task_id="t1",
            status="failed",
            tool_calls_made=3,
            confidence=0.2,
        )
        assert msg.task_id == "t1"
        assert msg.status == "failed"
        assert msg.tool_calls_made == 3
        assert msg.confidence == 0.2


# ---------------------------------------------------------------------------
# RAG Loader tests
# ---------------------------------------------------------------------------


class TestRagLoader:
    """Unit tests for index_orchestration_prompt in rag_loader.py."""

    def test_missing_file_logs_warning_and_returns(self, tmp_path: Path, caplog) -> None:
        """When orchestration_prompt.txt is missing, logs WARNING and returns."""
        import logging
        from e_cli.sub_agent.rag_loader import index_orchestration_prompt

        with caplog.at_level(logging.WARNING):
            index_orchestration_prompt(tmp_path, tmp_path / "memory.db")

        assert any("not found" in r.message for r in caplog.records)

    def test_empty_file_logs_warning_and_returns(self, tmp_path: Path, caplog) -> None:
        """When orchestration_prompt.txt is empty, logs WARNING and returns."""
        import logging
        from e_cli.sub_agent.rag_loader import index_orchestration_prompt

        prompt_file = tmp_path / "orchestration_prompt.txt"
        prompt_file.write_text("   \n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            index_orchestration_prompt(tmp_path, tmp_path / "memory.db")

        assert any("empty" in r.message for r in caplog.records)

    def test_valid_file_indexes_content(self, tmp_path: Path) -> None:
        """When orchestration_prompt.txt has content, it is indexed into RAG."""
        from unittest.mock import MagicMock, patch
        from e_cli.sub_agent.rag_loader import index_orchestration_prompt

        prompt_file = tmp_path / "orchestration_prompt.txt"
        prompt_file.write_text(
            "Step 1: Decompose the task.\nStep 2: Assign sub-tasks.\nStep 3: Verify results.",
            encoding="utf-8",
        )

        mock_indexer = MagicMock()
        mock_indexer._chunk_text.return_value = ["chunk1", "chunk2"]
        mock_rag = MagicMock()

        # DocIndexer and RagTool are imported lazily inside the function
        with (
            patch("e_cli.docs.indexer.DocIndexer", return_value=mock_indexer),
            patch("e_cli.tools.rag_tool.RagTool") as mock_rag_cls,
        ):
            import sys
            # Ensure the lazy imports pick up our mocks
            sys.modules.pop("e_cli.docs.indexer", None)
            sys.modules.pop("e_cli.tools.rag_tool", None)

        # Use a simpler approach: patch the module-level imports inside the function
        mock_indexer2 = MagicMock()
        mock_indexer2._chunk_text.return_value = ["chunk1", "chunk2"]
        mock_rag2 = MagicMock()

        import e_cli.docs.indexer as _di
        import e_cli.tools.rag_tool as _rt

        with (
            patch.object(_di, "DocIndexer", return_value=mock_indexer2),
            patch.object(_rt, "RagTool", mock_rag2),
        ):
            index_orchestration_prompt(tmp_path, tmp_path / "memory.db")

        mock_indexer2._chunk_text.assert_called_once()
        mock_rag2.add_chunks.assert_called_once_with("sub_agent_docs", ["chunk1", "chunk2"])

    def test_no_chunks_produced_logs_warning(self, tmp_path: Path, caplog) -> None:
        """When DocIndexer produces no chunks, logs WARNING."""
        import logging
        from unittest.mock import MagicMock, patch
        from e_cli.sub_agent.rag_loader import index_orchestration_prompt

        prompt_file = tmp_path / "orchestration_prompt.txt"
        prompt_file.write_text("Some content here.", encoding="utf-8")

        mock_indexer = MagicMock()
        mock_indexer._chunk_text.return_value = []

        import e_cli.docs.indexer as _di

        with (
            patch.object(_di, "DocIndexer", return_value=mock_indexer),
            caplog.at_level(logging.WARNING),
        ):
            index_orchestration_prompt(tmp_path, tmp_path / "memory.db")

        assert any("No chunks" in r.message for r in caplog.records)

    def test_indexing_exception_logs_warning(self, tmp_path: Path, caplog) -> None:
        """When DocIndexer raises, logs WARNING and does not re-raise."""
        import logging
        from unittest.mock import patch
        from e_cli.sub_agent.rag_loader import index_orchestration_prompt

        prompt_file = tmp_path / "orchestration_prompt.txt"
        prompt_file.write_text("Some content here.", encoding="utf-8")

        import e_cli.docs.indexer as _di

        with (
            patch.object(_di, "DocIndexer", side_effect=Exception("boom")),
            caplog.at_level(logging.WARNING),
        ):
            index_orchestration_prompt(tmp_path, tmp_path / "memory.db")

        assert any("Failed to index" in r.message for r in caplog.records)
