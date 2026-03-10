"""Core multi-step reasoning and tool-calling execution loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from e_cli.agent.protocol import ParsedAgentOutput, parse_tool_call
from e_cli.config import ApprovalMode
from e_cli.memory.service import MemoryService
from e_cli.models.base import ModelClient, ModelMessage
from e_cli.safety.approval import requestApprovalWithMode
from e_cli.safety.policy import SafetyPolicy
from e_cli.tools.router import ToolRouter
from e_cli.ui.messages import printInfo, printQuickTip


SYSTEM_PROMPT = """You are E-CLI, a terminal-native assistant.
Return exactly one JSON object for tool actions.
Supported tools:
- {\"tool\":\"shell\",\"command\":\"...\",\"reason\":\"...\"}
- {\"tool\":\"file.read\",\"path\":\"...\",\"reason\":\"...\"}
- {\"tool\":\"file.write\",\"path\":\"...\",\"content\":\"...\",\"reason\":\"...\"}
- {\"tool\":\"done\",\"reason\":\"...\"}
If no tool is needed, answer in plain text.
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

    def run(self, userPrompt: str, sessionId: str) -> str:
        """Runs the iterative tool-calling loop until completion or turn budget exhaustion."""

        try:
            toolRouter = ToolRouter(workspaceRoot=self.workspaceRoot)
            conversationHistory = self.memoryService.loadConversation(sessionId=sessionId)
            if not conversationHistory:
                conversationHistory = [ModelMessage(role="system", content=SYSTEM_PROMPT)]
            else:
                conversationHistory.insert(0, ModelMessage(role="system", content=SYSTEM_PROMPT))

            conversationHistory.append(ModelMessage(role="user", content=userPrompt))
            self.memoryService.appendMessage(sessionId=sessionId, role="user", content=userPrompt)
            finalAnswer = ""

            for turnIndex in range(self.maxTurns):
                printInfo(f"Turn {turnIndex + 1}/{self.maxTurns}")
                modelResponse = self.modelClient.chat(
                    model_name=self.modelName,
                    messages=conversationHistory,
                    timeout_seconds=self.timeoutSeconds,
                )
                parsedOutput: ParsedAgentOutput = parse_tool_call(modelResponse.content)

                if parsedOutput.toolCall is None:
                    finalAnswer = parsedOutput.assistantMessage
                    conversationHistory.append(ModelMessage(role="assistant", content=finalAnswer))
                    self.memoryService.appendMessage(sessionId=sessionId, role="assistant", content=finalAnswer)
                    break

                if parsedOutput.toolCall.tool == "done":
                    finalAnswer = parsedOutput.toolCall.reason or "Task completed."
                    conversationHistory.append(ModelMessage(role="assistant", content=finalAnswer))
                    self.memoryService.appendMessage(sessionId=sessionId, role="assistant", content=finalAnswer)
                    break

                safetyDecision = self.safetyPolicy.evaluate(parsedOutput.toolCall)
                if not safetyDecision.allowed:
                    toolOutput = f"Action blocked by policy: {safetyDecision.reason}"
                else:
                    approved = True
                    if safetyDecision.requiresApproval:
                        approved = requestApprovalWithMode(
                            parsedOutput.toolCall,
                            safetyDecision.reason,
                            self.approvalMode,
                        )
                    if not approved:
                        toolOutput = "Action denied by user approval gate."
                    else:
                        toolResult = toolRouter.execute(
                            toolCall=parsedOutput.toolCall,
                            timeoutSeconds=self.timeoutSeconds,
                        )
                        toolOutput = toolResult.output

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
