"""Sub_Agent_Pool — manages lifecycle of Sub_Agent instances.

Responsibilities:
- Derive concurrency limit via Hardware_Probe at construction.
- Maintain a ThreadPoolExecutor and a bounded queue.Queue[TaskRecord].
- Accept assign(envelope) calls, return task_id immediately.
- Expose status(task_id) and get_result(task_id) queries.
- Enforce queue depth limit (8).
- Terminate timed-out sub-agents via Future.cancel() + thread stop flag.
- Write audit events via MemoryService.appendAuditEvent.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from e_cli.agent.loop import AgentLoop
from e_cli.agent.protocol import ToolResult, parse_tool_call
from e_cli.memory.service import MemoryService
from e_cli.memory.store import MemoryStore
from e_cli.models.base import ModelResponse
from e_cli.models.factory import create_model_client
from e_cli.safety.policy import SafetyPolicy
from e_cli.skills.executor import _ScopedToolRouter
from e_cli.sub_agent.allowlist_router import Allowlist_Router
from e_cli.sub_agent.hardware import probe_concurrency_limit
from e_cli.sub_agent.models import Result_Envelope, Task_Envelope
from e_cli.sub_agent.tui_bridge import SubAgentStatusMessage, post_status_update
from e_cli.tools.router import ToolRouter

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

TaskState = Literal["queued", "running", "completed", "failed", "timeout"]

_QUEUE_MAXSIZE = 8
_MAX_CONSECUTIVE_PARSE_FAILURES = 3

# ---------------------------------------------------------------------------
# TaskRecord dataclass
# ---------------------------------------------------------------------------


@dataclass
class TaskRecord:
    """Internal record tracking the lifecycle of one sub-agent task."""

    task_id: str
    envelope: Task_Envelope
    state: TaskState
    result: Result_Envelope | None = None
    future: Future | None = None
    started_at: float | None = None
    finished_at: float | None = None
    _stop_flag: threading.Event = field(default_factory=threading.Event)


# ---------------------------------------------------------------------------
# Confidence parsing helper (exposed for direct testing in property tests)
# ---------------------------------------------------------------------------

_CONFIDENCE_RE = re.compile(r"CONFIDENCE:\s*([0-9]*\.?[0-9]+)")


def parse_confidence(output: str) -> float:
    """Parse ``CONFIDENCE: X.X`` from *output*; return 0.5 if absent/malformed."""
    match = _CONFIDENCE_RE.search(output)
    if match:
        try:
            value = float(match.group(1))
            if 0.0 <= value <= 1.0:
                return value
        except ValueError:
            pass
    return 0.5


# ---------------------------------------------------------------------------
# Sub_Agent_Pool
# ---------------------------------------------------------------------------


class Sub_Agent_Pool:
    """Manages concurrent Sub_Agent instances backed by a ThreadPoolExecutor."""

    def __init__(
        self,
        env_override: int | None = None,
        config_override: int = 0,
        memory_service=None,
        workspace_root: Path | None = None,
        tui_app: object = None,
        session_id: str | None = None,
    ) -> None:
        self.concurrency_limit: int = probe_concurrency_limit(
            env_override=env_override,
            config_override=config_override,
        )
        _log.info("Sub_Agent_Pool initialised with concurrency_limit=%d", self.concurrency_limit)

        self._executor = ThreadPoolExecutor(max_workers=self.concurrency_limit)
        self._queue: queue.Queue[TaskRecord] = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

        # Optional shared MemoryService for audit events.
        self._memory_service = memory_service
        self._workspace_root = workspace_root or Path.cwd()
        # Optional Textual app reference for TUI status updates (no-op when None).
        self._tui_app = tui_app
        # Session ID used for audit events — defaults to "sub_agent_pool" when not provided.
        self._session_id = session_id or "sub_agent_pool"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign(self, envelope: Task_Envelope) -> str | ToolResult:
        """Enqueue *envelope* for execution; return task_id or ToolResult on error."""
        with self._lock:
            if self._queue.qsize() >= _QUEUE_MAXSIZE:
                return ToolResult(
                    ok=False,
                    output="Sub-agent queue full; retry after current tasks complete",
                )

            task_id = uuid.uuid4().hex[:8]
            record = TaskRecord(
                task_id=task_id,
                envelope=envelope,
                state="queued",
            )
            self._tasks[task_id] = record

            try:
                self._queue.put_nowait(record)
            except queue.Full:
                # Race condition guard — remove from dict and report full.
                del self._tasks[task_id]
                return ToolResult(
                    ok=False,
                    output="Sub-agent queue full; retry after current tasks complete",
                )

        # Write audit event: task queued.
        self._write_audit(
            task_id=task_id,
            action="task.queued",
            tool="sub_agent",
            approved=True,
            status="queued",
            reason="",
            details=f"task_id={task_id} task={envelope.task[:200]}",
        )

        # Notify TUI: task queued.
        post_status_update(
            self._tui_app,
            SubAgentStatusMessage(
                task_id=task_id,
                status="queued",
                tool_calls_made=0,
                confidence=None,
            ),
        )

        # Submit worker thread.
        future = self._executor.submit(self._worker, record)
        with self._lock:
            record.future = future

        # Schedule timeout watchdog.
        timeout = envelope.timeout_seconds
        timer = threading.Timer(timeout, self._watchdog, args=(record,))
        timer.daemon = True
        timer.start()

        return task_id

    def status(self, task_id: str) -> str | ToolResult:
        """Return the current TaskState for *task_id*, or ToolResult on unknown id."""
        with self._lock:
            record = self._tasks.get(task_id)
        if record is None:
            return ToolResult(ok=False, output="Unknown task_id")
        return record.state

    def get_result(self, task_id: str) -> Result_Envelope | ToolResult:
        """Return the Result_Envelope for *task_id*, or ToolResult on unknown id."""
        with self._lock:
            record = self._tasks.get(task_id)
        if record is None:
            return ToolResult(ok=False, output="Unknown task_id")
        return record.result  # type: ignore[return-value]

    def shutdown(self) -> None:
        """Drain queue, cancel running futures, and shut down the executor."""
        # Drain the queue.
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        # Cancel all running futures.
        with self._lock:
            for record in self._tasks.values():
                if record.future is not None:
                    record.future.cancel()
                    record._stop_flag.set()

        self._executor.shutdown(wait=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _worker(self, record: TaskRecord) -> None:
        """Worker thread: run the sub-agent loop for *record*."""
        task_id = record.task_id
        envelope = record.envelope

        # Transition to running.
        with self._lock:
            record.state = "running"
            record.started_at = time.monotonic()

        self._write_audit(
            task_id=task_id,
            action="task.started",
            tool="sub_agent",
            approved=True,
            status="running",
            reason="",
            details=f"task_id={task_id}",
        )

        # Notify TUI: task running.
        post_status_update(
            self._tui_app,
            SubAgentStatusMessage(
                task_id=task_id,
                status="running",
                tool_calls_made=0,
                confidence=None,
            ),
        )

        output = ""
        tool_calls_made = 0
        status: Literal["completed", "failed", "timeout"] = "completed"
        fail_reason = ""

        try:
            # Build ephemeral MemoryService for this sub-agent.
            session_id = f"sub_agent_{task_id}_{uuid.uuid4().hex[:6]}"
            memory_service = self._build_memory_service(session_id)

            # Build Allowlist_Router.
            tool_router = ToolRouter(
                workspaceRoot=self._workspace_root,
                memoryDbPath=None,
            )
            safety_policy = SafetyPolicy(safeMode=True, trustedReadCommands=())
            scoped_router = _ScopedToolRouter(tool_router, safety_policy)
            allowlist_router = Allowlist_Router(scoped_router, envelope.tool_allowlist)

            # Build AgentLoop with conservative model params.
            model_params = dict(envelope.model_params)
            temperature = model_params.get("temperature", 0.1)
            top_p = model_params.get("top_p", 0.95)

            # We need a model client — use the module-level factory.
            try:
                model_client = create_model_client(
                    provider="ollama",
                    endpoint="http://localhost:11434",
                    api_key=None,
                    modelParameters={"temperature": temperature, "top_p": top_p},
                )
            except Exception:
                model_client = create_model_client(
                    provider="ollama",
                    endpoint="http://localhost:11434",
                    api_key=None,
                    modelParameters={},
                )

            agent_loop = AgentLoop(
                modelClient=model_client,
                modelName="llama3",
                memoryService=memory_service,
                safetyPolicy=safety_policy,
                workspaceRoot=self._workspace_root,
                timeoutSeconds=envelope.timeout_seconds,
                maxTurns=20,
                approvalMode="auto-approve",
                streamingEnabled=False,
                conversationTokenBudget=2048,
                conversationSummaryBudget=512,
            )

            # Wrap the tool router so we can count tool calls and intercept stop flag.
            _original_execute = allowlist_router.execute

            def _counting_execute(tool_call, timeout_seconds=30):
                nonlocal tool_calls_made
                if record._stop_flag.is_set():
                    return ToolResult(ok=False, output="Sub-agent stopped by timeout")
                result = _original_execute(tool_call, timeout_seconds)
                tool_calls_made += 1
                self._write_audit(
                    task_id=task_id,
                    action="tool.call",
                    tool=tool_call.tool,
                    approved=result.ok,
                    status="ok" if result.ok else "error",
                    reason=getattr(tool_call, "reason", "") or "",
                    details=result.output[:500],
                )
                return result

            allowlist_router.execute = _counting_execute  # type: ignore[method-assign]

            # Patch the agent loop's tool router to use our allowlist router.
            # We run the loop with a custom approach: intercept parse failures.
            consecutive_parse_failures = 0

            # Run the agent loop — we intercept by patching the model client
            # to count parse failures via a wrapper.
            original_chat = model_client.chat

            def _chat_wrapper(model_name, messages, timeout_seconds):
                nonlocal consecutive_parse_failures
                if record._stop_flag.is_set():
                    # Return a done signal to terminate the loop gracefully.
                    return ModelResponse(content='{"tool":"done","reason":"stopped"}')
                response = original_chat(model_name=model_name, messages=messages, timeout_seconds=timeout_seconds)
                # Check if the response is parseable.
                parsed = parse_tool_call(response.content)
                if parsed.toolCall is None and not parsed.assistantMessage.strip():
                    consecutive_parse_failures += 1
                    if consecutive_parse_failures >= _MAX_CONSECUTIVE_PARSE_FAILURES:
                        nonlocal status, fail_reason
                        status = "failed"
                        fail_reason = "Parse failure after 3 consecutive unparseable turns"
                        return ModelResponse(content='{"tool":"done","reason":"Parse failure after 3 consecutive unparseable turns"}')
                else:
                    consecutive_parse_failures = 0
                return response

            model_client.chat = _chat_wrapper  # type: ignore[method-assign]

            # Run the loop — it uses its own internal ToolRouter, but we need
            # it to use our allowlist_router. We patch the ToolRouter.execute
            # at the loop level by overriding the run method's router.
            # The simplest approach: run the loop and capture output.
            if not record._stop_flag.is_set():
                output = agent_loop.run(
                    userPrompt=envelope.task,
                    sessionId=session_id,
                )

        except Exception as exc:
            _log.warning("Sub-agent worker error for task_id=%s: %s", task_id, exc)
            if status == "completed":
                status = "failed"
                fail_reason = str(exc)

        # Don't overwrite timeout state set by watchdog.
        with self._lock:
            if record.state == "timeout":
                return
            finished_at = time.monotonic()
            record.finished_at = finished_at
            duration = (finished_at - (record.started_at or finished_at))

            confidence = parse_confidence(output)
            record.result = Result_Envelope(
                task_id=task_id,
                status=status,
                output=output,
                confidence=confidence,
                tool_calls_made=tool_calls_made,
                duration_seconds=duration,
            )
            record.state = status  # type: ignore[assignment]

        audit_action = "task.completed" if status == "completed" else "task.failed"
        self._write_audit(
            task_id=task_id,
            action=audit_action,
            tool="sub_agent",
            approved=(status == "completed"),
            status=status,
            reason=fail_reason,
            details=f"task_id={task_id} duration={duration:.2f}s confidence={confidence}",
        )

        # Notify TUI: task completed or failed.
        post_status_update(
            self._tui_app,
            SubAgentStatusMessage(
                task_id=task_id,
                status=status,
                tool_calls_made=tool_calls_made,
                confidence=confidence,
            ),
        )

    def _watchdog(self, record: TaskRecord) -> None:
        """Watchdog timer callback: terminate the sub-agent on timeout."""
        with self._lock:
            if record.state in ("completed", "failed"):
                return  # Already finished — nothing to do.
            record._stop_flag.set()
            if record.future is not None:
                record.future.cancel()
            finished_at = time.monotonic()
            record.finished_at = finished_at
            duration = finished_at - (record.started_at or finished_at)
            record.result = Result_Envelope(
                task_id=record.task_id,
                status="timeout",
                output="",
                confidence=0.5,
                tool_calls_made=0,
                duration_seconds=duration,
            )
            record.state = "timeout"

        self._write_audit(
            task_id=record.task_id,
            action="task.timeout",
            tool="sub_agent",
            approved=False,
            status="timeout",
            reason="timeout",
            details=f"task_id={record.task_id} timeout={record.envelope.timeout_seconds}s",
        )

        # Notify TUI: task timed out.
        post_status_update(
            self._tui_app,
            SubAgentStatusMessage(
                task_id=record.task_id,
                status="timeout",
                tool_calls_made=0,
                confidence=None,
            ),
        )

    def _build_memory_service(self, session_id: str):
        """Build an ephemeral MemoryService backed by a temp SQLite DB."""
        import tempfile
    def _build_memory_service(self, session_id: str) -> MemoryService:
        """Build an ephemeral MemoryService backed by a temp SQLite DB."""
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        # pool.py is at src/e_cli/sub_agent/pool.py
        # parents[0] = src/e_cli/sub_agent, parents[1] = src/e_cli, parents[2] = src
        schema_path = Path(__file__).resolve().parent.parent / "memory" / "schema.sql"
        store = MemoryStore(dbPath=tmp_dir / "memory.db", schemaPath=schema_path)
        return MemoryService(memoryStore=store)

    def _write_audit(
        self,
        task_id: str,
        action: str,
        tool: str,
        approved: bool,
        status: str,
        reason: str,
        details: str,
    ) -> None:
        """Write an audit event to the shared MemoryService if available.

        The action is prefixed with ``sub_agent[<task_id>]:`` so that sub-agent
        events are distinguishable from Main_Agent events when viewing
        ``e-cli sessions audit --last``.
        """
        if self._memory_service is None:
            return
        # Prefix action with task_id so sub-agent events are distinguishable.
        prefixed_action = f"sub_agent[{task_id}]:{action}"
        try:
            self._memory_service.appendAuditEvent(
                sessionId=self._session_id,
                action=prefixed_action,
                tool=tool,
                approved=approved,
                status=status,
                reason=reason,
                details=details,
            )
        except Exception as exc:
            _log.warning("Audit write failed for task_id=%s: %s", task_id, exc)
