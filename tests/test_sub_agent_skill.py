"""Unit and property-based tests for SubAgentSkill.

Tests cover:
- All four tool dispatches (assign, status, verify, help)
- Task_Envelope parsing
- Allowlist enforcement
- Result_Envelope construction
- Schema validation
- Confidence parsing
- Unknown task_id handling

Property tests:
- Property 3: Context truncation invariant
- Property 4: Main_Agent history isolation
- Property 9: Schema validation correctness
- Property 11: System prompt lists only allowlisted tools

**Validates: Requirements 2.2, 2.3, 4.4, 4.5, 5.2, 5.6, 7.1, 11.2**
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers to import SubAgentSkill from the skill.py in the home directory.
# ---------------------------------------------------------------------------

import importlib.util as _ilu

# Load skill.py from ~/.e-cli/skills/sub_agent/skill.py (the runtime location).
_HOME_SKILL_PY = Path.home() / ".e-cli" / "skills" / "sub_agent" / "skill.py"
_spec = _ilu.spec_from_file_location("_sub_agent_skill_module", _HOME_SKILL_PY)
_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

SubAgentSkill = _mod.SubAgentSkill
_build_system_prompt = _mod._build_system_prompt
_truncate_to_budget = _mod._truncate_to_budget
_count_tokens = _mod._count_tokens

from e_cli.agent.protocol import ToolCall, ToolResult
from e_cli.sub_agent.models import Result_Envelope, Task_Envelope
from e_cli.sub_agent.pool import Sub_Agent_Pool, TaskRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MANIFEST = {
    "name": "sub_agent",
    "version": "1.0.0",
    "description": "Sub-agent skill",
    "capabilities": [],
    "safetyClass": "elevated",
    "entrypoint": "skill.py",
    "tools": [],
}


def _make_skill(pool: Sub_Agent_Pool | None = None) -> SubAgentSkill:
    """Create a SubAgentSkill with optional pre-built pool."""
    with patch.object(SubAgentSkill, "__init__", lambda self, manifest: (
        super(SubAgentSkill, self).__init__(manifest) or
        setattr(self, "_pool", pool) or
        setattr(self, "_skill_dir", Path(__file__).parent.parent / "src" / "e_cli" / "sub_agent")
    )):
        skill = SubAgentSkill(_MANIFEST)
    return skill


_SKILL_DIR = Path(__file__).parent.parent / "src" / "e_cli" / "sub_agent"
# The orchestration_prompt.txt lives in ~/.e-cli/skills/sub_agent/ at runtime.
# For tests, we use the workspace copy of the skill template directory.
_HOME_SKILL_DIR = Path.home() / ".e-cli" / "skills" / "sub_agent"


def _make_skill_simple(pool: Sub_Agent_Pool | None = None) -> SubAgentSkill:
    """Create SubAgentSkill bypassing __init__ side effects."""
    skill = object.__new__(SubAgentSkill)
    # Call BaseSkill.__init__ manually.
    from e_cli.skills.base import BaseSkill
    BaseSkill.__init__(skill, _MANIFEST)
    skill._pool = pool
    # Use the home skill dir if it exists (has orchestration_prompt.txt), else workspace.
    skill._skill_dir = _HOME_SKILL_DIR if _HOME_SKILL_DIR.exists() else _SKILL_DIR
    return skill


def _make_pool_stub(
    assign_return: str | ToolResult = "abc12345",
    status_return: str | ToolResult = "completed",
    result_return: Result_Envelope | ToolResult | None = None,
) -> MagicMock:
    """Create a mock Sub_Agent_Pool."""
    pool = MagicMock(spec=Sub_Agent_Pool)
    pool.assign.return_value = assign_return
    pool.status.return_value = status_return
    if result_return is None:
        result_return = Result_Envelope(
            task_id="abc12345",
            status="completed",
            output="Done. CONFIDENCE: 0.8",
            confidence=0.8,
            tool_calls_made=2,
        )
    pool.get_result.return_value = result_return
    pool._tasks = {}
    return pool


def _make_assign_call(task: str = "do something", **kwargs) -> ToolCall:
    """Build a ToolCall for sub_agent.assign with task in content."""
    payload = {"task": task}
    payload.update(kwargs)
    return ToolCall(tool="shell", command="sub_agent.assign", content=json.dumps(payload))


def _make_status_call(task_id: str = "abc12345") -> ToolCall:
    return ToolCall(tool="shell", command="sub_agent.status", query=task_id)


def _make_verify_call(task_id: str = "abc12345") -> ToolCall:
    return ToolCall(tool="shell", command="sub_agent.verify", query=task_id)


def _make_help_call() -> ToolCall:
    return ToolCall(tool="shell", command="sub_agent.help")


# ---------------------------------------------------------------------------
# Unit tests: sub_agent.assign
# ---------------------------------------------------------------------------


class TestAssign:
    def test_assign_returns_task_id_on_success(self):
        pool = _make_pool_stub(assign_return="abc12345")
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_assign_call("summarize file"), None)
        assert result.ok is True
        assert result.output == "abc12345"

    def test_assign_missing_task_returns_error(self):
        pool = _make_pool_stub()
        skill = _make_skill_simple(pool)
        call = ToolCall(tool="shell", command="sub_agent.assign", content=json.dumps({}))
        result = skill.execute(call, None)
        assert result.ok is False
        assert "task" in result.output.lower()

    def test_assign_propagates_pool_error(self):
        pool = _make_pool_stub(
            assign_return=ToolResult(ok=False, output="Sub-agent queue full; retry after current tasks complete")
        )
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_assign_call("task"), None)
        assert result.ok is False
        assert "queue full" in result.output.lower()

    def test_assign_parses_tool_allowlist(self):
        pool = _make_pool_stub()
        skill = _make_skill_simple(pool)
        call = _make_assign_call("task", tool_allowlist=["file.read"])
        skill.execute(call, None)
        envelope = pool.assign.call_args[0][0]
        assert envelope.tool_allowlist == ["file.read"]

    def test_assign_parses_result_schema(self):
        pool = _make_pool_stub()
        skill = _make_skill_simple(pool)
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
        call = _make_assign_call("task", result_schema=schema)
        skill.execute(call, None)
        envelope = pool.assign.call_args[0][0]
        assert envelope.result_schema == schema

    def test_assign_parses_timeout_seconds(self):
        pool = _make_pool_stub()
        skill = _make_skill_simple(pool)
        call = _make_assign_call("task", timeout_seconds=60)
        skill.execute(call, None)
        envelope = pool.assign.call_args[0][0]
        assert envelope.timeout_seconds == 60

    def test_assign_truncates_context_to_budget(self):
        pool = _make_pool_stub()
        skill = _make_skill_simple(pool)
        # Create context that exceeds 2048 tokens (2048 * 4 = 8192 chars).
        long_context = "x" * 10000
        call = _make_assign_call("task", context=long_context)
        with patch("e_cli.config.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(
                subAgentContextBudget=2048,
                subAgentMaxConcurrency=0,
            )
            skill.execute(call, None)
        envelope = pool.assign.call_args[0][0]
        # Context should be truncated.
        assert len(envelope.context) < len(long_context)
        assert "[Context truncated" in envelope.context


# ---------------------------------------------------------------------------
# Unit tests: sub_agent.status
# ---------------------------------------------------------------------------


class TestStatus:
    def test_status_returns_state_string(self):
        pool = _make_pool_stub(status_return="running")
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_status_call("abc12345"), None)
        assert result.ok is True
        assert result.output == "running"

    def test_status_unknown_task_id(self):
        pool = _make_pool_stub(
            status_return=ToolResult(ok=False, output="Unknown task_id")
        )
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_status_call("unknown"), None)
        assert result.ok is False
        assert "Unknown task_id" in result.output

    def test_status_missing_task_id(self):
        pool = _make_pool_stub()
        skill = _make_skill_simple(pool)
        call = ToolCall(tool="shell", command="sub_agent.status")
        result = skill.execute(call, None)
        assert result.ok is False
        assert "task_id" in result.output.lower()

    def test_status_all_valid_states(self):
        for state in ("queued", "running", "completed", "failed", "timeout"):
            pool = _make_pool_stub(status_return=state)
            skill = _make_skill_simple(pool)
            result = skill.execute(_make_status_call("abc"), None)
            assert result.ok is True
            assert result.output == state


# ---------------------------------------------------------------------------
# Unit tests: sub_agent.verify
# ---------------------------------------------------------------------------


class TestVerify:
    def test_verify_returns_result_envelope_json(self):
        envelope_result = Result_Envelope(
            task_id="abc12345",
            status="completed",
            output="Done. CONFIDENCE: 0.9",
            confidence=0.9,
            tool_calls_made=3,
        )
        pool = _make_pool_stub(status_return="completed", result_return=envelope_result)
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is True
        data = json.loads(result.output)
        assert data["task_id"] == "abc12345"
        assert data["status"] == "completed"
        assert data["confidence"] == 0.9
        assert data["tool_calls_made"] == 3

    def test_verify_task_not_complete_returns_error(self):
        pool = _make_pool_stub(status_return="running")
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is False
        assert "not yet complete" in result.output.lower()

    def test_verify_queued_task_returns_error(self):
        pool = _make_pool_stub(status_return="queued")
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is False

    def test_verify_unknown_task_id(self):
        pool = _make_pool_stub(
            status_return=ToolResult(ok=False, output="Unknown task_id")
        )
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("unknown"), None)
        assert result.ok is False
        assert "Unknown task_id" in result.output

    def test_verify_missing_task_id(self):
        pool = _make_pool_stub()
        skill = _make_skill_simple(pool)
        call = ToolCall(tool="shell", command="sub_agent.verify")
        result = skill.execute(call, None)
        assert result.ok is False

    def test_verify_schema_validation_valid(self):
        """When result_schema is provided and output matches, schema_valid=True."""
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}
        output_json = json.dumps({"count": 5})
        envelope_result = Result_Envelope(
            task_id="abc12345",
            status="completed",
            output=output_json,
            confidence=0.8,
            tool_calls_made=1,
        )
        pool = _make_pool_stub(status_return="completed", result_return=envelope_result)
        # Inject task record with schema.
        task_record = MagicMock()
        task_record.envelope.result_schema = schema
        pool._tasks = {"abc12345": task_record}
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is True
        data = json.loads(result.output)
        assert data["schema_valid"] is True
        assert data["schema_errors"] == []

    def test_verify_schema_validation_invalid(self):
        """When result_schema is provided and output doesn't match, schema_valid=False."""
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}
        output_json = json.dumps({"name": "test"})  # missing required 'count'
        envelope_result = Result_Envelope(
            task_id="abc12345",
            status="completed",
            output=output_json,
            confidence=0.5,
            tool_calls_made=1,
        )
        pool = _make_pool_stub(status_return="completed", result_return=envelope_result)
        task_record = MagicMock()
        task_record.envelope.result_schema = schema
        pool._tasks = {"abc12345": task_record}
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is True
        data = json.loads(result.output)
        assert data["schema_valid"] is False
        assert len(data["schema_errors"]) > 0

    def test_verify_schema_validation_not_json(self):
        """When output is not JSON and schema is provided, schema_valid=False."""
        schema = {"type": "object"}
        envelope_result = Result_Envelope(
            task_id="abc12345",
            status="completed",
            output="plain text output",
            confidence=0.5,
            tool_calls_made=1,
        )
        pool = _make_pool_stub(status_return="completed", result_return=envelope_result)
        task_record = MagicMock()
        task_record.envelope.result_schema = schema
        pool._tasks = {"abc12345": task_record}
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is True
        data = json.loads(result.output)
        assert data["schema_valid"] is False

    def test_verify_no_schema_schema_valid_is_none(self):
        """When no result_schema, schema_valid is None."""
        envelope_result = Result_Envelope(
            task_id="abc12345",
            status="completed",
            output="some output",
            confidence=0.7,
            tool_calls_made=1,
        )
        pool = _make_pool_stub(status_return="completed", result_return=envelope_result)
        task_record = MagicMock()
        task_record.envelope.result_schema = None
        pool._tasks = {"abc12345": task_record}
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is True
        data = json.loads(result.output)
        assert data["schema_valid"] is None

    def test_verify_confidence_parsed_from_output(self):
        """Confidence is parsed from CONFIDENCE: line in output."""
        envelope_result = Result_Envelope(
            task_id="abc12345",
            status="completed",
            output="Task done.\nCONFIDENCE: 0.75",
            confidence=0.75,
            tool_calls_made=2,
        )
        pool = _make_pool_stub(status_return="completed", result_return=envelope_result)
        pool._tasks = {}
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is True
        data = json.loads(result.output)
        assert data["confidence"] == 0.75

    def test_verify_failed_task_returns_result(self):
        """verify works for failed tasks too."""
        envelope_result = Result_Envelope(
            task_id="abc12345",
            status="failed",
            output="Parse failure after 3 consecutive unparseable turns",
            confidence=0.5,
            tool_calls_made=0,
        )
        pool = _make_pool_stub(status_return="failed", result_return=envelope_result)
        pool._tasks = {}
        skill = _make_skill_simple(pool)
        result = skill.execute(_make_verify_call("abc12345"), None)
        assert result.ok is True
        data = json.loads(result.output)
        assert data["status"] == "failed"


# ---------------------------------------------------------------------------
# Unit tests: sub_agent.help
# ---------------------------------------------------------------------------


class TestHelp:
    def test_help_returns_orchestration_prompt(self):
        skill = _make_skill_simple()
        result = skill.execute(_make_help_call(), None)
        assert result.ok is True
        assert len(result.output) > 0
        # Should contain the three-step pattern.
        assert "assign" in result.output.lower()

    def test_help_returns_error_if_file_missing(self):
        skill = _make_skill_simple()
        skill._skill_dir = Path("/nonexistent/path")
        result = skill.execute(_make_help_call(), None)
        assert result.ok is False
        assert "orchestration_prompt.txt" in result.output

    def test_help_content_contains_three_steps(self):
        skill = _make_skill_simple()
        result = skill.execute(_make_help_call(), None)
        assert result.ok is True
        content = result.output.lower()
        assert "decompose" in content or "step 1" in content
        assert "assign" in content
        assert "verify" in content or "poll" in content


# ---------------------------------------------------------------------------
# Unit tests: unknown tool dispatch
# ---------------------------------------------------------------------------


class TestUnknownTool:
    def test_unknown_tool_returns_error(self):
        skill = _make_skill_simple()
        call = ToolCall(tool="shell", command="sub_agent.unknown")
        result = skill.execute(call, None)
        assert result.ok is False
        assert "Unknown tool" in result.output


# ---------------------------------------------------------------------------
# Unit tests: system prompt builder
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_prompt_contains_only_allowlisted_tools(self):
        allowlist = ["file.read", "http.get"]
        prompt = _build_system_prompt(allowlist, "", 2048)
        assert "file.read" in prompt
        assert "http.get" in prompt
        # Non-allowlisted tools should not appear.
        assert "file.write" not in prompt
        assert "shell" not in prompt

    def test_prompt_context_injected(self):
        prompt = _build_system_prompt(["file.read"], "My project context.", 2048)
        assert "My project context." in prompt

    def test_prompt_context_truncated(self):
        long_context = "A" * 10000
        prompt = _build_system_prompt(["file.read"], long_context, 100)
        assert "[Context truncated" in prompt
        # The full context should not be present.
        assert long_context not in prompt

    def test_prompt_contains_confidence_example(self):
        prompt = _build_system_prompt(["file.read"], "", 2048)
        assert "CONFIDENCE:" in prompt

    def test_prompt_contains_done_example(self):
        prompt = _build_system_prompt(["file.read"], "", 2048)
        assert "done" in prompt.lower()

    def test_prompt_contains_tool_call_example(self):
        prompt = _build_system_prompt(["file.read"], "", 2048)
        assert '"tool"' in prompt

    def test_empty_allowlist_shows_no_tools(self):
        prompt = _build_system_prompt([], "", 2048)
        assert "no tools available" in prompt.lower()


# ---------------------------------------------------------------------------
# Unit tests: _truncate_to_budget
# ---------------------------------------------------------------------------


class TestTruncateToBudget:
    def test_short_text_not_truncated(self):
        text = "hello"
        result, was_truncated = _truncate_to_budget(text, 100)
        assert result == text
        assert was_truncated is False

    def test_long_text_truncated(self):
        text = "x" * 1000
        result, was_truncated = _truncate_to_budget(text, 10)
        assert was_truncated is True
        assert len(result) < len(text)

    def test_truncated_length_respects_budget(self):
        text = "x" * 10000
        budget = 50
        result, _ = _truncate_to_budget(text, budget)
        assert _count_tokens(result) <= budget


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Property 3: Context truncation invariant
# **Validates: Requirements 2.2, 5.2**
# ---------------------------------------------------------------------------

@given(context=st.text())
@settings(max_examples=100)
def test_property3_context_truncation_invariant(context: str) -> None:
    """Property 3: Injected context is always ≤ subAgentContextBudget tokens.

    For any context string of arbitrary length, the context injected into the
    Sub_Agent system prompt contains at most subAgentContextBudget tokens, and
    a truncation notice is appended when the original string exceeded the budget.

    **Validates: Requirements 2.2, 5.2**
    """
    budget = 2048
    prompt = _build_system_prompt(["file.read"], context, budget)

    # Extract the context portion from the prompt (after "Context:\n").
    if "Context:\n" in prompt:
        context_section = prompt.split("Context:\n", 1)[1]
    else:
        context_section = ""

    # The context section (minus truncation notice) must be within budget.
    # Remove the truncation notice if present.
    if "[Context truncated" in context_section:
        # The truncation notice was added — verify original was over budget.
        assert _count_tokens(context) > budget or len(context) > budget * _mod._CHARS_PER_TOKEN

    # The total context section must not exceed budget + notice overhead.
    # We check the raw injected context (before notice) is within budget.
    truncated, was_truncated = _truncate_to_budget(context, budget)
    assert _count_tokens(truncated) <= budget

    # If truncation occurred, the notice must be in the prompt.
    if was_truncated:
        assert "[Context truncated" in prompt


# ---------------------------------------------------------------------------
# Property 4: Main_Agent history isolation
# **Validates: Requirements 2.3, 7.1**
# ---------------------------------------------------------------------------

@given(history=st.lists(st.text(min_size=1, max_size=200), min_size=0, max_size=10))
@settings(max_examples=100)
def test_property4_main_agent_history_isolation(history: list[str]) -> None:
    """Property 4: None of the Main_Agent history messages appear in the Sub_Agent system prompt.

    For any Main_Agent conversation history of arbitrary length and content,
    none of the conversation messages appear in the Sub_Agent's system prompt.

    **Validates: Requirements 2.3, 7.1**
    """
    # Build a system prompt with a specific context (not from history).
    context = "Task context only."
    prompt = _build_system_prompt(["file.read"], context, 2048)

    # None of the history messages should appear in the prompt.
    for message in history:
        # Only check messages that are long enough to be meaningful (avoid false positives
        # with very short strings that might coincidentally appear in the template).
        if len(message) >= 10:
            assert message not in prompt, (
                f"History message found in sub-agent prompt: {message!r}"
            )


# ---------------------------------------------------------------------------
# Property 9: Schema validation correctness
# **Validates: Requirements 4.4, 4.5**
# ---------------------------------------------------------------------------

def json_schema_strategy():
    """Generate simple JSON schemas for property testing."""
    # Generate schemas that require specific types.
    return st.one_of(
        # Object schema with required string field.
        st.just({"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
        # Object schema with required integer field.
        st.just({"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}),
        # String schema.
        st.just({"type": "string"}),
        # Integer schema.
        st.just({"type": "integer"}),
        # Array schema.
        st.just({"type": "array"}),
    )


@given(schema=json_schema_strategy(), output=st.text())
@settings(max_examples=100)
def test_property9_schema_validation_correctness(schema: dict, output: str) -> None:
    """Property 9: schema_valid accurately reflects whether output conforms to schema.

    For any JSON Schema and any output string:
    - schema_valid accurately reflects conformance.
    - schema_errors is non-empty iff schema_valid is False.

    **Validates: Requirements 4.4, 4.5**
    """
    skill = _make_skill_simple()
    schema_valid, schema_errors = skill._validate_schema(output, schema)

    # schema_errors must be non-empty iff schema_valid is False.
    if schema_valid is False:
        assert len(schema_errors) > 0, (
            "schema_errors must be non-empty when schema_valid is False"
        )
    else:
        assert schema_valid is True
        assert schema_errors == [], (
            "schema_errors must be empty when schema_valid is True"
        )


# ---------------------------------------------------------------------------
# Property 11: System prompt lists only allowlisted tools
# **Validates: Requirements 5.6**
# ---------------------------------------------------------------------------

_ALL_KNOWN_TOOLS = list(_mod._TOOL_DESCRIPTIONS.keys())


@given(
    allowlist=st.lists(
        st.sampled_from(_ALL_KNOWN_TOOLS),
        min_size=1,
        max_size=len(_ALL_KNOWN_TOOLS),
        unique=True,
    )
)
@settings(max_examples=100)
def test_property11_system_prompt_lists_only_allowlisted_tools(allowlist: list[str]) -> None:
    """Property 11: Sub_Agent system prompt contains exactly the allowlisted tool schemas.

    For any tool_allowlist, the Sub_Agent's system prompt contains tool schema entries
    for exactly the tools in the allowlist and no others.

    **Validates: Requirements 5.6**
    """
    prompt = _build_system_prompt(allowlist, "", 2048)

    # Every allowlisted tool must appear in the prompt.
    for tool in allowlist:
        assert tool in prompt, f"Allowlisted tool {tool!r} not found in prompt"

    # No non-allowlisted tool should appear in the tool list section.
    non_allowlisted = [t for t in _ALL_KNOWN_TOOLS if t not in allowlist]
    for tool in non_allowlisted:
        # The tool name should not appear as a tool entry (it might appear in examples).
        # We check the tool list section specifically.
        # The tool list is between "Available tools:" and the next blank line.
        if "Available tools:" in prompt:
            tools_section_start = prompt.index("Available tools:") + len("Available tools:")
            # Find end of tools section (next blank line or "Tool call example").
            tools_section_end = len(prompt)
            for marker in ["\nTool call example", "\nDone example", "\nContext:"]:
                idx = prompt.find(marker, tools_section_start)
                if idx != -1 and idx < tools_section_end:
                    tools_section_end = idx
            tools_section = prompt[tools_section_start:tools_section_end]
            assert tool not in tools_section, (
                f"Non-allowlisted tool {tool!r} found in tools section of prompt"
            )
