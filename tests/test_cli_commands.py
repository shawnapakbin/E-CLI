"""Tests for CLI command handlers without invoking terminal subprocesses."""

from pathlib import Path

from e_cli.cli import (
    approvalSet,
    approvalStatus,
    ask,
    continueSession,
    doctor,
    listModels,
    listSessions,
    safeModeStatus,
    selectModel,
    setSafeMode,
    showSession,
    testModel,
    listTools,
    runTool,
    showConfig,
    setConfig,
    useModel,
)
from e_cli.config import AppConfig
from e_cli.memory.store import MemoryEntry, SessionSummary
from e_cli.models.base import ModelResponse
from e_cli.agent.protocol import ToolResult
from e_cli.models.discovery import DiscoveredEndpoint


def test_models_list_no_discovery(monkeypatch) -> None:
    """Ensures list command handles empty discovery with user guidance."""

    monkeypatch.setattr("e_cli.cli.load_config", lambda: AppConfig())
    monkeypatch.setattr("e_cli.cli.ModelDiscovery.discover", lambda: [])
    monkeypatch.setattr("e_cli.cli.printError", lambda _m: None)
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)
    listModels()


def test_models_use_persists_selection(monkeypatch) -> None:
    """Ensures selected provider/model values are written to config."""

    stored: dict[str, object] = {}
    monkeypatch.setattr("e_cli.cli.load_config", lambda: AppConfig())
    monkeypatch.setattr("e_cli.cli.save_config", lambda cfg: stored.update(cfg.model_dump()))
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)
    useModel(provider="ollama", endpoint="http://127.0.0.1:11434", model="llama3")
    assert stored["model"] == "llama3"


def test_safe_mode_commands(monkeypatch) -> None:
    """Ensures safe mode status and update commands execute without errors."""

    cfg = AppConfig()
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.save_config", lambda _cfg: None)
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)
    safeModeStatus()
    setSafeMode(enabled=False)
    assert cfg.safeMode is False


def test_ask_without_model(monkeypatch) -> None:
    """Ensures ask command exits gracefully when no model is selected."""

    monkeypatch.setattr("e_cli.cli.load_config", lambda: AppConfig(model=""))
    monkeypatch.setattr("e_cli.cli.printError", lambda _m: None)
    ask(prompt="hello")


def test_ask_happy_path(monkeypatch, tmp_path: Path) -> None:
    """Ensures ask command executes agent loop path and prints final response."""

    cfg = AppConfig(model="m", endpoint="http://x", provider="ollama", memoryPath=str(tmp_path / "m.db"))
    saved: dict[str, object] = {}
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.save_config", lambda config: saved.update(config.model_dump()))
    monkeypatch.setattr("e_cli.cli.create_model_client", lambda provider, endpoint: object())

    class FakeLoop:
        def __init__(self, **kwargs: object):
            _ = kwargs

        def run(self, userPrompt: str, sessionId: str) -> str:
            _ = (userPrompt, sessionId)
            return "done"

    monkeypatch.setattr("e_cli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)
    ask(prompt="task")
    assert isinstance(saved.get("lastSessionId"), str)
    assert saved.get("lastSessionId")


def test_ask_uses_explicit_session_id(monkeypatch, tmp_path: Path) -> None:
    """Ensures ask command honors explicit session id and persists it to config."""

    cfg = AppConfig(model="m", endpoint="http://x", provider="ollama", memoryPath=str(tmp_path / "m.db"))
    saved: dict[str, object] = {}
    seenSessionIds: list[str] = []

    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.save_config", lambda config: saved.update(config.model_dump()))
    monkeypatch.setattr("e_cli.cli.create_model_client", lambda provider, endpoint: object())

    class FakeLoop:
        def __init__(self, **kwargs: object):
            _ = kwargs

        def run(self, userPrompt: str, sessionId: str) -> str:
            _ = userPrompt
            seenSessionIds.append(sessionId)
            return "done"

    monkeypatch.setattr("e_cli.cli.AgentLoop", FakeLoop)
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)

    ask(prompt="task", sessionId="session-42")
    assert seenSessionIds == ["session-42"]
    assert saved.get("lastSessionId") == "session-42"


def test_list_models_with_discovery(monkeypatch) -> None:
    """Ensures list command prints models when endpoints are reachable."""

    monkeypatch.setattr("e_cli.cli.load_config", lambda: AppConfig())
    monkeypatch.setattr(
        "e_cli.cli.ModelDiscovery.discover",
        lambda: [DiscoveredEndpoint(provider="ollama", endpoint="http://127.0.0.1:11434")],
    )

    class FakeClient:
        def list_models(self, timeout_seconds: int) -> list[str]:
            _ = timeout_seconds
            return ["llama3"]

    monkeypatch.setattr("e_cli.cli.create_model_client", lambda provider, endpoint: FakeClient())
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)
    listModels()


def test_model_select_with_index(monkeypatch) -> None:
    """Ensures index-based model selection persists provider and model values."""

    cfg = AppConfig()
    saved: dict[str, object] = {}
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.save_config", lambda config: saved.update(config.model_dump()))
    monkeypatch.setattr(
        "e_cli.cli._collectModelOptions",
        lambda _cfg: [
            type("Opt", (), {"provider": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "llama3"})
        ],
    )
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)

    selectModel(index=1)
    assert saved["provider"] == "ollama"
    assert saved["model"] == "llama3"


def test_approval_commands(monkeypatch) -> None:
    """Ensures approval mode status and set commands update config correctly."""

    cfg = AppConfig()
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.save_config", lambda _cfg: None)
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)

    approvalStatus()
    approvalSet(mode="auto-approve")
    assert cfg.approvalMode == "auto-approve"


def test_sessions_list_command(monkeypatch) -> None:
    """Ensures sessions list prints available session summaries."""

    class FakeMemoryService:
        def listSessions(self, limit: int) -> list[SessionSummary]:
            _ = limit
            return [
                SessionSummary(sessionId="s1", messageCount=2, lastCreatedAt="2026-03-10T00:00:00Z")
            ]

    monkeypatch.setattr("e_cli.cli.load_config", lambda: AppConfig())
    monkeypatch.setattr("e_cli.cli._buildMemoryService", lambda _config: FakeMemoryService())
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)

    listSessions(limit=5)


def test_sessions_show_uses_last_session(monkeypatch) -> None:
    """Ensures session show uses lastSessionId fallback when option is omitted."""

    class FakeMemoryService:
        def loadEntries(self, sessionId: str, limit: int) -> list[MemoryEntry]:
            _ = limit
            return [
                MemoryEntry(
                    sessionId=sessionId,
                    role="user",
                    content="hello",
                    createdAt="2026-03-10T00:00:00Z",
                )
            ]

    cfg = AppConfig(lastSessionId="session-last")
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli._buildMemoryService", lambda _config: FakeMemoryService())
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)
    monkeypatch.setattr("e_cli.cli.printError", lambda _m: None)

    showSession(limit=5)


def test_sessions_continue_with_explicit_session_id(monkeypatch) -> None:
    """Ensures continue command delegates to ask with explicit session id."""

    seenCalls: list[tuple[str, str]] = []
    monkeypatch.setattr("e_cli.cli.load_config", lambda: AppConfig(lastSessionId="session-last"))
    monkeypatch.setattr("e_cli.cli.ask", lambda prompt, sessionId: seenCalls.append((prompt, sessionId)))
    monkeypatch.setattr("e_cli.cli.printError", lambda _m: None)
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)

    continueSession(prompt="inspect nginx", sessionId="session-42", last=False)
    assert seenCalls == [("inspect nginx", "session-42")]


def test_sessions_continue_with_last_flag(monkeypatch) -> None:
    """Ensures continue command uses lastSessionId when --last is selected."""

    seenCalls: list[tuple[str, str]] = []
    monkeypatch.setattr("e_cli.cli.load_config", lambda: AppConfig(lastSessionId="session-last"))
    monkeypatch.setattr("e_cli.cli.ask", lambda prompt, sessionId: seenCalls.append((prompt, sessionId)))
    monkeypatch.setattr("e_cli.cli.printError", lambda _m: None)
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)

    continueSession(prompt="inspect nginx", last=True)
    assert seenCalls == [("inspect nginx", "session-last")]


def test_sessions_continue_requires_target(monkeypatch) -> None:
    """Ensures continue command fails gracefully when no session target is available."""

    seenCalls: list[tuple[str, str]] = []
    cfg = AppConfig(lastSessionId="")
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.ask", lambda prompt, sessionId: seenCalls.append((prompt, sessionId)))
    monkeypatch.setattr("e_cli.cli.printError", lambda _m: None)
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)

    continueSession(prompt="inspect nginx", last=False)
    assert seenCalls == []


def test_models_test_happy_path(monkeypatch) -> None:
    """Ensures models test sends a user prompt and prints response preview."""

    cfg = AppConfig(model="llama3", provider="ollama", endpoint="http://127.0.0.1:11434")

    class FakeClient:
        def chat(self, model_name: str, messages, timeout_seconds: int) -> ModelResponse:
            _ = (model_name, timeout_seconds)
            assert len(messages) == 1
            assert messages[0].role == "user"
            return ModelResponse(content="OK")

    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.create_model_client", lambda provider, endpoint: FakeClient())
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)

    testModel(prompt="Reply OK")


def test_doctor_reports_checks(monkeypatch, tmp_path: Path) -> None:
    """Ensures doctor runs core checks and reports check lines."""

    cfg = AppConfig(
        model="llama3",
        provider="ollama",
        endpoint="http://127.0.0.1:11434",
        memoryPath=str(tmp_path / "memory.db"),
    )
    captured: list[str] = []

    class FakeClient:
        def list_models(self, timeout_seconds: int) -> list[str]:
            _ = timeout_seconds
            return ["llama3"]

    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr(
        "e_cli.cli.ModelDiscovery.discover",
        lambda: [DiscoveredEndpoint(provider="ollama", endpoint="http://127.0.0.1:11434")],
    )
    monkeypatch.setattr("e_cli.cli.create_model_client", lambda provider, endpoint: FakeClient())
    monkeypatch.setattr("e_cli.cli.printInfo", lambda m: captured.append(m))
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)

    doctor()
    assert any("config.model" in line for line in captured)
    assert any("selected.model" in line for line in captured)


def test_tools_list_command(monkeypatch) -> None:
    """Ensures tools list prints current policy summary lines."""

    cfg = AppConfig()
    captured: list[str] = []
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.printInfo", lambda m: captured.append(m))
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)

    listTools()
    assert any(line.startswith("shell:") for line in captured)
    assert any(line.startswith("file.read:") for line in captured)


def test_tools_run_shell_success(monkeypatch, tmp_path: Path) -> None:
    """Ensures tools run executes shell tool through router when policy allows."""

    cfg = AppConfig(timeoutSeconds=5, approvalMode="auto-approve")

    class FakeRouter:
        def __init__(self, workspaceRoot):
            _ = workspaceRoot

        def execute(self, toolCall, timeoutSeconds: int) -> ToolResult:
            _ = (toolCall, timeoutSeconds)
            return ToolResult(ok=True, output="ok")

    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.ToolRouter", FakeRouter)
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)

    runTool(tool="shell", command="echo hi")


def test_tools_run_rejects_unknown_tool(monkeypatch) -> None:
    """Ensures tools run rejects unsupported tool names."""

    cfg = AppConfig()
    errors: list[str] = []
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.printError", lambda m: errors.append(m))

    runTool(tool="unknown")
    assert any("Unsupported tool" in message for message in errors)


def test_config_show_command(monkeypatch) -> None:
    """Ensures config show prints key persisted settings."""

    cfg = AppConfig(model="llama3", endpoint="http://127.0.0.1:11434")
    captured: list[str] = []
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.printInfo", lambda m: captured.append(m))
    monkeypatch.setattr("e_cli.cli.printQuickTip", lambda _m: None)

    showConfig()
    assert any(line.startswith("provider=") for line in captured)
    assert any(line.startswith("model=") for line in captured)


def test_config_set_updates_selected_fields(monkeypatch) -> None:
    """Ensures config set persists updates for provided options only."""

    cfg = AppConfig()
    saved: dict[str, object] = {}
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.save_config", lambda config: saved.update(config.model_dump()))
    monkeypatch.setattr("e_cli.cli.printInfo", lambda _m: None)

    setConfig(provider="vllm", model="model-a", maxTurns=12, timeoutSeconds=90)
    assert saved["provider"] == "vllm"
    assert saved["model"] == "model-a"
    assert saved["maxTurns"] == 12
    assert saved["timeoutSeconds"] == 90


def test_config_set_rejects_invalid_limits(monkeypatch) -> None:
    """Ensures config set validates positive integer constraints."""

    cfg = AppConfig()
    errors: list[str] = []
    monkeypatch.setattr("e_cli.cli.load_config", lambda: cfg)
    monkeypatch.setattr("e_cli.cli.printError", lambda m: errors.append(m))

    setConfig(maxTurns=0)
    assert any("maxTurns must be >= 1" in message for message in errors)
