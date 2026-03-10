"""CLI command surface for E-CLI operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid

import typer

from e_cli.agent.loop import AgentLoop
from e_cli.agent.protocol import ToolCall
from e_cli.config import ApprovalMode, AppConfig, ProviderType, load_config, save_config
from e_cli.memory.service import MemoryService
from e_cli.memory.store import MemoryStore
from e_cli.models.base import ModelMessage
from e_cli.models.discovery import DiscoveredEndpoint, ModelDiscovery
from e_cli.models.factory import create_model_client
from e_cli.safety.approval import requestApprovalWithMode
from e_cli.safety.policy import SafetyPolicy
from e_cli.tools.router import ToolRouter
from e_cli.ui.messages import printError, printInfo, printQuickTip

app = typer.Typer(help="E-CLI terminal-native LLM agent")
modelsApp = typer.Typer(help="Model discovery and selection commands")
safeModeApp = typer.Typer(help="Safe mode controls")
approvalApp = typer.Typer(help="Approval mode controls")
sessionsApp = typer.Typer(help="Session memory commands")
toolsApp = typer.Typer(help="Tool inspection and execution commands")
configApp = typer.Typer(help="Configuration inspection and updates")
app.add_typer(modelsApp, name="models")
app.add_typer(safeModeApp, name="safe-mode")
app.add_typer(approvalApp, name="approval")
app.add_typer(sessionsApp, name="sessions")
app.add_typer(toolsApp, name="tools")
app.add_typer(configApp, name="config")


@dataclass(frozen=True)
class ModelSelectionOption:
    """Represents one selectable model candidate from endpoint discovery."""

    provider: ProviderType
    endpoint: str
    model: str


def _collectModelOptions(config: AppConfig) -> list[ModelSelectionOption]:
    """Discover and flatten provider/model combinations for interactive selection."""

    try:
        discoveredEndpoints: list[DiscoveredEndpoint] = ModelDiscovery.discover()
        options: list[ModelSelectionOption] = []
        for endpoint in discoveredEndpoints:
            try:
                modelClient = create_model_client(provider=endpoint.provider, endpoint=endpoint.endpoint)
                models = modelClient.list_models(timeout_seconds=config.timeoutSeconds)
                for model in models:
                    options.append(
                        ModelSelectionOption(
                            provider=endpoint.provider,
                            endpoint=endpoint.endpoint,
                            model=model,
                        )
                    )
            except Exception as providerError:
                printError(f"{endpoint.provider} @ {endpoint.endpoint}: {providerError}")
        return options
    except Exception as exc:
        raise RuntimeError(f"Failed collecting model options: {exc}") from exc


def _buildMemoryService(config: AppConfig) -> MemoryService:
    """Creates memory service dependencies from current app configuration."""

    try:
        dbPath = Path(config.memoryPath)
        schemaPath = Path(__file__).resolve().parent / "memory" / "schema.sql"
        memoryStore = MemoryStore(dbPath=dbPath, schemaPath=schemaPath)
        return MemoryService(memoryStore=memoryStore)
    except Exception as exc:
        raise RuntimeError(f"Failed to create memory service: {exc}") from exc


def _buildSafetyPolicy(config: AppConfig) -> SafetyPolicy:
    """Build runtime safety policy from persisted config values."""

    try:
        return SafetyPolicy(
            safeMode=config.safeMode,
            trustedReadCommands=(
                "ls",
                "dir",
                "pwd",
                "Get-Location",
                "cat",
                "type",
                "head",
                "tail",
                "echo",
                "systemctl status",
                "journalctl",
                "tasklist",
                "ps",
            ),
            blockedShellPatterns=(
                "rm -rf /",
                "format c:",
                "mkfs",
                "dd if=",
                "shutdown /s",
                "reboot",
                "halt",
            ),
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to build safety policy: {exc}") from exc


def _policySummaryRows(policy: SafetyPolicy) -> list[tuple[str, bool, str]]:
    """Build tool policy summary rows for `tools list` output."""

    try:
        rows: list[tuple[str, bool, str]] = []
        shellDecision = policy.evaluate(ToolCall(tool="shell", command="echo hello"))
        rows.append(("shell", shellDecision.allowed, shellDecision.reason))
        fileReadDecision = policy.evaluate(ToolCall(tool="file.read", path="README.md"))
        rows.append(("file.read", fileReadDecision.allowed, fileReadDecision.reason))
        fileWriteDecision = policy.evaluate(ToolCall(tool="file.write", path="tmp.txt", content="x"))
        rows.append(("file.write", fileWriteDecision.allowed, fileWriteDecision.reason))
        doneDecision = policy.evaluate(ToolCall(tool="done", reason="completed"))
        rows.append(("done", doneDecision.allowed, doneDecision.reason))
        return rows
    except Exception as exc:
        raise RuntimeError(f"Failed building policy summary rows: {exc}") from exc


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="Task prompt for the agent"),
    sessionId: str = typer.Option("", "--session-id", help="Resume or set conversation session id"),
) -> None:
    """Run one full agent session for a user prompt."""

    try:
        config = load_config()
        if not config.model:
            printError("No model selected. Run 'e-cli models list' and then 'e-cli models use'.")
            return

        modelClient = create_model_client(provider=config.provider, endpoint=config.endpoint)
        memoryService = _buildMemoryService(config)
        safetyPolicy = _buildSafetyPolicy(config)
        agentLoop = AgentLoop(
            modelClient=modelClient,
            modelName=config.model,
            memoryService=memoryService,
            safetyPolicy=safetyPolicy,
            workspaceRoot=Path.cwd(),
            timeoutSeconds=config.timeoutSeconds,
            maxTurns=config.maxTurns,
            approvalMode=config.approvalMode,
        )

        sessionIdText = sessionId if isinstance(sessionId, str) else ""
        effectiveSessionId = sessionIdText.strip() or config.lastSessionId or str(uuid.uuid4())
        finalAnswer = agentLoop.run(userPrompt=prompt, sessionId=effectiveSessionId)
        config.lastSessionId = effectiveSessionId
        save_config(config)
        printInfo(finalAnswer)
        printQuickTip(f"Session id: {effectiveSessionId}")
    except Exception as exc:
        printError(str(exc))


@app.command("doctor")
def doctor() -> None:
    """Run local diagnostics for config, model connectivity, safety, and memory."""

    try:
        config = load_config()
        checks: list[tuple[str, bool, str]] = []

        modelConfigured = bool(config.model.strip())
        checks.append(("config.model", modelConfigured, config.model or "(not set)"))

        memoryPath = Path(config.memoryPath)
        memoryPath.parent.mkdir(parents=True, exist_ok=True)
        if not memoryPath.exists():
            memoryPath.touch()
        checks.append(("memory.db", True, str(memoryPath)))

        try:
            _ = _buildMemoryService(config)
            checks.append(("memory.service", True, "schema loaded"))
        except Exception as memoryExc:
            checks.append(("memory.service", False, str(memoryExc)))

        policy = _buildSafetyPolicy(config)
        checks.append(("safe-mode", True, f"safeMode={policy.safeMode}, approval={config.approvalMode}"))

        discovered = ModelDiscovery.discover()
        checks.append(("discovery", bool(discovered), f"reachable endpoints={len(discovered)}"))

        if modelConfigured:
            try:
                modelClient = create_model_client(provider=config.provider, endpoint=config.endpoint)
                modelList = modelClient.list_models(timeout_seconds=config.timeoutSeconds)
                selectedModelReachable = config.model in modelList
                checks.append(
                    (
                        "selected.model",
                        selectedModelReachable,
                        f"provider={config.provider}, endpoint={config.endpoint}",
                    )
                )
            except Exception as modelExc:
                checks.append(("selected.model", False, str(modelExc)))

        failures = 0
        for name, ok, detail in checks:
            status = "OK" if ok else "FAIL"
            if not ok:
                failures += 1
            printInfo(f"[{status}] {name}: {detail}")

        if failures:
            printQuickTip("Run 'e-cli models list' then 'e-cli models use', and verify provider server status.")
        else:
            printQuickTip("Doctor checks passed. Try 'e-cli models test' for live inference validation.")
    except Exception as exc:
        printError(str(exc))


@modelsApp.command("list")
def listModels() -> None:
    """Discover model endpoints and print provider/model candidates."""

    try:
        config = load_config()
        discovered = ModelDiscovery.discover()
        if not discovered:
            printError("No model endpoints discovered.")
            printQuickTip("Start Ollama, LM Studio server, or vLLM and try again.")
            return

        for endpoint in discovered:
            try:
                modelClient = create_model_client(provider=endpoint.provider, endpoint=endpoint.endpoint)
                models = modelClient.list_models(timeout_seconds=config.timeoutSeconds)
                modelText = ", ".join(models) if models else "(no models returned)"
                printInfo(f"{endpoint.provider} @ {endpoint.endpoint}: {modelText}")
            except Exception as providerError:
                printError(f"{endpoint.provider} @ {endpoint.endpoint}: {providerError}")
    except Exception as exc:
        printError(str(exc))


@modelsApp.command("use")
def useModel(
    provider: ProviderType = typer.Option(..., "--provider", help="Model provider"),
    endpoint: str = typer.Option(..., "--endpoint", help="Provider endpoint URL"),
    model: str = typer.Option(..., "--model", help="Model name/id"),
) -> None:
    """Persist active provider/model selection in local configuration."""

    try:
        config = load_config()
        config.provider = provider
        config.endpoint = endpoint
        config.model = model
        save_config(config)
        printInfo(f"Selected {provider}:{model} at {endpoint}")
    except Exception as exc:
        printError(str(exc))


@modelsApp.command("select")
def selectModel(index: int = typer.Option(-1, "--index", help="1-based model choice index")) -> None:
    """Interactively select a discovered model and persist provider endpoint settings."""

    try:
        config = load_config()
        options = _collectModelOptions(config)
        if not options:
            printError("No model options discovered.")
            printQuickTip("Run local providers or set ECLI_LAN_HOSTS to scan additional hosts.")
            return

        for optionIndex, option in enumerate(options, start=1):
            printInfo(f"[{optionIndex}] {option.provider} @ {option.endpoint} -> {option.model}")

        selectedIndex = index
        if selectedIndex < 1 or selectedIndex > len(options):
            userInput = input(f"Select model index [1-{len(options)}]: ").strip()
            selectedIndex = int(userInput)
        if selectedIndex < 1 or selectedIndex > len(options):
            printError("Invalid model selection index.")
            return

        selected = options[selectedIndex - 1]
        config.provider = selected.provider
        config.endpoint = selected.endpoint
        config.model = selected.model
        save_config(config)
        printInfo(f"Selected {selected.provider}:{selected.model} at {selected.endpoint}")
    except Exception as exc:
        printError(str(exc))


@modelsApp.command("test")
def testModel(prompt: str = typer.Option("Reply with OK", "--prompt", help="Smoke-test prompt")) -> None:
    """Send a quick prompt to the selected model to validate live inference path."""

    try:
        config = load_config()
        if not config.model:
            printError("No model selected. Run 'e-cli models list' and then 'e-cli models use'.")
            return

        modelClient = create_model_client(provider=config.provider, endpoint=config.endpoint)
        response = modelClient.chat(
            model_name=config.model,
            messages=[ModelMessage(role="user", content=prompt)],
            timeout_seconds=config.timeoutSeconds,
        )
        reply = response.content.strip()
        preview = reply if len(reply) <= 300 else reply[:300] + "..."
        printInfo(f"Model test succeeded for {config.provider}:{config.model}")
        printInfo(preview or "(empty response)")
    except Exception as exc:
        printError(f"Model test failed: {exc}")


@safeModeApp.command("status")
def safeModeStatus() -> None:
    """Print current safe mode status from persisted configuration."""

    try:
        config = load_config()
        printInfo(f"safeMode={config.safeMode}")
    except Exception as exc:
        printError(str(exc))


@safeModeApp.command("set")
def setSafeMode(enabled: bool = typer.Argument(..., help="true or false")) -> None:
    """Enable or disable safe mode in persisted configuration."""

    try:
        config = load_config()
        config.safeMode = enabled
        save_config(config)
        printInfo(f"safeMode set to {enabled}")
    except Exception as exc:
        printError(str(exc))


@approvalApp.command("status")
def approvalStatus() -> None:
    """Print current approval mode for mutating operations."""

    try:
        config = load_config()
        printInfo(f"approvalMode={config.approvalMode}")
    except Exception as exc:
        printError(str(exc))


@approvalApp.command("set")
def approvalSet(mode: ApprovalMode = typer.Argument(..., help="interactive | auto-approve | deny")) -> None:
    """Set approval mode to support interactive or batch execution flows."""

    try:
        config = load_config()
        config.approvalMode = mode
        save_config(config)
        printInfo(f"approvalMode set to {mode}")
    except Exception as exc:
        printError(str(exc))


@sessionsApp.command("list")
def listSessions(limit: int = typer.Option(20, "--limit", help="Maximum sessions to display")) -> None:
    """List recent conversation sessions from persistent memory."""

    try:
        config = load_config()
        memoryService = _buildMemoryService(config)
        sessions = memoryService.listSessions(limit=limit)
        if not sessions:
            printError("No sessions found in memory.")
            printQuickTip("Run 'e-cli ask' to create and persist a conversation session.")
            return

        for index, sessionSummary in enumerate(sessions, start=1):
            printInfo(
                f"[{index}] {sessionSummary.sessionId} | "
                f"messages={sessionSummary.messageCount} | "
                f"last={sessionSummary.lastCreatedAt}"
            )
    except Exception as exc:
        printError(str(exc))


@sessionsApp.command("show")
def showSession(
    sessionId: str = typer.Option("", "--session-id", help="Session id to inspect"),
    limit: int = typer.Option(20, "--limit", help="Maximum messages to display"),
) -> None:
    """Show conversation messages for one session id."""

    try:
        config = load_config()
        sessionIdText = sessionId if isinstance(sessionId, str) else ""
        effectiveSessionId = sessionIdText.strip() or config.lastSessionId
        if not effectiveSessionId:
            printError("No session id provided and no last session available.")
            printQuickTip("Provide --session-id or run 'e-cli ask' first.")
            return

        memoryService = _buildMemoryService(config)
        entries = memoryService.loadEntries(sessionId=effectiveSessionId, limit=limit)
        if not entries:
            printError(f"No messages found for session: {effectiveSessionId}")
            return

        printInfo(f"Session: {effectiveSessionId}")
        for entry in entries:
            contentPreview = entry.content if len(entry.content) <= 240 else entry.content[:240] + "..."
            printInfo(f"[{entry.createdAt}] {entry.role}: {contentPreview}")
    except Exception as exc:
        printError(str(exc))


@sessionsApp.command("continue")
def continueSession(
    prompt: str = typer.Argument(..., help="Task prompt to continue an existing session"),
    sessionId: str = typer.Option("", "--session-id", help="Session id to continue"),
    last: bool = typer.Option(False, "--last", help="Continue the last active session"),
) -> None:
    """Continue a prior session by reusing a selected or remembered session id."""

    try:
        config = load_config()
        sessionIdText = sessionId if isinstance(sessionId, str) else ""
        effectiveSessionId = sessionIdText.strip()
        if not effectiveSessionId and last:
            effectiveSessionId = config.lastSessionId
        if not effectiveSessionId:
            printError("No session selected. Use --session-id or --last.")
            printQuickTip("Run 'e-cli sessions list' to find an id, then continue it.")
            return

        ask(prompt=prompt, sessionId=effectiveSessionId)
    except Exception as exc:
        printError(str(exc))


@toolsApp.command("list")
def listTools() -> None:
    """List available tools and their policy posture under current safety config."""

    try:
        config = load_config()
        policy = _buildSafetyPolicy(config)
        rows = _policySummaryRows(policy)
        for toolName, allowed, reason in rows:
            status = "allowed" if allowed else "blocked"
            printInfo(f"{toolName}: {status} ({reason})")
        printQuickTip("Use 'e-cli tools run' to validate tool execution before full agent runs.")
    except Exception as exc:
        printError(str(exc))


@toolsApp.command("run")
def runTool(
    tool: str = typer.Option(..., "--tool", help="Tool name: shell | file.read | file.write"),
    command: str = typer.Option("", "--command", help="Shell command for --tool shell"),
    path: str = typer.Option("", "--path", help="Target path for file tools"),
    content: str = typer.Option("", "--content", help="Content for --tool file.write"),
    reason: str = typer.Option("manual tool run", "--reason", help="Reason annotation for policy checks"),
) -> None:
    """Run one tool call through policy and router for manual diagnostics."""

    try:
        config = load_config()
        policy = _buildSafetyPolicy(config)

        normalizedTool = tool.strip().lower()
        if normalizedTool not in {"shell", "file.read", "file.write"}:
            printError("Unsupported tool. Use shell, file.read, or file.write.")
            return

        toolCall = ToolCall(
            tool=normalizedTool,
            command=command or None,
            path=path or None,
            content=content or None,
            reason=reason,
        )
        decision = policy.evaluate(toolCall)
        if not decision.allowed:
            printError(f"Action blocked by policy: {decision.reason}")
            return

        if decision.requiresApproval:
            approved = requestApprovalWithMode(toolCall, decision.reason, config.approvalMode)
            if not approved:
                printError("Action denied by approval mode.")
                return

        router = ToolRouter(workspaceRoot=Path.cwd())
        result = router.execute(toolCall=toolCall, timeoutSeconds=config.timeoutSeconds)
        if result.ok:
            printInfo(result.output)
        else:
            printError(result.output)
    except Exception as exc:
        printError(str(exc))


@configApp.command("show")
def showConfig() -> None:
    """Display active configuration values with safe redaction guidance."""

    try:
        config = load_config()
        printInfo(f"provider={config.provider}")
        printInfo(f"model={config.model or '(not set)'}")
        printInfo(f"endpoint={config.endpoint}")
        printInfo(f"safeMode={config.safeMode}")
        printInfo(f"approvalMode={config.approvalMode}")
        printInfo(f"memoryPath={config.memoryPath}")
        printInfo(f"lastSessionId={config.lastSessionId or '(none)'}")
        printInfo(f"maxTurns={config.maxTurns}")
        printInfo(f"timeoutSeconds={config.timeoutSeconds}")
        printQuickTip("Use 'e-cli config set --help' to update one or more values.")
    except Exception as exc:
        printError(str(exc))


@configApp.command("set")
def setConfig(
    provider: ProviderType | None = typer.Option(None, "--provider", help="ollama | lmstudio | vllm"),
    model: str = typer.Option("", "--model", help="Model name/id"),
    endpoint: str = typer.Option("", "--endpoint", help="Provider endpoint URL"),
    safeMode: bool | None = typer.Option(None, "--safe-mode", help="Enable/disable safe mode"),
    approvalMode: ApprovalMode | None = typer.Option(None, "--approval-mode", help="interactive | auto-approve | deny"),
    memoryPath: str = typer.Option("", "--memory-path", help="SQLite memory DB path"),
    maxTurns: int | None = typer.Option(None, "--max-turns", help="Maximum agent turns per ask"),
    timeoutSeconds: int | None = typer.Option(None, "--timeout-seconds", help="Model/tool timeout in seconds"),
) -> None:
    """Update one or more persisted configuration values in a single command."""

    try:
        config = load_config()
        changedFields: list[str] = []
        modelText = model if isinstance(model, str) else ""
        endpointText = endpoint if isinstance(endpoint, str) else ""
        memoryPathText = memoryPath if isinstance(memoryPath, str) else ""
        safeModeValue = safeMode if isinstance(safeMode, bool) else None
        approvalModeValue = approvalMode if isinstance(approvalMode, str) else None

        if provider is not None:
            config.provider = provider
            changedFields.append("provider")
        if modelText.strip():
            config.model = modelText.strip()
            changedFields.append("model")
        if endpointText.strip():
            config.endpoint = endpointText.strip()
            changedFields.append("endpoint")
        if safeModeValue is not None:
            config.safeMode = safeModeValue
            changedFields.append("safeMode")
        if approvalModeValue is not None:
            config.approvalMode = approvalModeValue
            changedFields.append("approvalMode")
        if memoryPathText.strip():
            config.memoryPath = memoryPathText.strip()
            changedFields.append("memoryPath")
        if maxTurns is not None:
            if maxTurns < 1:
                printError("maxTurns must be >= 1")
                return
            config.maxTurns = maxTurns
            changedFields.append("maxTurns")
        if timeoutSeconds is not None:
            if timeoutSeconds < 1:
                printError("timeoutSeconds must be >= 1")
                return
            config.timeoutSeconds = timeoutSeconds
            changedFields.append("timeoutSeconds")

        if not changedFields:
            printError("No changes specified. Provide at least one --option to update.")
            return

        save_config(config)
        printInfo(f"Updated config fields: {', '.join(changedFields)}")
    except Exception as exc:
        printError(str(exc))
