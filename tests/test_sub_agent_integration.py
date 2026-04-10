"""Integration test for Sub_Agent_Pool with a mocked ModelClient.

Spawns a real Sub_Agent_Pool, assigns a read-only task, polls status() until
"completed", calls get_result(), and asserts all Result_Envelope fields are
present and valid.

**Validates: Requirements 11.5**
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from e_cli.memory.service import MemoryService
from e_cli.memory.store import MemoryStore
from e_cli.models.base import ModelResponse
from e_cli.sub_agent.models import Result_Envelope, Task_Envelope
from e_cli.sub_agent.pool import Sub_Agent_Pool

# ---------------------------------------------------------------------------
# Canned model client — returns a done response with CONFIDENCE: 0.9
# ---------------------------------------------------------------------------

_CANNED_RESPONSE = '{"tool":"done","reason":"Task complete. CONFIDENCE: 0.9"}'


class CannedModelClient:
    """Deterministic model client that always returns a canned done response."""

    provider_name = "canned"

    def chat(self, model_name: str, messages, timeout_seconds: int) -> ModelResponse:
        return ModelResponse(content=_CANNED_RESPONSE)

    def list_models(self, timeout_seconds: int) -> list[str]:
        return ["canned-model"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"


def _make_memory_service(tmp_path: Path) -> MemoryService:
    store = MemoryStore(dbPath=tmp_path / "memory.db", schemaPath=_SCHEMA_PATH)
    return MemoryService(memoryStore=store)


def _make_pool(tmp_path: Path) -> Sub_Agent_Pool:
    """Build a Sub_Agent_Pool with concurrency_limit=2 and a real MemoryService."""
    memory_service = _make_memory_service(tmp_path)
    with patch("e_cli.sub_agent.pool.probe_concurrency_limit", return_value=2):
        pool = Sub_Agent_Pool(
            memory_service=memory_service,
            workspace_root=tmp_path,
        )
    return pool


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


def test_integration_assign_poll_get_result(tmp_path: Path) -> None:
    """Integration test: spawn pool, assign read-only task, poll until completed,
    verify all Result_Envelope fields are present and valid.

    **Validates: Requirements 11.5**
    """
    canned_client = CannedModelClient()
    pool = _make_pool(tmp_path)

    def _make_sub_mem(session_id: str) -> MemoryService:
        store = MemoryStore(
            dbPath=tmp_path / f"sub_{session_id}.db",
            schemaPath=_SCHEMA_PATH,
        )
        return MemoryService(memoryStore=store)

    # Keep patches active for the entire duration of the test so the worker
    # thread (which runs asynchronously) sees the mocked create_model_client.
    with patch("e_cli.sub_agent.pool.create_model_client", return_value=canned_client), \
         patch.object(pool, "_build_memory_service", side_effect=_make_sub_mem):

        # Assign a read-only task with the default read-only tool allowlist.
        envelope = Task_Envelope(
            task="List the files in the current directory.",
            tool_allowlist=["file.read", "http.get", "rag.search", "git.diff"],
            timeout_seconds=30,
        )
        task_id = pool.assign(envelope)

        # assign() must return a non-empty string task_id immediately.
        assert isinstance(task_id, str), "assign() must return a string task_id"
        assert len(task_id) > 0, "task_id must be non-empty"

        # Poll status() until "completed" (or timeout after 10 s).
        deadline = time.monotonic() + 10.0
        state = None
        while time.monotonic() < deadline:
            state = pool.status(task_id)
            if state == "completed":
                break
            time.sleep(0.05)

    assert state == "completed", f"Expected 'completed' but got {state!r} after polling"

    # Retrieve the result.
    result = pool.get_result(task_id)

    # Must be a Result_Envelope, not a ToolResult error.
    assert isinstance(result, Result_Envelope), (
        f"get_result() must return a Result_Envelope, got {type(result)}"
    )

    # --- Assert all required fields are present and valid ---

    # task_id: non-empty string matching the assigned task_id.
    assert isinstance(result.task_id, str) and len(result.task_id) > 0, \
        "Result_Envelope.task_id must be a non-empty string"
    assert result.task_id == task_id, \
        f"Result_Envelope.task_id {result.task_id!r} must match assigned task_id {task_id!r}"

    # status: must be "completed".
    assert result.status == "completed", \
        f"Result_Envelope.status must be 'completed', got {result.status!r}"

    # output: must be a string (may be empty if the loop returned nothing).
    assert isinstance(result.output, str), \
        "Result_Envelope.output must be a string"

    # confidence: parsed from "CONFIDENCE: 0.9" in the canned response → 0.9.
    assert isinstance(result.confidence, float), \
        "Result_Envelope.confidence must be a float"
    assert 0.0 <= result.confidence <= 1.0, \
        f"Result_Envelope.confidence must be in [0.0, 1.0], got {result.confidence}"
    assert result.confidence == pytest.approx(0.9, abs=1e-6), \
        f"Expected confidence 0.9 (from canned response), got {result.confidence}"

    # tool_calls_made: non-negative integer.
    assert isinstance(result.tool_calls_made, int), \
        "Result_Envelope.tool_calls_made must be an int"
    assert result.tool_calls_made >= 0, \
        "Result_Envelope.tool_calls_made must be >= 0"

    # duration_seconds: non-negative float.
    assert isinstance(result.duration_seconds, float), \
        "Result_Envelope.duration_seconds must be a float"
    assert result.duration_seconds >= 0.0, \
        "Result_Envelope.duration_seconds must be >= 0.0"

    pool.shutdown()
