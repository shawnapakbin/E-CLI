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
