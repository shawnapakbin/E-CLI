"""OpenAI-compatible provider implementation used by LM Studio and vLLM."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import requests

from e_cli.models.base import ModelClient, ModelMessage, ModelResponse


class OpenAICompatibleClient(ModelClient):
    """Client for OpenAI-compatible chat and models endpoints."""

    provider_name = "openai-compatible"

    def __init__(self, endpoint: str, api_key: str = "", modelParameters: dict[str, Any] | None = None) -> None:
        """Initialize endpoint and optional API key for authenticated endpoints."""

        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.modelParameters = dict(modelParameters or {})

    def _completionPayload(
        self,
        model_name: str,
        messages: list[ModelMessage],
        stream: bool,
    ) -> dict[str, object]:
        """Build a chat completion payload with configured inference parameters."""

        payload: dict[str, object] = {
            "model": model_name,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": stream,
        }
        if "temperature" in self.modelParameters:
            payload["temperature"] = self.modelParameters["temperature"]
        if "top_p" in self.modelParameters:
            payload["top_p"] = self.modelParameters["top_p"]
        if "max_output_tokens" in self.modelParameters:
            payload["max_tokens"] = self.modelParameters["max_output_tokens"]
        for key, value in self.modelParameters.items():
            if key in {"temperature", "top_p", "max_output_tokens", "model", "messages", "stream"}:
                continue
            payload[key] = value
        return payload

    def _headers(self) -> dict[str, str]:
        """Build request headers including authorization when configured."""

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        """Invoke OpenAI-compatible chat completions and normalize content text."""

        payload = self._completionPayload(model_name=model_name, messages=messages, stream=False)
        response = requests.post(
            f"{self.endpoint}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices", [])
        if not choices:
            return ModelResponse(content="")
        message_payload = choices[0].get("message", {})
        content = message_payload.get("content", "")
        return ModelResponse(content=str(content))

    def stream_chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> Iterator[str]:
        """Yield incremental text deltas from OpenAI-compatible SSE responses."""

        payload = self._completionPayload(model_name=model_name, messages=messages, stream=True)
        with requests.post(
            f"{self.endpoint}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=timeout_seconds,
            stream=True,
        ) as response:
            response.raise_for_status()
            for rawLine in response.iter_lines(decode_unicode=True):
                if not rawLine:
                    continue
                line = rawLine.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                payloadLine = json.loads(data)
                choices = payloadLine.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                chunk = str(delta.get("content", ""))
                if chunk:
                    yield chunk

    def list_models(self, timeout_seconds: int) -> list[str]:
        """Fetch model IDs from OpenAI-compatible models endpoint."""

        response = requests.get(
            f"{self.endpoint}/v1/models",
            headers=self._headers(),
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        entries = body.get("data", [])
        return [str(entry.get("id", "")) for entry in entries if entry.get("id")]
