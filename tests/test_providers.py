"""Tests for Ollama and OpenAI-compatible provider clients."""

from e_cli.models.base import ModelMessage
from e_cli.models.providers.ollama import OllamaClient
from e_cli.models.providers.openai_compatible import OpenAICompatibleClient


class DummyResponse:
    """Simple HTTP response stand-in for provider request tests."""

    def __init__(self, payload: dict[str, object], ok: bool = True) -> None:
        """Stores JSON payload and status for fake network calls."""

        self._payload = payload
        self.ok = ok

    def raise_for_status(self) -> None:
        """Raises an error when response is marked as failure."""

        if not self.ok:
            raise RuntimeError("http error")

    def json(self) -> dict[str, object]:
        """Returns fake JSON payload."""

        return self._payload


def test_openai_compatible_chat_and_models(monkeypatch) -> None:
    """Ensures OpenAI-compatible client parses chat and model list responses."""

    def fakePost(url: str, json: dict[str, object], headers: dict[str, str], timeout: int):
        _ = (url, json, headers, timeout)
        return DummyResponse({"choices": [{"message": {"content": "ok"}}]})

    def fakeGet(url: str, headers: dict[str, str], timeout: int):
        _ = (url, headers, timeout)
        return DummyResponse({"data": [{"id": "model-a"}]})

    monkeypatch.setattr("e_cli.models.providers.openai_compatible.requests.post", fakePost)
    monkeypatch.setattr("e_cli.models.providers.openai_compatible.requests.get", fakeGet)

    client = OpenAICompatibleClient(endpoint="http://127.0.0.1:8000", api_key="k")
    reply = client.chat("model-a", [ModelMessage(role="user", content="hi")], timeout_seconds=5)
    models = client.list_models(timeout_seconds=5)

    assert reply.content == "ok"
    assert models == ["model-a"]


def test_ollama_chat_and_models(monkeypatch) -> None:
    """Ensures Ollama client parses chat and tags responses."""

    def fakePost(url: str, json: dict[str, object], timeout: int):
        _ = (url, json, timeout)
        return DummyResponse({"message": {"content": "hello"}})

    def fakeGet(url: str, timeout: int):
        _ = (url, timeout)
        return DummyResponse({"models": [{"name": "llama3"}]})

    monkeypatch.setattr("e_cli.models.providers.ollama.requests.post", fakePost)
    monkeypatch.setattr("e_cli.models.providers.ollama.requests.get", fakeGet)

    client = OllamaClient(endpoint="http://127.0.0.1:11434")
    reply = client.chat("llama3", [ModelMessage(role="user", content="hi")], timeout_seconds=5)
    models = client.list_models(timeout_seconds=5)

    assert reply.content == "hello"
    assert models == ["llama3"]
