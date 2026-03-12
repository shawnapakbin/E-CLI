"""Core multi-step reasoning and tool-calling execution loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from e_cli.agent.protocol import ParsedAgentOutput, parse_tool_call
from e_cli.config import ApprovalMode
from e_cli.memory.service import MemoryService
from e_cli.models.base import ModelClient, ModelMessage, ModelResponse
from e_cli.safety.approval import requestApprovalWithMode
from e_cli.safety.policy import SafetyPolicy
from e_cli.tools.router import ToolRouter
from e_cli.ui.messages import printInfo, printQuickTip, printStream, printStreamBreak


SYSTEM_PROMPT = """You are E-CLI, a terminal-native assistant.

For tool actions:
- Return exactly one JSON object with one of these schemas:
  - {"tool":"shell","command":"...","reason":"..."}
  - {"tool":"file.read","path":"...","reason":"..."}
  - {"tool":"file.write","path":"...","content":"...","reason":"..."}
  - {"tool":"git.diff","path":"optional/path","reason":"..."}
  - {"tool":"http.get","url":"https://...","reason":"..."}
  - {"tool":"done","reason":"..."}

For normal assistant replies (no tool needed):
- Return plain text only.
- Do NOT return JSON.
- Do NOT wrap text in braces.
- Do NOT use code fences.
"""


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
    lastAssistantResponseStreamed: bool = False

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
                for chunk in chunks:
                    printStream(chunk)
                printStreamBreak()
                return ModelResponse(content="".join(chunks), streamed=True)
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
        except Exception:
            return

    def run(self, userPrompt: str, sessionId: str) -> str:
        """Runs the iterative tool-calling loop until completion or turn budget exhaustion."""

        finalAnswer = ""
        self.lastAssistantResponseStreamed = False

        try:
            toolRouter = ToolRouter(workspaceRoot=self.workspaceRoot)
            conversationHistory = self.memoryService.loadConversation(
                sessionId=sessionId,
                maxTokens=self.conversationTokenBudget,
                summaryTokens=self.conversationSummaryBudget,
            )
            if not conversationHistory:
                conversationHistory = [ModelMessage(role="system", content=SYSTEM_PROMPT)]
            else:
                conversationHistory.insert(0, ModelMessage(role="system", content=SYSTEM_PROMPT))

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

                conversationHistory.append(ModelMessage(role="assistant", content=modelResponse.content))
                conversationHistory.append(ModelMessage(role="tool", content=toolOutput))
                self.memoryService.appendMessage(sessionId=sessionId, role="assistant", content=modelResponse.content)
                self.memoryService.appendMessage(sessionId=sessionId, role="tool", content=toolOutput)

                printQuickTip("Use 'e-cli safe-mode status' to inspect execution policy.")

            if not finalAnswer:
                finalAnswer = "Reached max turns without explicit completion."
            return finalAnswer
        except Exception as exc:
            raise RuntimeError(f"Agent loop failed: {exc}") from exc
