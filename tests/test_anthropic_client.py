"""Unit tests for the AnthropicClient provider."""

from __future__ import annotations

import json
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from e_cli.config import AppConfig
from e_cli.models.base import ModelMessage
from e_cli.models.exceptions import ConfigurationError, ProviderRateLimitError
from e_cli.models.providers.anthropic import CLAUDE_MODELS, AnthropicClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(api_key: str = "") -> AppConfig:
    return AppConfig(anthropicApiKey=api_key)


def _make_client(api_key: str = "test-key") -> AnthropicClient:
    return AnthropicClient(_make_config(api_key=api_key))


def _messages() -> list[ModelMessage]:
    return [
        ModelMessage(role="system", content="You are helpful."),
        ModelMessage(role="user", content="Hello"),
    ]


# ---------------------------------------------------------------------------
# 2.3 – API key resolution and ConfigurationError
# ---------------------------------------------------------------------------

class TestApiKeyResolution:
    def test_raises_when_no_key_anywhere(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ConfigurationError, match="Anthropic API key not configured"):
            AnthropicClient(_make_config(api_key=""))

    def test_uses_env_var_when_config_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        client = AnthropicClient(_make_config(api_key=""))
        assert client._api_key == "env-key"

    def test_uses_config_key_when_env_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = AnthropicClient(_make_config(api_key="config-key"))
        assert client._api_key == "config-key"

    def test_env_var_takes_precedence_over_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        client = AnthropicClient(_make_config(api_key="config-key"))
        assert client._api_key == "env-key"


# ---------------------------------------------------------------------------
# list_models – static, no network call
# ---------------------------------------------------------------------------

class TestListModels:
    def test_returns_static_claude_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = _make_client()
        models = client.list_models(timeout_seconds=5)
        assert models == CLAUDE_MODELS
        assert "claude-opus-4-5" in models
        assert "claude-sonnet-4-5" in models
        assert "claude-haiku-3-5" in models


# ---------------------------------------------------------------------------
# chat – correct request construction
# ---------------------------------------------------------------------------

class TestChat:
    def test_correct_request_construction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = _make_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Hi there!"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = client.chat("claude-haiku-3-5", _messages(), timeout_seconds=30)

        assert result.content == "Hi there!"
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert payload["model"] == "claude-haiku-3-5"
        assert payload["stream"] is False
        assert any(m["role"] == "user" for m in payload["messages"])
        # System message should be extracted to top-level "system" field
        assert "system" in payload
        assert "You are helpful." in payload["system"]

    def test_passes_model_parameters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = AppConfig(anthropicApiKey="key", temperature=0.5, topP=0.9, maxOutputTokens=512)
        client = AnthropicClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": [{"type": "text", "text": "ok"}]}
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            client.chat("claude-haiku-3-5", _messages(), timeout_seconds=30)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args.args[1]
        assert payload["temperature"] == 0.5
        assert payload["top_p"] == 0.9
        assert payload["max_tokens"] == 512


# ---------------------------------------------------------------------------
# stream_chat – token yield
# ---------------------------------------------------------------------------

class TestStreamChat:
    def _make_sse_lines(self, tokens: list[str]) -> list[str]:
        lines: list[str] = []
        for token in tokens:
            event = {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": token},
            }
            lines.append(f"data: {json.dumps(event)}")
        lines.append("data: [DONE]")
        return lines

    def test_yields_text_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = _make_client()

        sse_lines = self._make_sse_lines(["Hello", " world", "!"])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_lines.return_value = iter(sse_lines)

        with patch("requests.post", return_value=mock_response):
            tokens = list(client.stream_chat("claude-haiku-3-5", _messages(), timeout_seconds=30))

        assert tokens == ["Hello", " world", "!"]

    def test_skips_non_text_delta_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = _make_client()

        lines = [
            'data: {"type": "message_start", "message": {}}',
            'data: {"type": "content_block_start", "index": 0}',
            'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hi"}}',
            "data: [DONE]",
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_lines.return_value = iter(lines)

        with patch("requests.post", return_value=mock_response):
            tokens = list(client.stream_chat("claude-haiku-3-5", _messages(), timeout_seconds=30))

        assert tokens == ["hi"]


# ---------------------------------------------------------------------------
# 2.4 – Rate-limit retry behaviour
# ---------------------------------------------------------------------------

class TestRateLimitRetry:
    def test_retries_on_429_and_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = _make_client()

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"content": [{"type": "text", "text": "ok"}]}
        success_response.raise_for_status = MagicMock()

        call_count = 0

        def fake_post(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return rate_limit_response
            return success_response

        with patch("requests.post", side_effect=fake_post):
            with patch("time.sleep") as mock_sleep:
                result = client.chat("claude-haiku-3-5", _messages(), timeout_seconds=30)

        assert result.content == "ok"
        assert call_count == 3
        # Should have slept twice (after attempt 0 and 1)
        assert mock_sleep.call_count == 2

    def test_retries_on_529_overloaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = _make_client()

        overload_response = MagicMock()
        overload_response.status_code = 529

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"content": [{"type": "text", "text": "done"}]}
        success_response.raise_for_status = MagicMock()

        responses = [overload_response, success_response]

        with patch("requests.post", side_effect=responses):
            with patch("time.sleep"):
                result = client.chat("claude-haiku-3-5", _messages(), timeout_seconds=30)

        assert result.content == "done"

    def test_raises_after_max_attempts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = _make_client()

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429

        with patch("requests.post", return_value=rate_limit_response):
            with patch("time.sleep"):
                with pytest.raises(ProviderRateLimitError):
                    client.chat("claude-haiku-3-5", _messages(), timeout_seconds=30)

    def test_exponential_backoff_delays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = _make_client()

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429

        sleep_calls: list[int] = []

        def fake_sleep(seconds: int) -> None:
            sleep_calls.append(seconds)

        with patch("requests.post", return_value=rate_limit_response):
            with patch("time.sleep", side_effect=fake_sleep):
                with pytest.raises(ProviderRateLimitError):
                    client.chat("claude-haiku-3-5", _messages(), timeout_seconds=30)

        # 4 attempts → 3 sleeps with delays [1, 2, 4]
        assert sleep_calls == [1, 2, 4]
