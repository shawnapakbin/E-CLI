"""CLI command surface for E-CLI operations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
import uuid

import typer

from e_cli.agent.loop import AgentLoop
from e_cli.agent.protocol import ToolCall
from e_cli.config import ApprovalMode, AppConfig, ProviderType, RagCorpus, get_app_dir, load_config, save_config
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


@app.callback(invoke_without_command=True)
def rootCallback(ctx: typer.Context) -> None:
    """Start interactive chat when no explicit subcommand is provided."""

    if ctx.invoked_subcommand is None:
        chat()


@dataclass(frozen=True)
class ModelSelectionOption:
    """Represents one selectable model candidate from endpoint discovery."""

    provider: ProviderType
    endpoint: str
    model: str


def _persistModelSelection(config: AppConfig, selected: ModelSelectionOption) -> None:
    """Persist one selected model option to active configuration."""

    config.provider = selected.provider
    config.endpoint = selected.endpoint
    config.model = selected.model
    save_config(config)


def _chooseModelFromOptions(config: AppConfig, options: list[ModelSelectionOption], index: int = -1) -> bool:
    """Interactively or directly select a model option and persist it."""

    selectedIndex = index
    if selectedIndex < 1 or selectedIndex > len(options):
        userInput = input(f"Select model index [1-{len(options)}]: ").strip()
        selectedIndex = int(userInput)
    if selectedIndex < 1 or selectedIndex > len(options):
        printError("Invalid model selection index.")
        return False

    selected = options[selectedIndex - 1]
    _persistModelSelection(config, selected)
    printInfo(f"Selected {selected.provider}:{selected.model} at {selected.endpoint}")
    return True


def _collectModelOptions(config: AppConfig) -> list[ModelSelectionOption]:
    """Discover and flatten provider/model combinations for interactive selection."""

    try:
        discoveredEndpoints: list[DiscoveredEndpoint] = ModelDiscovery.discover()
        options: list[ModelSelectionOption] = []
        for endpoint in discoveredEndpoints:
            try:
                modelClient = _createConfiguredModelClient(config, provider=endpoint.provider, endpoint=endpoint.endpoint)
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


def _createConfiguredModelClient(config: AppConfig, provider: ProviderType, endpoint: str):
    """Create a model client using persisted inference parameters."""

    return create_model_client(
        provider=provider,
        endpoint=endpoint,
        modelParameters=config.modelParameters(),
    )


def _parseProviderOption(rawValue: str) -> bool | int | float | str:
    """Parse a CLI provider option value into a scalar JSON-compatible type."""

    lowered = rawValue.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(rawValue)
    except ValueError:
        pass
    try:
        return float(rawValue)
    except ValueError:
        return rawValue


def _resolveSessionId(config: AppConfig, sessionId: str = "", last: bool = False) -> str:
    """Resolve an explicit or remembered session id for session commands."""

    sessionIdText = sessionId if isinstance(sessionId, str) else ""
    if sessionIdText.strip():
        return sessionIdText.strip()
    if last:
        return config.lastSessionId
    return config.lastSessionId


def _readChatInput(promptText: str) -> str:
    """Read one chat line with terminal editing/history when available."""

    try:
        if sys.stdin.isatty() and sys.stdout.isatty():
            try:
                from prompt_toolkit import prompt as promptToolkitPrompt
                from prompt_toolkit.history import FileHistory

                historyPath = get_app_dir() / "chat_history.txt"
                historyPath.parent.mkdir(parents=True, exist_ok=True)
                return promptToolkitPrompt(promptText, history=FileHistory(str(historyPath)))
            except Exception:
                pass
        return input(promptText)
    except Exception:
        return input(promptText)


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


def _buildAgentLoop(config: AppConfig) -> AgentLoop:
    """Create a fully configured agent loop from persisted configuration."""

    modelClient = _createConfiguredModelClient(config, provider=config.provider, endpoint=config.endpoint)
    memoryService = _buildMemoryService(config)
    safetyPolicy = _buildSafetyPolicy(config)
    return AgentLoop(
        modelClient=modelClient,
        modelName=config.model,
        memoryService=memoryService,
        safetyPolicy=safetyPolicy,
        workspaceRoot=Path.cwd(),
        timeoutSeconds=config.timeoutSeconds,
        maxTurns=config.maxTurns,
        approvalMode=config.approvalMode,
        streamingEnabled=config.streamingEnabled,
        conversationTokenBudget=config.conversationTokenBudget,
        conversationSummaryBudget=config.conversationSummaryBudget,
        memoryDbPath=config.memoryPath,
        ragCorpusDefault=config.ragCorpusDefault,
        ragTopK=config.ragTopK,
    )


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
        gitDiffDecision = policy.evaluate(ToolCall(tool="git.diff", path="README.md"))
        rows.append(("git.diff", gitDiffDecision.allowed, gitDiffDecision.reason))
        httpGetDecision = policy.evaluate(ToolCall(tool="http.get", url="https://example.com"))
        rows.append(("http.get", httpGetDecision.allowed, httpGetDecision.reason))
        browserDecision = policy.evaluate(ToolCall(tool="browser", url="https://example.com"))
        rows.append(("browser", browserDecision.allowed, browserDecision.reason))
        sshDecision = policy.evaluate(ToolCall(tool="ssh", host="example-host", command="uname -a"))
        rows.append(("ssh", sshDecision.allowed, sshDecision.reason))
        curlDecision = policy.evaluate(ToolCall(tool="curl", url="https://example.com", method="GET"))
        rows.append(("curl", curlDecision.allowed, curlDecision.reason))
        ragDecision = policy.evaluate(ToolCall(tool="rag.search", query="agent loop", corpus="combined"))
        rows.append(("rag.search", ragDecision.allowed, ragDecision.reason))
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

        agentLoop = _buildAgentLoop(config)

        sessionIdText = sessionId if isinstance(sessionId, str) else ""
        effectiveSessionId = sessionIdText.strip() or config.lastSessionId or str(uuid.uuid4())
        finalAnswer = agentLoop.run(userPrompt=prompt, sessionId=effectiveSessionId)
        config.lastSessionId = effectiveSessionId
        save_config(config)
        if not getattr(agentLoop, "lastAssistantResponseStreamed", False):
            printInfo(finalAnswer)
        printQuickTip(f"Session id: {effectiveSessionId}")
    except Exception as exc:
        printError(str(exc))


@app.command("chat")
def chat(
    sessionId: str = typer.Option("", "--session-id", help="Resume or set conversation session id"),
    last: bool = typer.Option(False, "--last", help="Resume the last active session id"),
) -> None:
    """Start an interactive multi-turn chat session."""

    try:
        config = load_config()
        if not config.model:
            printError("No model selected. Run 'e-cli models list' and then 'e-cli models use'.")
            return

        agentLoop = _buildAgentLoop(config)
        sessionIdText = sessionId if isinstance(sessionId, str) else ""
        effectiveSessionId = sessionIdText.strip() or (config.lastSessionId if last else "") or str(uuid.uuid4())

        printQuickTip("Interactive mode started. Use /help for commands.")
        printQuickTip(f"Session id: {effectiveSessionId}")

        while True:
            try:
                userPrompt = _readChatInput("~~> ").strip()
            except EOFError:
                printQuickTip("Interactive chat ended (EOF).")
                break
            except KeyboardInterrupt:
                printQuickTip("Interactive chat interrupted.")
                break

            if not userPrompt:
                continue

            normalized = userPrompt.lower()
            if normalized in {"/exit", "/quit"}:
                printQuickTip("Interactive chat ended.")
                break
            if normalized == "/help":
                printInfo("/help    Show chat commands")
                printInfo("/session Show current session id")
                printInfo("/new     Start a new session id")
                printInfo("/exit    End interactive chat")
                continue
            if normalized == "/session":
                printInfo(f"sessionId={effectiveSessionId}")
                continue
            if normalized == "/new":
                effectiveSessionId = str(uuid.uuid4())
                printQuickTip(f"New session id: {effectiveSessionId}")
                continue

            finalAnswer = agentLoop.run(userPrompt=userPrompt, sessionId=effectiveSessionId)
            config.lastSessionId = effectiveSessionId
            save_config(config)
            if not getattr(agentLoop, "lastAssistantResponseStreamed", False):
                printInfo(finalAnswer)
    except Exception as exc:
        printError(str(exc))


@app.command("doctor")
def doctor(
    interactive: bool = typer.Option(None, "--interactive", "-i", help="Force interactive menu mode"),
    batch: bool = typer.Option(False, "--batch", "-b", help="Force batch/CLI mode"),
) -> None:
    """Run local diagnostics for config, model connectivity, safety, and memory."""

    try:
        config = load_config()

        # Determine if we should use menu mode
        use_menu = interactive if interactive is not None else (config.interactiveMenus and not batch)

        # If interactive mode and in TTY, show menu
        if use_menu and sys.stdin.isatty() and sys.stdout.isatty():
            from e_cli.menus.doctor_menu import create_doctor_menu
            from e_cli.ui.menu import MenuSession

            menu = create_doctor_menu()
            session = MenuSession(root_menu=menu)
            session.run()
            return

        # Otherwise, run traditional diagnostic checks
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
        checks.append(("streaming", True, f"enabled={config.streamingEnabled}"))
        checks.append(("memory.tokens", True, f"budget={config.conversationTokenBudget}"))

        discovered = ModelDiscovery.discover()
        checks.append(("discovery", bool(discovered), f"reachable endpoints={len(discovered)}"))

        if modelConfigured:
            try:
                modelClient = _createConfiguredModelClient(config, provider=config.provider, endpoint=config.endpoint)
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
def listModels(
    choose: bool = typer.Option(False, "--choose", help="Pick a model index from the discovered list"),
) -> None:
    """Discover model endpoints, print a numbered menu, and optionally choose one."""

    try:
        config = load_config()
        options = _collectModelOptions(config)
        if not options:
            printError("No model endpoints discovered.")
            printQuickTip("Start Ollama, LM Studio server, or vLLM and try again.")
            return

        for optionIndex, option in enumerate(options, start=1):
            printInfo(f"[{optionIndex}] {option.provider} @ {option.endpoint} -> {option.model}")

        if choose:
            _chooseModelFromOptions(config, options)
        else:
            printQuickTip("Run 'e-cli models list --choose' to select from this menu now.")
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

        _chooseModelFromOptions(config, options, index=index)
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

        modelClient = _createConfiguredModelClient(config, provider=config.provider, endpoint=config.endpoint)
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
        effectiveSessionId = _resolveSessionId(config=config, sessionId=sessionId)
        if not effectiveSessionId:
            printError("No session id provided and no last session available.")
            printQuickTip("Provide --session-id or run 'e-cli ask' first.")
            return

        memoryService = _buildMemoryService(config)
        entries = memoryService.loadEntries(sessionId=effectiveSessionId, limit=limit)
        summary = memoryService.getConversationSummary(sessionId=effectiveSessionId)
        if not entries:
            if summary is None:
                printError(f"No messages found for session: {effectiveSessionId}")
                return
            printInfo(f"Session: {effectiveSessionId}")
            printInfo(
                f"Compacted summary covers through entry #{summary.coveredUntilId} | updated={summary.updatedAt}"
            )
            printInfo(summary.content)
            return

        printInfo(f"Session: {effectiveSessionId}")
        if summary is not None:
            printInfo(f"Compacted summary covers through entry #{summary.coveredUntilId} | updated={summary.updatedAt}")
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


@sessionsApp.command("audit")
def showSessionAudit(
    sessionId: str = typer.Option("", "--session-id", help="Session id to inspect"),
    limit: int = typer.Option(20, "--limit", help="Maximum audit events to display"),
) -> None:
    """Show persisted audit events for one session id."""

    try:
        config = load_config()
        effectiveSessionId = _resolveSessionId(config=config, sessionId=sessionId)
        if not effectiveSessionId:
            printError("No session id provided and no last session available.")
            printQuickTip("Provide --session-id or run 'e-cli ask' first.")
            return

        memoryService = _buildMemoryService(config)
        auditEvents = memoryService.listAuditEvents(sessionId=effectiveSessionId, limit=limit)
        if not auditEvents:
            printError(f"No audit events found for session: {effectiveSessionId}")
            return

        printInfo(f"Audit: {effectiveSessionId}")
        for event in auditEvents:
            detailPreview = event.details if len(event.details) <= 160 else event.details[:160] + "..."
            printInfo(
                f"[{event.createdAt}] {event.action} {event.tool} | "
                f"status={event.status} | approved={event.approved} | {detailPreview}"
            )
    except Exception as exc:
        printError(str(exc))


@sessionsApp.command("compact")
def compactSession(
    sessionId: str = typer.Option("", "--session-id", help="Session id to compact"),
    last: bool = typer.Option(False, "--last", help="Compact the last active session"),
    keepRecent: int = typer.Option(8, "--keep-recent", help="Minimum number of recent raw messages to keep"),
    targetTokens: int = typer.Option(0, "--target-tokens", help="Approximate token budget for retained raw messages; 0 uses current config defaults"),
    dryRun: bool = typer.Option(False, "--dry-run", help="Preview compaction without changing stored session data"),
    replaceExistingSummary: bool = typer.Option(False, "--replace-existing-summary", help="Discard any existing persisted summary and rebuild from raw retained history"),
) -> None:
    """Compact older session history into a stored summary and prune raw entries."""

    try:
        config = load_config()
        sessionIdText = sessionId if isinstance(sessionId, str) else ""
        lastValue = last if isinstance(last, bool) else False
        keepRecentValue = keepRecent if isinstance(keepRecent, int) and not isinstance(keepRecent, bool) else 8
        targetTokensValue = targetTokens if isinstance(targetTokens, int) and not isinstance(targetTokens, bool) else 0
        dryRunValue = dryRun if isinstance(dryRun, bool) else False
        replaceExistingSummaryValue = replaceExistingSummary if isinstance(replaceExistingSummary, bool) else False

        effectiveSessionId = _resolveSessionId(config=config, sessionId=sessionIdText, last=lastValue)
        if not effectiveSessionId:
            printError("No session selected. Use --session-id or --last.")
            printQuickTip("Run 'e-cli sessions list' to find an id, then compact it.")
            return

        memoryService = _buildMemoryService(config)
        effectiveTargetTokens = targetTokensValue if targetTokensValue > 0 else max(
            400,
            config.conversationTokenBudget - config.conversationSummaryBudget,
        )
        result = memoryService.compactSession(
            sessionId=effectiveSessionId,
            keepRecent=keepRecentValue,
            targetTokens=effectiveTargetTokens,
            dryRun=dryRunValue,
            replaceExistingSummary=replaceExistingSummaryValue,
        )

        if result.compactedEntryCount == 0:
            printInfo(
                f"No compaction applied for {effectiveSessionId}; retained {result.retainedEntryCount} message(s)."
            )
            return

        modeLabel = "Dry run" if result.dryRun else "Compacted"
        printInfo(
            f"{modeLabel} {effectiveSessionId}: compacted={result.compactedEntryCount}, retained={result.retainedEntryCount}, estimatedTokens={result.estimatedTokensCompacted}"
        )
        printInfo(
            f"coveredUntilId={result.coveredUntilId} | deleted={result.deletedEntryCount} | original={result.originalEntryCount}"
        )

        if not dryRunValue:
            memoryService.appendAuditEvent(
                sessionId=effectiveSessionId,
                action="session.compact",
                tool="memory",
                approved=True,
                status="ok",
                reason="manual compaction",
                details=(
                    f"compacted={result.compactedEntryCount};retained={result.retainedEntryCount};"
                    f"deleted={result.deletedEntryCount};coveredUntilId={result.coveredUntilId};"
                    f"estimatedTokens={result.estimatedTokensCompacted}"
                ),
            )
            if config.lastSessionId != effectiveSessionId:
                config.lastSessionId = effectiveSessionId
                save_config(config)
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
        printQuickTip("Use 'e-cli tools run --tool shell --command \"echo hello\"' to validate tool execution before full agent runs.")
    except Exception as exc:
        printError(str(exc))


@toolsApp.command("run")
def runTool(
    tool: str = typer.Option(
        ...,
        "--tool",
        help="Tool name: shell | file.read | file.write | git.diff | http.get | browser | ssh | curl | rag.search",
    ),
    command: str = typer.Option("", "--command", help="Shell command for --tool shell"),
    path: str = typer.Option("", "--path", help="Target path for file tools"),
    url: str = typer.Option("", "--url", help="Target URL for --tool http.get | browser | curl"),
    content: str = typer.Option("", "--content", help="Content for --tool file.write"),
    method: str = typer.Option("GET", "--method", help="HTTP method for --tool curl"),
    header: list[str] = typer.Option([], "--header", help="Header for --tool curl in key=value format"),
    host: str = typer.Option("", "--host", help="SSH host for --tool ssh"),
    user: str = typer.Option("", "--user", help="SSH user for --tool ssh"),
    port: int = typer.Option(22, "--port", help="SSH port for --tool ssh"),
    identityFile: str = typer.Option("", "--identity-file", help="SSH identity file for --tool ssh"),
    query: str = typer.Option("", "--query", help="Search query for --tool rag.search"),
    corpus: RagCorpus | None = typer.Option(None, "--corpus", help="Corpus for --tool rag.search: session | workspace | combined"),
    topK: int | None = typer.Option(None, "--top-k", help="Result count for --tool rag.search (1-10)"),
    reason: str = typer.Option("manual tool run", "--reason", help="Reason annotation for policy checks"),
) -> None:
    """Run one tool call through policy and router for manual diagnostics."""

    try:
        config = load_config()
        policy = _buildSafetyPolicy(config)

        normalizedTool = tool.strip().lower()
        supportedTools = {"shell", "file.read", "file.write", "git.diff", "http.get", "browser", "ssh", "curl", "rag.search"}
        if normalizedTool not in supportedTools:
            printError("Unsupported tool. Use shell, file.read, file.write, git.diff, http.get, browser, ssh, curl, or rag.search.")
            return

        if topK is not None and (topK < 1 or topK > 10):
            printError("topK must be between 1 and 10")
            return

        parsedHeaders: dict[str, str] = {}
        for rawHeader in header:
            if "=" not in rawHeader:
                printError("Headers must use key=value format.")
                return
            key, value = rawHeader.split("=", 1)
            keyText = key.strip()
            if not keyText:
                printError("Header key cannot be empty.")
                return
            parsedHeaders[keyText] = value.strip()

        toolCall = ToolCall(
            tool=normalizedTool,
            command=command or None,
            path=path or None,
            url=url or None,
            content=content or None,
            method=method or None,
            headers=parsedHeaders or None,
            host=host or None,
            user=user or None,
            port=port if port > 0 else None,
            identityFile=identityFile or None,
            query=query or None,
            corpus=corpus,
            topK=topK,
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

        router = ToolRouter(
            workspaceRoot=Path.cwd(),
            memoryDbPath=Path(config.memoryPath).expanduser() if config.memoryPath else None,
            ragCorpusDefault=config.ragCorpusDefault,
            ragTopK=config.ragTopK,
        )
        result = router.execute(toolCall=toolCall, timeoutSeconds=config.timeoutSeconds)
        try:
            memoryService = _buildMemoryService(config)
            memoryService.appendAuditEvent(
                sessionId=config.lastSessionId or "manual",
                action="manual.tool.execute",
                tool=normalizedTool,
                approved=result.ok,
                status="ok" if result.ok else "error",
                reason=reason,
                details=result.output,
            )
        except Exception:
            pass
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
        printInfo(f"streamingEnabled={config.streamingEnabled}")
        printInfo(f"conversationTokenBudget={config.conversationTokenBudget}")
        printInfo(f"conversationSummaryBudget={config.conversationSummaryBudget}")
        printInfo(f"temperature={config.temperature}")
        printInfo(f"topP={config.topP}")
        printInfo(f"maxOutputTokens={config.maxOutputTokens}")
        printInfo(f"ragCorpusDefault={config.ragCorpusDefault}")
        printInfo(f"ragTopK={config.ragTopK}")
        printInfo(f"providerOptions={json.dumps(config.providerOptions, sort_keys=True)}")
        printQuickTip("Use 'e-cli config set --help' to update one or more values.")
    except Exception as exc:
        printError(str(exc))


@configApp.command("set")
def setConfig(
    provider: ProviderType | None = typer.Option(None, "--provider", help="ollama | lmstudio | vllm"),
    model: str = typer.Option("", "--model", help="Model name/id"),
    endpoint: str = typer.Option("", "--endpoint", help="Provider endpoint URL"),
    safeMode: bool | None = typer.Option(
        None,
        "--safe-mode/--no-safe-mode",
        help="Enable/disable safe mode",
    ),
    approvalMode: ApprovalMode | None = typer.Option(None, "--approval-mode", help="interactive | auto-approve | deny"),
    memoryPath: str = typer.Option("", "--memory-path", help="SQLite memory DB path"),
    maxTurns: int | None = typer.Option(None, "--max-turns", help="Maximum agent turns per ask"),
    timeoutSeconds: int | None = typer.Option(None, "--timeout-seconds", help="Model/tool timeout in seconds"),
    streamingEnabled: bool | None = typer.Option(
        None,
        "--streaming-enabled/--no-streaming-enabled",
        help="Enable/disable streaming model output",
    ),
    conversationTokenBudget: int | None = typer.Option(None, "--conversation-token-budget", help="Approximate token budget for recalled session context"),
    conversationSummaryBudget: int | None = typer.Option(None, "--conversation-summary-budget", help="Approximate token budget reserved for summary context"),
    temperature: float | None = typer.Option(None, "--temperature", help="Sampling temperature for model responses"),
    topP: float | None = typer.Option(None, "--top-p", help="Nucleus sampling parameter for model responses"),
    maxOutputTokens: int | None = typer.Option(None, "--max-output-tokens", help="Maximum tokens to generate when supported by the provider"),
    ragCorpusDefault: RagCorpus | None = typer.Option(None, "--rag-corpus-default", help="Default corpus for rag.search: session | workspace | combined"),
    ragTopK: int | None = typer.Option(None, "--rag-top-k", help="Default result count for rag.search (1-10)"),
    providerOption: list[str] | None = typer.Option(None, "--provider-option", help="Provider-specific option as key=value; repeatable"),
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
        maxTurnsValue = maxTurns if isinstance(maxTurns, int) and not isinstance(maxTurns, bool) else None
        timeoutSecondsValue = timeoutSeconds if isinstance(timeoutSeconds, int) and not isinstance(timeoutSeconds, bool) else None
        streamingEnabledValue = streamingEnabled if isinstance(streamingEnabled, bool) else None
        conversationTokenBudgetValue = conversationTokenBudget if isinstance(conversationTokenBudget, int) and not isinstance(conversationTokenBudget, bool) else None
        conversationSummaryBudgetValue = conversationSummaryBudget if isinstance(conversationSummaryBudget, int) and not isinstance(conversationSummaryBudget, bool) else None
        temperatureValue = float(temperature) if isinstance(temperature, int | float) and not isinstance(temperature, bool) else None
        topPValue = float(topP) if isinstance(topP, int | float) and not isinstance(topP, bool) else None
        maxOutputTokensValue = maxOutputTokens if isinstance(maxOutputTokens, int) and not isinstance(maxOutputTokens, bool) else None
        ragCorpusDefaultValue = ragCorpusDefault if isinstance(ragCorpusDefault, str) else None
        ragTopKValue = ragTopK if isinstance(ragTopK, int) and not isinstance(ragTopK, bool) else None
        providerOptionValues = providerOption if isinstance(providerOption, list) else []

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
        if maxTurnsValue is not None:
            if maxTurnsValue < 1:
                printError("maxTurns must be >= 1")
                return
            config.maxTurns = maxTurnsValue
            changedFields.append("maxTurns")
        if timeoutSecondsValue is not None:
            if timeoutSecondsValue < 1:
                printError("timeoutSeconds must be >= 1")
                return
            config.timeoutSeconds = timeoutSecondsValue
            changedFields.append("timeoutSeconds")
        if streamingEnabledValue is not None:
            config.streamingEnabled = streamingEnabledValue
            changedFields.append("streamingEnabled")
        if conversationTokenBudgetValue is not None:
            if conversationTokenBudgetValue < 256:
                printError("conversationTokenBudget must be >= 256")
                return
            config.conversationTokenBudget = conversationTokenBudgetValue
            changedFields.append("conversationTokenBudget")
        if conversationSummaryBudgetValue is not None:
            if conversationSummaryBudgetValue < 128:
                printError("conversationSummaryBudget must be >= 128")
                return
            config.conversationSummaryBudget = conversationSummaryBudgetValue
            changedFields.append("conversationSummaryBudget")
        if temperatureValue is not None:
            config.temperature = temperatureValue
            changedFields.append("temperature")
        if topPValue is not None:
            if topPValue <= 0:
                printError("topP must be > 0")
                return
            config.topP = topPValue
            changedFields.append("topP")
        if maxOutputTokensValue is not None:
            if maxOutputTokensValue < 0:
                printError("maxOutputTokens must be >= 0")
                return
            config.maxOutputTokens = maxOutputTokensValue
            changedFields.append("maxOutputTokens")
        if ragCorpusDefaultValue is not None:
            config.ragCorpusDefault = ragCorpusDefaultValue
            changedFields.append("ragCorpusDefault")
        if ragTopKValue is not None:
            if ragTopKValue < 1 or ragTopKValue > 10:
                printError("ragTopK must be between 1 and 10")
                return
            config.ragTopK = ragTopKValue
            changedFields.append("ragTopK")
        if providerOptionValues:
            updatedOptions = dict(config.providerOptions)
            for rawOption in providerOptionValues:
                if "=" not in rawOption:
                    printError("providerOption must use key=value format")
                    return
                key, rawValue = rawOption.split("=", 1)
                keyText = key.strip()
                if not keyText:
                    printError("providerOption key cannot be empty")
                    return
                updatedOptions[keyText] = _parseProviderOption(rawValue.strip())
            config.providerOptions = updatedOptions
            changedFields.append("providerOptions")

        if not changedFields:
            printError("No changes specified. Provide at least one --option to update.")
            return

        save_config(config)
        printInfo(f"Updated config fields: {', '.join(changedFields)}")
    except Exception as exc:
        printError(str(exc))
