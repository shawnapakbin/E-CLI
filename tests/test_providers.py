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

    def __enter__(self):
        """Support context manager usage for streamed provider requests."""

        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Support context manager usage for streamed provider requests."""

        _ = (exc_type, exc, tb)

    def iter_lines(self, decode_unicode: bool = False):
        """Return no streamed lines by default for non-streaming test cases."""

        _ = decode_unicode
        return iter(())


def test_openai_compatible_chat_and_models(monkeypatch) -> None:
    """Ensures OpenAI-compatible client parses chat and model list responses."""

    seenPayloads: list[dict[str, object]] = []

    def fakePost(url: str, json: dict[str, object], headers: dict[str, str], timeout: int):
        _ = (url, headers, timeout)
        seenPayloads.append(json)
        return DummyResponse({"choices": [{"message": {"content": "ok"}}]})

    def fakeGet(url: str, headers: dict[str, str], timeout: int):
        _ = (url, headers, timeout)
        return DummyResponse({"data": [{"id": "model-a"}]})

    monkeypatch.setattr("e_cli.models.providers.openai_compatible.requests.post", fakePost)
    monkeypatch.setattr("e_cli.models.providers.openai_compatible.requests.get", fakeGet)

    client = OpenAICompatibleClient(
        endpoint="http://127.0.0.1:8000",
        api_key="k",
        modelParameters={"temperature": 0.7, "top_p": 0.8, "max_output_tokens": 256, "seed": 7},
    )
    reply = client.chat("model-a", [ModelMessage(role="user", content="hi")], timeout_seconds=5)
    models = client.list_models(timeout_seconds=5)

    assert reply.content == "ok"
    assert models == ["model-a"]
    assert seenPayloads[0]["temperature"] == 0.7
    assert seenPayloads[0]["top_p"] == 0.8
    assert seenPayloads[0]["max_tokens"] == 256
    assert seenPayloads[0]["seed"] == 7


def test_ollama_chat_and_models(monkeypatch) -> None:
    """Ensures Ollama client parses chat and tags responses."""

    seenPayloads: list[dict[str, object]] = []

    def fakePost(url: str, json: dict[str, object], timeout: int):
        _ = (url, timeout)
        seenPayloads.append(json)
        return DummyResponse({"message": {"content": "hello"}})

    def fakeGet(url: str, timeout: int):
        _ = (url, timeout)
        return DummyResponse({"models": [{"name": "llama3"}]})

    monkeypatch.setattr("e_cli.models.providers.ollama.requests.post", fakePost)
    monkeypatch.setattr("e_cli.models.providers.ollama.requests.get", fakeGet)

    client = OllamaClient(
        endpoint="http://127.0.0.1:11434",
        modelParameters={"temperature": 0.4, "top_p": 0.9, "max_output_tokens": 128},
    )
    reply = client.chat("llama3", [ModelMessage(role="user", content="hi")], timeout_seconds=5)
    models = client.list_models(timeout_seconds=5)

    assert reply.content == "hello"
    assert models == ["llama3"]
    options = seenPayloads[0]["options"]
    assert isinstance(options, dict)
    assert options["temperature"] == 0.4
    assert options["top_p"] == 0.9
    assert options["num_predict"] == 128


def test_openai_compatible_streaming(monkeypatch) -> None:
    """Ensures OpenAI-compatible client yields streamed text deltas."""

    class DummyStreamResponse(DummyResponse):
        def iter_lines(self, decode_unicode: bool = False):
            _ = decode_unicode
            return iter(
                [
                    'data: {"choices":[{"delta":{"content":"hel"}}]}',
                    'data: {"choices":[{"delta":{"content":"lo"}}]}',
                    'data: [DONE]',
                ]
            )

    def fakePost(url: str, json: dict[str, object], headers: dict[str, str], timeout: int, stream: bool = False):
        _ = (url, json, headers, timeout, stream)
        return DummyStreamResponse({})

    monkeypatch.setattr("e_cli.models.providers.openai_compatible.requests.post", fakePost)
    client = OpenAICompatibleClient(endpoint="http://127.0.0.1:8000", api_key="k")
    chunks = list(client.stream_chat("model-a", [ModelMessage(role="user", content="hi")], timeout_seconds=5))

    assert chunks == ["hel", "lo"]


def test_ollama_streaming(monkeypatch) -> None:
    """Ensures Ollama client yields streamed message chunks."""

    class DummyStreamResponse(DummyResponse):
        def iter_lines(self, decode_unicode: bool = False):
            _ = decode_unicode
            return iter(
                [
                    '{"message":{"content":"he"}}',
                    '{"message":{"content":"llo"}}',
                ]
            )

    def fakePost(url: str, json: dict[str, object], timeout: int, stream: bool = False):
        _ = (url, json, timeout, stream)
        return DummyStreamResponse({})

    monkeypatch.setattr("e_cli.models.providers.ollama.requests.post", fakePost)
    client = OllamaClient(endpoint="http://127.0.0.1:11434")
    chunks = list(client.stream_chat("llama3", [ModelMessage(role="user", content="hi")], timeout_seconds=5))

    assert chunks == ["he", "llo"]
