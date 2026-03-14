"""Tests for agent loop completion behavior."""

from pathlib import Path

from e_cli.agent.loop import AgentError, AgentLoop, build_system_prompt
from e_cli.memory.service import MemoryService
from e_cli.memory.store import MemoryStore
from e_cli.models.base import ModelMessage, ModelResponse
from e_cli.safety.policy import SafetyPolicy


class FakeModelClient:
    """Test model client that returns deterministic outputs per invocation."""

    provider_name = "fake"

    def __init__(self) -> None:
        """Initializes invocation counter for deterministic response sequence."""

        self.callCount = 0

    def chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> ModelResponse:
        """Returns shell call first, then done signal second."""

        self.callCount += 1
        if self.callCount == 1:
            return ModelResponse(content='{"tool":"shell","command":"echo hello"}')
        return ModelResponse(content='{"tool":"done","reason":"completed"}')

    def list_models(self, timeout_seconds: int) -> list[str]:
        """Returns synthetic model list for contract completeness."""

        return ["fake-model"]

    def stream_chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> list[str]:
        """Return streaming chunks for the same deterministic response sequence."""

        response = self.chat(model_name=model_name, messages=messages, timeout_seconds=timeout_seconds)
        return [response.content]


def test_agent_loop_completes_with_done_signal(tmp_path: Path, monkeypatch) -> None:
    """Verifies loop returns done reason and persists interaction memory."""

    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=tmp_path / "memory.db", schemaPath=schemaPath)
    memoryService = MemoryService(memoryStore=store)
    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))
    modelClient = FakeModelClient()

    monkeypatch.setattr("e_cli.safety.approval.requestApproval", lambda _toolCall, _reason: True)

    loop = AgentLoop(
        modelClient=modelClient,
        modelName="fake-model",
        memoryService=memoryService,
        safetyPolicy=policy,
        workspaceRoot=tmp_path,
        timeoutSeconds=5,
        maxTurns=4,
        approvalMode="interactive",
        streamingEnabled=True,
        conversationTokenBudget=3200,
        conversationSummaryBudget=800,
    )

    result = loop.run(userPrompt="say hello", sessionId="s1")
    assert result == "completed"
    auditEvents = memoryService.listAuditEvents(sessionId="s1")
    assert any(event.action == "tool.execute" for event in auditEvents)


def test_agent_loop_tags_tool_call_as_ai_thinking_and_persists_tool_result_as_user_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Ensures tool-call turns are labeled as AI Thinking and tool output is fed back as user context."""

    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=tmp_path / "memory.db", schemaPath=schemaPath)
    memoryService = MemoryService(memoryStore=store)
    policy = SafetyPolicy(safeMode=True, trustedReadCommands=("echo",))
    modelClient = FakeModelClient()
    infoLines: list[str] = []

    monkeypatch.setattr("e_cli.safety.approval.requestApproval", lambda _toolCall, _reason: True)
    monkeypatch.setattr("e_cli.agent.loop.printInfo", lambda message: infoLines.append(message))
    monkeypatch.setattr("e_cli.agent.loop.printQuickTip", lambda _message: None)

    loop = AgentLoop(
        modelClient=modelClient,
        modelName="fake-model",
        memoryService=memoryService,
        safetyPolicy=policy,
        workspaceRoot=tmp_path,
        timeoutSeconds=5,
        maxTurns=4,
        approvalMode="interactive",
        streamingEnabled=True,
        conversationTokenBudget=3200,
        conversationSummaryBudget=800,
    )

    result = loop.run(userPrompt="say hello", sessionId="s2")

    assert result == "completed"
    assert any(line.startswith("AI Thinking: {") for line in infoLines)

    entries = store.listAllBySession("s2")
    toolResultEntries = [entry for entry in entries if entry.content.startswith("[Tool result: shell]\n")]
    assert toolResultEntries
    assert all(entry.role == "user" for entry in toolResultEntries)


def test_agent_loop_loads_summary_for_long_history(tmp_path: Path) -> None:
    """Verifies token-budgeted recall inserts a summary message for older turns."""

    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=tmp_path / "memory.db", schemaPath=schemaPath)
    memoryService = MemoryService(memoryStore=store)
    for index in range(12):
        store.append(sessionId="session-long", role="user", content=f"message {index} " + ("x" * 220))

    messages = memoryService.loadConversation(sessionId="session-long", maxTokens=160, summaryTokens=80)

    assert messages[0].role == "system"
    assert "Prior conversation summary" in messages[0].content


def test_build_system_prompt_contains_tool_names() -> None:
    """Ensures build_system_prompt includes all core tool names in the output."""

    prompt = build_system_prompt()
    for tool_name in ("shell", "file.read", "file.write", "git.diff", "http.get",
                      "browser", "ssh", "curl", "rag.search", "done"):
        assert tool_name in prompt


def test_build_system_prompt_custom_persona() -> None:
    """Ensures a custom persona string appears in the built prompt."""

    prompt = build_system_prompt(persona="You are a setup assistant.")
    assert "You are a setup assistant." in prompt


def test_build_system_prompt_extra_schemas_injected() -> None:
    """Ensures extra tool schemas passed by callers appear in the built prompt."""

    extra = ['{"tool":"my_skill","query":"..."}']
    prompt = build_system_prompt(extra_tool_schemas=extra)
    assert "my_skill" in prompt


def test_agent_error_enum_values() -> None:
    """Ensures AgentError enum has the expected classification codes."""

    codes = {e.value for e in AgentError}
    assert "PARSE_ERROR" in codes
    assert "MAX_TURNS" in codes
    assert "MODEL_TIMEOUT" in codes
    assert "TOOL_EXEC_ERROR" in codes


def test_agent_loop_generic_exception_raises_runtime_error(tmp_path: Path, monkeypatch) -> None:
    """Ensures unknown exceptions from the loop are wrapped as classified RuntimeErrors."""

    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=tmp_path / "memory.db", schemaPath=schemaPath)
    memoryService = MemoryService(memoryStore=store)
    policy = SafetyPolicy(safeMode=False, trustedReadCommands=())

    class ExplodingModelClient:
        provider_name = "fake"

        def chat(self, model_name, messages, timeout_seconds):  # noqa: ANN001
            raise ValueError("unexpected model error")

        def list_models(self, timeout_seconds):  # noqa: ANN001
            return []

    monkeypatch.setattr("e_cli.agent.loop.printQuickTip", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printInfo", lambda _m: None)

    loop = AgentLoop(
        modelClient=ExplodingModelClient(),
        modelName="bad-model",
        memoryService=memoryService,
        safetyPolicy=policy,
        workspaceRoot=tmp_path,
        timeoutSeconds=5,
        maxTurns=4,
        approvalMode="auto-approve",
        streamingEnabled=False,
        conversationTokenBudget=3200,
        conversationSummaryBudget=800,
    )

    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="TOOL_EXEC_ERROR"):
        loop.run(userPrompt="trigger failure", sessionId="err-session")
