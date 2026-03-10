"""OpenAI-compatible provider implementation used by LM Studio and vLLM."""

from __future__ import annotations

import requests

from e_cli.models.base import ModelClient, ModelMessage, ModelResponse


class OpenAICompatibleClient(ModelClient):
    """Client for OpenAI-compatible chat and models endpoints."""

    provider_name = "openai-compatible"

    def __init__(self, endpoint: str, api_key: str = "") -> None:
        """Initialize endpoint and optional API key for authenticated endpoints."""

        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        """Build request headers including authorization when configured."""

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        """Invoke OpenAI-compatible chat completions and normalize content text."""

        payload = {
            "model": model_name,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": 0.2,
        }
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
