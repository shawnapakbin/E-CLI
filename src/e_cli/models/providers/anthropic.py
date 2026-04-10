"""Anthropic Claude provider implementation."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import requests

from e_cli.config import AppConfig
from e_cli.models.base import ModelClient, ModelMessage, ModelResponse
from e_cli.models.exceptions import ConfigurationError, ProviderRateLimitError

# Static list of known Claude model IDs (no network call required).
CLAUDE_MODELS: list[str] = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-3-5",
]

_RETRY_DELAYS: list[int] = [1, 2, 4, 8]
_MAX_ATTEMPTS: int = 4


class AnthropicClient(ModelClient):
    """Anthropic Messages API client implementing the ModelClient protocol."""

    BASE_URL = "https://api.anthropic.com/v1/messages"
    provider_name = "anthropic"

    def __init__(self, config: AppConfig) -> None:
        """Resolve API key and store model parameters; raise ConfigurationError if key absent."""

        api_key = os.getenv("ANTHROPIC_API_KEY") or config.anthropicApiKey
        if not api_key:
            raise ConfigurationError("Anthropic API key not configured")
        self._api_key = api_key
        self._model_parameters: dict[str, Any] = dict(config.modelParameters())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self, stream: bool = False) -> dict[str, str]:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if stream:
            headers["anthropic-beta"] = "stream"
        return headers

    def _build_payload(
        self,
        model_name: str,
        messages: list[ModelMessage],
        stream: bool,
    ) -> dict[str, Any]:
        """Build the Anthropic Messages API request payload."""

        # Separate system messages from the conversation.
        system_parts: list[str] = []
        conversation: list[dict[str, str]] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            else:
                conversation.append({"role": msg.role, "content": msg.content})

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": conversation,
            "stream": stream,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        # Inject model parameters.
        if "temperature" in self._model_parameters:
            payload["temperature"] = self._model_parameters["temperature"]
        if "top_p" in self._model_parameters:
            payload["top_p"] = self._model_parameters["top_p"]
        max_tokens = int(self._model_parameters.get("max_output_tokens", 0))
        payload["max_tokens"] = max_tokens if max_tokens > 0 else 4096

        return payload

    @staticmethod
    def _check_rate_limit(response: requests.Response) -> None:
        """Raise ProviderRateLimitError for HTTP 429 or 529 responses."""

        if response.status_code in (429, 529):
            raise ProviderRateLimitError(
                f"Anthropic rate limit / overload (HTTP {response.status_code})"
            )

    def _post_with_retry(
        self,
        payload: dict[str, Any],
        stream: bool,
        timeout_seconds: int,
    ) -> requests.Response:
        """POST to the Anthropic API with exponential back-off on rate-limit errors."""

        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = requests.post(
                    self.BASE_URL,
                    headers=self._headers(stream=stream),
                    json=payload,
                    timeout=timeout_seconds,
                    stream=stream,
                )
                self._check_rate_limit(response)
                response.raise_for_status()
                return response
            except ProviderRateLimitError as exc:
                last_exc = exc
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_RETRY_DELAYS[attempt])
                continue
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # ModelClient protocol
    # ------------------------------------------------------------------

    def chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> ModelResponse:
        """Send a non-streaming chat request and return the full response."""

        payload = self._build_payload(model_name, messages, stream=False)
        response = self._post_with_retry(payload, stream=False, timeout_seconds=timeout_seconds)
        body = response.json()
        content_blocks = body.get("content", [])
        text = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )
        return ModelResponse(content=text)

    def stream_chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> Iterator[str]:
        """Yield text delta tokens from the Anthropic streaming API."""

        payload = self._build_payload(model_name, messages, stream=True)
        response = self._post_with_retry(payload, stream=True, timeout_seconds=timeout_seconds)

        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data:"):
                continue
            data_str = raw_line[len("data:"):].strip()
            if data_str == "[DONE]":
                break
            try:
                import json
                event = json.loads(data_str)
            except Exception:
                continue
            # Anthropic stream events: content_block_delta with delta.type == text_delta
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        yield text

    def list_models(self, timeout_seconds: int) -> list[str]:
        """Return the static list of known Claude model IDs without a network call."""

        return list(CLAUDE_MODELS)
