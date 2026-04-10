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


# ---------------------------------------------------------------------------
# Provider fallback chain tests (Task 3.1 / 3.2)
# ---------------------------------------------------------------------------

from e_cli.config import AppConfig


def _make_loop(tmp_path: Path, model_client, config: AppConfig | None = None) -> AgentLoop:
    """Helper: build a minimal AgentLoop for fallback tests."""
    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=tmp_path / "memory.db", schemaPath=schemaPath)
    memoryService = MemoryService(memoryStore=store)
    policy = SafetyPolicy(safeMode=False, trustedReadCommands=())
    return AgentLoop(
        modelClient=model_client,
        modelName="fake-model",
        memoryService=memoryService,
        safetyPolicy=policy,
        workspaceRoot=tmp_path,
        timeoutSeconds=5,
        maxTurns=2,
        approvalMode="auto-approve",
        streamingEnabled=False,
        conversationTokenBudget=3200,
        conversationSummaryBudget=800,
        config=config,
    )


class _ReachableClient:
    """Fake client that is always reachable and returns a done signal."""

    provider_name = "reachable"

    def list_models(self, timeout_seconds: int) -> list[str]:
        return ["fake-model"]

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        return ModelResponse(content='{"tool":"done","reason":"ok"}')


class _UnreachableClient:
    """Fake client that always raises a connection error."""

    provider_name = "unreachable"

    def list_models(self, timeout_seconds: int) -> list[str]:
        raise ConnectionError("endpoint unreachable")

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        raise ConnectionError("endpoint unreachable")


def test_fallback_chain_skips_unreachable_primary_and_uses_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    """When primary provider is unreachable, loop switches to first reachable fallback."""

    config = AppConfig(
        provider="ollama",
        model="fake-model",
        fallbackChain=["lmstudio", "bundled"],
        memoryPath=str(tmp_path / "memory.db"),
    )

    primary = _UnreachableClient()
    primary.provider_name = "ollama"

    fallback = _ReachableClient()
    fallback.provider_name = "lmstudio"

    warnings: list[str] = []
    monkeypatch.setattr("e_cli.agent.loop.printWarning", lambda msg: warnings.append(msg))
    monkeypatch.setattr("e_cli.agent.loop.printInfo", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printQuickTip", lambda _m: None)

    # Patch create_model_client to return our fallback stub for lmstudio
    def fake_create(provider, endpoint, api_key, modelParameters, config):
        if provider == "lmstudio":
            return fallback
        bad = _UnreachableClient()
        bad.provider_name = provider
        return bad

    monkeypatch.setattr("e_cli.agent.loop.create_model_client", fake_create)

    loop = _make_loop(tmp_path, primary, config)
    result = loop.run(userPrompt="hello", sessionId="fb-test")

    assert result == "ok"
    assert loop.modelClient is fallback
    # Warning about primary being unreachable must have been logged
    assert any("unreachable" in w.lower() or "ollama" in w.lower() for w in warnings)


def test_fallback_chain_logs_warning_for_each_failed_provider(
    tmp_path: Path, monkeypatch
) -> None:
    """A warning is logged for each provider that fails before trying the next."""

    config = AppConfig(
        provider="ollama",
        model="fake-model",
        fallbackChain=["lmstudio", "bundled"],
        memoryPath=str(tmp_path / "memory.db"),
    )

    primary = _UnreachableClient()
    primary.provider_name = "ollama"

    good_client = _ReachableClient()
    good_client.provider_name = "bundled"

    call_order: list[str] = []

    def fake_create(provider, endpoint, api_key, modelParameters, config):
        call_order.append(provider)
        if provider == "lmstudio":
            bad = _UnreachableClient()
            bad.provider_name = "lmstudio"
            return bad
        return good_client

    warnings: list[str] = []
    monkeypatch.setattr("e_cli.agent.loop.printWarning", lambda msg: warnings.append(msg))
    monkeypatch.setattr("e_cli.agent.loop.printInfo", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printQuickTip", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.create_model_client", fake_create)

    loop = _make_loop(tmp_path, primary, config)
    result = loop.run(userPrompt="hello", sessionId="fb-warn-test")

    assert result == "ok"
    # lmstudio and bundled should have been tried
    assert "lmstudio" in call_order
    assert "bundled" in call_order
    # At least one warning for the failed lmstudio provider
    assert any("lmstudio" in w for w in warnings)


def test_fallback_chain_raises_when_all_providers_fail(
    tmp_path: Path, monkeypatch
) -> None:
    """RuntimeError is raised when primary and all fallback providers are unreachable."""

    import pytest

    config = AppConfig(
        provider="ollama",
        model="fake-model",
        fallbackChain=["lmstudio", "bundled"],
        memoryPath=str(tmp_path / "memory.db"),
    )

    primary = _UnreachableClient()
    primary.provider_name = "ollama"

    def fake_create(provider, endpoint, api_key, modelParameters, config):
        bad = _UnreachableClient()
        bad.provider_name = provider
        return bad

    monkeypatch.setattr("e_cli.agent.loop.printWarning", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printInfo", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printQuickTip", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.create_model_client", fake_create)

    loop = _make_loop(tmp_path, primary, config)

    with pytest.raises(RuntimeError, match="All providers unreachable"):
        loop.run(userPrompt="hello", sessionId="fb-fail-test")


def test_no_fallback_when_primary_is_reachable(
    tmp_path: Path, monkeypatch
) -> None:
    """When primary provider is reachable, fallback chain is never consulted."""

    config = AppConfig(
        provider="ollama",
        model="fake-model",
        fallbackChain=["lmstudio", "bundled"],
        memoryPath=str(tmp_path / "memory.db"),
    )

    primary = _ReachableClient()
    primary.provider_name = "ollama"

    create_calls: list[str] = []

    def fake_create(provider, endpoint, api_key, modelParameters, config):
        create_calls.append(provider)
        return _ReachableClient()

    monkeypatch.setattr("e_cli.agent.loop.printWarning", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printInfo", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printQuickTip", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.create_model_client", fake_create)

    loop = _make_loop(tmp_path, primary, config)
    result = loop.run(userPrompt="hello", sessionId="fb-noop-test")

    assert result == "ok"
    # create_model_client should NOT have been called for fallback providers
    assert create_calls == []


def test_no_fallback_when_config_is_none(tmp_path: Path, monkeypatch) -> None:
    """When no config is provided, fallback resolution is skipped entirely."""

    primary = _ReachableClient()

    monkeypatch.setattr("e_cli.agent.loop.printWarning", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printInfo", lambda _m: None)
    monkeypatch.setattr("e_cli.agent.loop.printQuickTip", lambda _m: None)

    loop = _make_loop(tmp_path, primary, config=None)
    result = loop.run(userPrompt="hello", sessionId="fb-noconfig-test")

    assert result == "ok"
