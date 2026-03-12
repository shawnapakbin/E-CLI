"""Tests for model factory routing and tool router dispatch."""

from pathlib import Path

from e_cli.agent.protocol import ToolCall
from e_cli.models.factory import create_model_client
from e_cli.tools.router import ToolRouter


def test_factory_creates_ollama_client() -> None:
    """Ensures provider factory returns correct implementation for Ollama."""

    client = create_model_client(provider="ollama", endpoint="http://127.0.0.1:11434")
    assert client.provider_name == "ollama"


def test_factory_creates_lmstudio_client() -> None:
    """Ensures provider factory returns LM Studio OpenAI-compatible client."""

    client = create_model_client(provider="lmstudio", endpoint="http://127.0.0.1:1234")
    assert client.provider_name == "lmstudio"


def test_router_done_tool() -> None:
    """Ensures done tool branch returns completion result."""

    router = ToolRouter(workspaceRoot=Path.cwd())
    result = router.execute(ToolCall(tool="done", reason="ok"), timeoutSeconds=1)
    assert result.ok is True


def test_router_file_read_missing_path() -> None:
    """Ensures invalid file read payload returns an error."""

    router = ToolRouter(workspaceRoot=Path.cwd())
    result = router.execute(ToolCall(tool="file.read"), timeoutSeconds=1)
    assert result.ok is False


def test_router_git_diff_dispatch(monkeypatch) -> None:
    """Ensures git diff tool dispatches through the native git helper."""

    monkeypatch.setattr(
        "e_cli.tools.router.GitTool.diff",
        lambda self, path, timeout_seconds: type("Result", (), {"ok": True, "output": "diff --git"})(),
    )
    router = ToolRouter(workspaceRoot=Path.cwd())
    result = router.execute(ToolCall(tool="git.diff", path="README.md"), timeoutSeconds=1)
    assert result.ok is True
    assert "diff --git" in result.output


def test_router_http_get_requires_url() -> None:
    """Ensures http.get returns a validation error when URL is missing."""

    router = ToolRouter(workspaceRoot=Path.cwd())
    result = router.execute(ToolCall(tool="http.get"), timeoutSeconds=1)
    assert result.ok is False


def test_router_browser_dispatch(monkeypatch) -> None:
    """Ensures browser tool dispatches through browser helper."""

    monkeypatch.setattr(
        "e_cli.tools.router.BrowserTool.open",
        lambda url, timeout_seconds: type("Result", (), {"ok": True, "output": f"opened {url}"})(),
    )
    router = ToolRouter(workspaceRoot=Path.cwd())
    result = router.execute(ToolCall(tool="browser", url="https://example.com"), timeoutSeconds=1)
    assert result.ok is True
    assert "opened" in result.output


def test_router_ssh_dispatch(monkeypatch) -> None:
    """Ensures SSH tool dispatches through SSH helper."""

    monkeypatch.setattr(
        "e_cli.tools.router.SshTool.run",
        lambda **kwargs: type("Result", (), {"ok": True, "output": "remote ok", "exitCode": 0})(),
    )
    router = ToolRouter(workspaceRoot=Path.cwd())
    result = router.execute(ToolCall(tool="ssh", host="server.local", command="uname -a"), timeoutSeconds=1)
    assert result.ok is True
    assert "exitCode=0" in result.output


def test_router_curl_dispatch(monkeypatch) -> None:
    """Ensures curl tool dispatches through curl helper."""

    monkeypatch.setattr(
        "e_cli.tools.router.CurlTool.request",
        lambda **kwargs: type("Result", (), {"ok": True, "output": "status=200"})(),
    )
    router = ToolRouter(workspaceRoot=Path.cwd())
    result = router.execute(ToolCall(tool="curl", url="https://example.com", method="GET"), timeoutSeconds=1)
    assert result.ok is True
    assert "status=200" in result.output


def test_router_rag_search_dispatch(monkeypatch) -> None:
    """Ensures rag.search dispatches through rag helper with defaults."""

    monkeypatch.setattr(
        "e_cli.tools.router.RagTool.search",
        lambda **kwargs: type("Result", (), {"ok": True, "output": f"rag {kwargs['query']}"})(),
    )
    router = ToolRouter(workspaceRoot=Path.cwd())
    result = router.execute(ToolCall(tool="rag.search", query="router execute"), timeoutSeconds=1)
    assert result.ok is True
    assert "rag router execute" in result.output
