"""Tests for agent loop completion behavior."""

from pathlib import Path

from e_cli.agent.loop import AgentLoop
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
