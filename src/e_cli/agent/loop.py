"""Core multi-step reasoning and tool-calling execution loop."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from e_cli.agent.protocol import ParsedAgentOutput, parse_tool_call
from e_cli.config import ApprovalMode
from e_cli.memory.service import MemoryService
from e_cli.models.base import ModelClient, ModelMessage, ModelResponse
from e_cli.models.factory import create_model_client
from e_cli.safety.approval import requestApprovalWithMode
from e_cli.safety.policy import SafetyPolicy
from e_cli.tools.router import ToolRouter
from e_cli.ui.messages import printInfo, printQuickTip, printWarning

if TYPE_CHECKING:
    from e_cli.config import AppConfig

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured error categories
# ---------------------------------------------------------------------------

class AgentError(str, Enum):
    """Distinct failure categories surfaced by the agent loop."""

    PARSE_ERROR = "PARSE_ERROR"
    POLICY_BLOCK = "POLICY_BLOCK"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    TOOL_EXEC_ERROR = "TOOL_EXEC_ERROR"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MEMORY_ERROR = "MEMORY_ERROR"
    MAX_TURNS = "MAX_TURNS"


_RECOVERY_HINTS: dict[AgentError, str] = {
    AgentError.PARSE_ERROR: "Lower temperature or check that the model follows instruction format.",
    AgentError.POLICY_BLOCK: "Run 'e-cli safe-mode status' to review the active policy.",
    AgentError.APPROVAL_DENIED: "Re-run with --approval-mode auto-approve if the action is safe.",
    AgentError.TOOL_EXEC_ERROR: "Run 'e-cli sessions audit --last' to inspect the error details.",
    AgentError.MODEL_TIMEOUT: "Increase timeoutSeconds or restart the model server.",
    AgentError.MEMORY_ERROR: "Run 'e-cli doctor' to inspect memory DB health.",
    AgentError.MAX_TURNS: "Increase maxTurns with 'e-cli config set --max-turns N' or break the task into smaller steps.",
}


# ---------------------------------------------------------------------------
# Dynamic system prompt builder
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: list[str] = [
    '{"tool":"shell","command":"...","reason":"..."}',
    '{"tool":"file.read","path":"...","reason":"..."}',
    '{"tool":"file.write","path":"...","content":"...","reason":"..."}',
    '{"tool":"git.diff","path":"optional","reason":"..."}',
    '{"tool":"http.get","url":"https://...","reason":"..."}',
    '{"tool":"browser","url":"https://...","reason":"..."}',
    '{"tool":"ssh","host":"...","command":"...","reason":"..."}',
    '{"tool":"curl","url":"https://...","method":"GET","reason":"..."}',
    '{"tool":"rag.search","query":"...","corpus":"session|workspace|combined","topK":5,"reason":"..."}',
    '{"tool":"done","reason":"..."}',
]


def build_system_prompt(
    extra_tool_schemas: list[str] | None = None,
    persona: str | None = None,
) -> str:
    """Build the system prompt from the registered tool schema list and optional persona.

    Callers can inject additional tool schemas (e.g. from loaded skills) or override
    the assistant persona for custom task modes such as the setup-helper.
    """

    schemas = list(_TOOL_SCHEMAS)
    if extra_tool_schemas:
        schemas.extend(extra_tool_schemas)

    tool_block = "\n".join(schemas)
    persona_line = persona if persona else "You are E-CLI, a terminal-native assistant with access to tools."

    return (
        f"{persona_line}\n\n"
        "To use a tool, respond with ONLY a JSON object (no code fences):\n"
        f"{tool_block}\n\n"
        "When you receive a [Tool result: ...] message, use it to answer the user and avoid repeating the same tool call.\n"
        "For normal replies, return plain text only.\n"
    )


@dataclass(slots=True)
class AgentLoop:
    """Coordinates model reasoning, policy checks, tool execution, and memory updates."""

    modelClient: ModelClient
    modelName: str
    memoryService: MemoryService
    safetyPolicy: SafetyPolicy
    workspaceRoot: Path
    timeoutSeconds: int
    maxTurns: int
    approvalMode: ApprovalMode
    streamingEnabled: bool
    conversationTokenBudget: int
    conversationSummaryBudget: int
    memoryDbPath: str | None = None
    ragCorpusDefault: str = "combined"
    ragTopK: int = 5
    lastAssistantResponseStreamed: bool = False
    #: Optional persona string injected into the system prompt (e.g. for setup-helper mode).
    persona: str | None = None
    #: Optional extra tool schemas injected by loaded skills.
    extraToolSchemas: list[str] | None = None
    #: Optional app config used for provider fallback chain resolution.
    config: "AppConfig | None" = None

    def _tryConnectProvider(self, client: ModelClient) -> bool:
        """Probe a provider by listing its models; returns True if reachable."""
        try:
            client.list_models(timeout_seconds=min(self.timeoutSeconds, 5))
            return True
        except Exception:
            return False

    def _resolveModelClient(self) -> None:
        """Attempt primary provider; if unreachable, walk fallbackChain in order.

        Mutates ``self.modelClient`` to the first reachable provider found.
        Raises ``RuntimeError`` if all providers in the chain are unreachable.
        """
        if self.config is None:
            return  # No config supplied — skip fallback resolution.

        if self._tryConnectProvider(self.modelClient):
            return  # Primary provider is reachable.

        primary_name = getattr(self.modelClient, "provider_name", "unknown")
        _log.warning("Primary provider '%s' is unreachable; starting fallback chain.", primary_name)
        printWarning(f"Provider '{primary_name}' is unreachable. Trying fallback chain…")

        fallback_chain: list[str] = list(self.config.fallbackChain)
        # Remove the primary provider from the chain to avoid retrying it.
        fallback_chain = [p for p in fallback_chain if p != primary_name]

        for provider_name in fallback_chain:
            _log.warning("Trying fallback provider '%s'.", provider_name)
            printWarning(f"Trying fallback provider '{provider_name}'…")
            try:
                candidate = create_model_client(
                    provider=provider_name,  # type: ignore[arg-type]
                    endpoint=self.config.endpoint,
                    api_key=self.config.anthropicApiKey,
                    modelParameters=self.config.modelParameters(),
                    config=self.config,
                )
                if self._tryConnectProvider(candidate):
                    _log.warning(
                        "Fallback provider '%s' is reachable; switching to it.", provider_name
                    )
                    printWarning(f"Switched to fallback provider '{provider_name}'.")
                    self.modelClient = candidate
                    return
                _log.warning("Fallback provider '%s' is also unreachable.", provider_name)
                printWarning(f"Fallback provider '{provider_name}' is also unreachable.")
            except Exception as exc:
                _log.warning("Fallback provider '%s' failed to initialise: %s", provider_name, exc)
                printWarning(f"Fallback provider '{provider_name}' failed: {exc}")

        raise RuntimeError(
            f"All providers unreachable. Primary: '{primary_name}'. "
            f"Fallback chain tried: {fallback_chain}. "
            "Check that at least one provider server is running."
        )

    def _requestModelResponse(self, conversationHistory: list[ModelMessage]) -> ModelResponse:
        """Request one model response, preferring provider streaming when enabled."""

        if not self.streamingEnabled or not hasattr(self.modelClient, "stream_chat"):
            return self.modelClient.chat(
                model_name=self.modelName,
                messages=conversationHistory,
                timeout_seconds=self.timeoutSeconds,
            )

        try:
            streamingClient = cast(ModelClient, self.modelClient)
            chunks = list(
                streamingClient.stream_chat(
                    model_name=self.modelName,
                    messages=conversationHistory,
                    timeout_seconds=self.timeoutSeconds,
                )
            )
            if chunks:
                # Buffer streamed chunks and parse before printing so tool calls can be labeled.
                return ModelResponse(content="".join(chunks), streamed=False)
        except Exception as exc:
            printInfo(f"Streaming unavailable, falling back to buffered response: {exc}")

        return self.modelClient.chat(
            model_name=self.modelName,
            messages=conversationHistory,
            timeout_seconds=self.timeoutSeconds,
        )

    def _audit(
        self,
        sessionId: str,
        action: str,
        tool: str,
        approved: bool,
        status: str,
        reason: str,
        details: str,
    ) -> None:
        """Persist audit details without letting logging failures break the loop."""

        try:
            self.memoryService.appendAuditEvent(
                sessionId=sessionId,
                action=action,
                tool=tool,
                approved=approved,
                status=status,
                reason=reason,
                details=details[:2000],
            )
        except Exception as auditExc:
            _log.warning("Audit write failed (session %s action %s): %s", sessionId, action, auditExc)
            printWarning(f"Audit record could not be saved: {auditExc}")

    def run(self, userPrompt: str, sessionId: str) -> str:
        """Runs the iterative tool-calling loop until completion or turn budget exhaustion."""

        finalAnswer = ""
        self.lastAssistantResponseStreamed = False

        try:
            self._resolveModelClient()

            toolRouter = ToolRouter(
                workspaceRoot=self.workspaceRoot,
                memoryDbPath=Path(self.memoryDbPath).expanduser() if self.memoryDbPath else None,
                ragCorpusDefault=self.ragCorpusDefault,
                ragTopK=self.ragTopK,
            )

            # Load skills and register their tools into the router.
            try:
                from e_cli.skills.executor import SkillExecutor
                skillExecutor = SkillExecutor(
                    router=toolRouter,
                    safety_policy=self.safetyPolicy,
                )
                skillExecutor.load_all()
                toolRouter.register_skill_executor(skillExecutor)
                skill_tool_schemas = [
                    f'{{"tool":"{t.name}","reason":"..."}}'
                    for t in skillExecutor.registered_tools()
                ]
                if skill_tool_schemas:
                    if self.extraToolSchemas is None:
                        self.extraToolSchemas = skill_tool_schemas
                    else:
                        self.extraToolSchemas = list(self.extraToolSchemas) + skill_tool_schemas
            except Exception as skillExc:
                _log.warning("Failed to load skills: %s", skillExc)
            conversationHistory = self.memoryService.loadConversation(
                sessionId=sessionId,
                maxTokens=self.conversationTokenBudget,
                summaryTokens=self.conversationSummaryBudget,
            )
            systemPrompt = build_system_prompt(
                extra_tool_schemas=self.extraToolSchemas,
                persona=self.persona,
            )
            if not conversationHistory:
                conversationHistory = [ModelMessage(role="system", content=systemPrompt)]
            else:
                conversationHistory.insert(0, ModelMessage(role="system", content=systemPrompt))

            conversationHistory.append(ModelMessage(role="user", content=userPrompt))
            self.memoryService.appendMessage(sessionId=sessionId, role="user", content=userPrompt)

            for turnIndex in range(self.maxTurns):
                printInfo(f"Turn {turnIndex + 1}/{self.maxTurns}")
                modelResponse = self._requestModelResponse(conversationHistory)
                parsedOutput: ParsedAgentOutput = parse_tool_call(modelResponse.content)

                if parsedOutput.toolCall is None:
                    finalAnswer = parsedOutput.assistantMessage
                    self.lastAssistantResponseStreamed = modelResponse.streamed
                    conversationHistory.append(ModelMessage(role="assistant", content=finalAnswer))
                    self.memoryService.appendMessage(sessionId=sessionId, role="assistant", content=finalAnswer)
                    break

                if parsedOutput.toolCall.tool == "done":
                    finalAnswer = parsedOutput.toolCall.reason or "Task completed."
                    self.lastAssistantResponseStreamed = False
                    conversationHistory.append(ModelMessage(role="assistant", content=finalAnswer))
                    self.memoryService.appendMessage(sessionId=sessionId, role="assistant", content=finalAnswer)
                    break

                printInfo(f"AI Thinking: {modelResponse.content.strip()}")

                safetyDecision = self.safetyPolicy.evaluate(parsedOutput.toolCall)
                toolLabel = parsedOutput.toolCall.tool
                if not safetyDecision.allowed:
                    toolOutput = f"Action blocked by policy: {safetyDecision.reason}"
                    self._audit(
                        sessionId=sessionId,
                        action="policy.evaluate",
                        tool=toolLabel,
                        approved=False,
                        status="blocked",
                        reason=safetyDecision.reason,
                        details=toolOutput,
                    )
                else:
                    approved = True
                    if safetyDecision.requiresApproval:
                        approved = requestApprovalWithMode(
                            parsedOutput.toolCall,
                            safetyDecision.reason,
                            self.approvalMode,
                        )
                        self._audit(
                            sessionId=sessionId,
                            action="approval",
                            tool=toolLabel,
                            approved=approved,
                            status="approved" if approved else "denied",
                            reason=safetyDecision.reason,
                            details=parsedOutput.toolCall.model_dump_json(),
                        )
                    if not approved:
                        toolOutput = "Action denied by user approval gate."
                    else:
                        toolResult = toolRouter.execute(
                            toolCall=parsedOutput.toolCall,
                            timeoutSeconds=self.timeoutSeconds,
                        )
                        toolOutput = toolResult.output
                        self._audit(
                            sessionId=sessionId,
                            action="tool.execute",
                            tool=toolLabel,
                            approved=toolResult.ok,
                            status="ok" if toolResult.ok else "error",
                            reason=parsedOutput.toolCall.reason or "",
                            details=toolOutput,
                        )

                toolCallJson = parsedOutput.toolCall.model_dump_json(exclude_none=True)
                toolResultMsg = f"[Tool result: {toolLabel}]\n{toolOutput}"
                conversationHistory.append(ModelMessage(role="assistant", content=toolCallJson))
                conversationHistory.append(ModelMessage(role="user", content=toolResultMsg))
                self.memoryService.appendMessage(sessionId=sessionId, role="assistant", content=toolCallJson)
                self.memoryService.appendMessage(sessionId=sessionId, role="user", content=toolResultMsg)

                printQuickTip("Use 'e-cli safe-mode status' to inspect execution policy.")

            if not finalAnswer:
                hint = _RECOVERY_HINTS[AgentError.MAX_TURNS]
                finalAnswer = f"Reached max turns without explicit completion. Hint: {hint}"
            return finalAnswer
        except TimeoutError as exc:
            hint = _RECOVERY_HINTS[AgentError.MODEL_TIMEOUT]
            raise RuntimeError(
                f"[{AgentError.MODEL_TIMEOUT}] Model request timed out. {hint}"
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:
            # Classify unknown exceptions and surface a recovery hint.
            errorCode = AgentError.TOOL_EXEC_ERROR
            hint = _RECOVERY_HINTS[errorCode]
            raise RuntimeError(
                f"[{errorCode}] Agent loop failed: {exc}. {hint}"
            ) from exc
