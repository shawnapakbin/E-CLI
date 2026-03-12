"""Tool routing layer that dispatches validated tool calls to concrete tool implementations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from e_cli.agent.protocol import ToolCall, ToolResult
from e_cli.tools.browser_tool import BrowserTool
from e_cli.tools.curl_tool import CurlTool
from e_cli.tools.file_tool import FileTool
from e_cli.tools.git_tool import GitTool
from e_cli.tools.http_tool import HttpTool
from e_cli.tools.rag_tool import RagTool
from e_cli.tools.shell_tool import ShellTool
from e_cli.tools.ssh_tool import SshTool


@dataclass(slots=True)
class ToolRouter:
    """Coordinates shell and file tools behind a single dispatch contract."""

    workspaceRoot: Path
    memoryDbPath: Path | None = None
    ragCorpusDefault: str = "combined"
    ragTopK: int = 5

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

            return ToolResult(ok=False, output=f"Unknown tool: {toolCall.tool}")
        except Exception as exc:
            return ToolResult(ok=False, output=f"Tool router error: {exc}")
