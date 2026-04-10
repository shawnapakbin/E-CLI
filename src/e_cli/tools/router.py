"""Tool routing layer that dispatches validated tool calls to concrete tool implementations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from e_cli.agent.protocol import ToolCall, ToolResult
from e_cli.tools.browser_tool import BrowserTool
from e_cli.tools.curl_tool import CurlTool
from e_cli.tools.file_tool import FileTool
from e_cli.tools.git_tool import GitTool
from e_cli.tools.http_tool import HttpTool
from e_cli.tools.playwright_tool import PlaywrightTool
from e_cli.tools.rag_tool import RagTool
from e_cli.tools.shell_tool import ShellTool
from e_cli.tools.ssh_tool import SshTool
from e_cli.tools.system_tool import SystemTool

if TYPE_CHECKING:
    from e_cli.skills.executor import SkillExecutor


@dataclass(slots=True)
class ToolRouter:
    """Coordinates shell and file tools behind a single dispatch contract."""

    workspaceRoot: Path
    memoryDbPath: Path | None = None
    ragCorpusDefault: str = "combined"
    ragTopK: int = 5
    _playwright_tool: PlaywrightTool = field(default_factory=PlaywrightTool, init=False, repr=False)
    _system_tool: SystemTool = field(default_factory=SystemTool, init=False, repr=False)
    # Skill executor registered at session start; None means no skills loaded.
    _skill_executor: "SkillExecutor | None" = field(default=None, init=False, repr=False)

    def register_skill_executor(self, executor: "SkillExecutor") -> None:
        """Register a SkillExecutor so skill tools can be dispatched through this router."""
        self._skill_executor = executor

    def execute(self, toolCall: ToolCall, timeoutSeconds: int) -> ToolResult:
        """Execute one tool call and return a normalized tool result."""

        try:
            if toolCall.tool == "shell":
                if not toolCall.command:
                    return ToolResult(ok=False, output="Missing shell command.")
                shellResult = ShellTool.run(command=toolCall.command, timeout_seconds=timeoutSeconds)
                return ToolResult(
                    ok=shellResult.ok,
                    output=f"exitCode={shellResult.exitCode}\n{shellResult.output}",
                )

            if toolCall.tool == "git.diff":
                gitResult = GitTool(self.workspaceRoot).diff(path=toolCall.path, timeout_seconds=timeoutSeconds)
                return ToolResult(ok=gitResult.ok, output=gitResult.output)

            if toolCall.tool == "http.get":
                if not toolCall.url:
                    return ToolResult(ok=False, output="Missing URL for http.get.")
                httpResult = HttpTool.get(url=toolCall.url, timeout_seconds=timeoutSeconds)
                return ToolResult(ok=httpResult.ok, output=httpResult.output)

            if toolCall.tool == "browser":
                if not toolCall.url:
                    return ToolResult(ok=False, output="Missing URL for browser.")
                browserResult = BrowserTool.open(url=toolCall.url, timeout_seconds=timeoutSeconds)
                return ToolResult(ok=browserResult.ok, output=browserResult.output)

            if toolCall.tool == "browser.playwright":
                action = toolCall.action or ""
                if not action:
                    return ToolResult(ok=False, output="Missing 'action' for browser.playwright.")
                kwargs: dict[str, object] = {}
                if toolCall.url is not None:
                    kwargs["url"] = toolCall.url
                if toolCall.selector is not None:
                    kwargs["selector"] = toolCall.selector
                if toolCall.text is not None:
                    kwargs["text"] = toolCall.text
                if toolCall.path is not None:
                    kwargs["path"] = toolCall.path
                if toolCall.expression is not None:
                    kwargs["expression"] = toolCall.expression
                return asyncio.run(self._playwright_tool.execute(action, **kwargs))

            if toolCall.tool == "ssh":
                sshResult = SshTool.run(
                    host=toolCall.host or "",
                    remote_command=toolCall.command or "",
                    timeout_seconds=timeoutSeconds,
                    user=toolCall.user,
                    port=toolCall.port,
                    identity_file=toolCall.identityFile,
                )
                return ToolResult(
                    ok=sshResult.ok,
                    output=f"exitCode={sshResult.exitCode}\n{sshResult.output}",
                )

            if toolCall.tool == "curl":
                if not toolCall.url:
                    return ToolResult(ok=False, output="Missing URL for curl.")
                curlResult = CurlTool.request(
                    url=toolCall.url,
                    timeout_seconds=timeoutSeconds,
                    method=toolCall.method or "GET",
                    headers=toolCall.headers,
                    content=toolCall.content,
                )
                return ToolResult(ok=curlResult.ok, output=curlResult.output)

            if toolCall.tool == "rag.search":
                query = (toolCall.query or "").strip()
                if not query:
                    return ToolResult(ok=False, output="Missing query for rag.search.")
                ragResult = RagTool.search(
                    query=query,
                    timeout_seconds=timeoutSeconds,
                    workspace_root=self.workspaceRoot,
                    memory_db_path=self.memoryDbPath,
                    corpus=toolCall.corpus or self.ragCorpusDefault,
                    top_k=toolCall.topK or self.ragTopK,
                )
                return ToolResult(ok=ragResult.ok, output=ragResult.output)

            fileTool = FileTool(self.workspaceRoot)
            if toolCall.tool == "file.read":
                if not toolCall.path:
                    return ToolResult(ok=False, output="Missing file path for read.")
                fileResult = fileTool.read(toolCall.path)
                return ToolResult(ok=fileResult.ok, output=fileResult.output)

            if toolCall.tool == "file.write":
                if not toolCall.path:
                    return ToolResult(ok=False, output="Missing file path for write.")
                fileResult = fileTool.write(toolCall.path, toolCall.content or "")
                return ToolResult(ok=fileResult.ok, output=fileResult.output)

            if toolCall.tool == "done":
                return ToolResult(ok=True, output="Task marked complete by model.")

            if toolCall.tool == "system":
                action = toolCall.action or ""
                if not action:
                    return ToolResult(ok=False, output="Missing 'action' for system tool.")
                return self._system_tool.execute(action, **{
                    k: v for k, v in {
                        "pid": toolCall.command,
                        "package": toolCall.content,
                        "lines": toolCall.topK,
                    }.items() if v is not None
                })

            # Delegate to skill executor if one is registered.
            if self._skill_executor is not None:
                skill_tools = {t.name for t in self._skill_executor.registered_tools()}
                if toolCall.tool in skill_tools:
                    args = toolCall.model_dump(exclude_none=True, exclude={"tool"})
                    return self._skill_executor.execute(toolCall.tool, args)

            return ToolResult(ok=False, output=f"Unknown tool: {toolCall.tool}")
        except Exception as exc:
            return ToolResult(ok=False, output=f"Tool router error: {exc}")
