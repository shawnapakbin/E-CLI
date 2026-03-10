"""Ollama provider implementation for local or remote endpoints."""

from __future__ import annotations

import requests

from e_cli.models.base import ModelClient, ModelMessage, ModelResponse


class OllamaClient(ModelClient):
    """Ollama-compatible client using the /api/chat and /api/tags endpoints."""

    provider_name = "ollama"

    def __init__(self, endpoint: str) -> None:
        """Store normalized endpoint base URL for API calls."""

        self.endpoint = endpoint.rstrip("/")

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        """Invoke Ollama chat API and normalize content payload to a text response."""

        payload = {
            "model": model_name,
            "stream": False,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
        }
        response = requests.post(
            f"{self.endpoint}/api/chat",
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        content = body.get("message", {}).get("content", "")
        return ModelResponse(content=str(content))

    def list_models(self, timeout_seconds: int) -> list[str]:
        """Fetch model tags from Ollama endpoint and return model names."""

        response = requests.get(f"{self.endpoint}/api/tags", timeout=timeout_seconds)
        response.raise_for_status()
        body = response.json()
        models = body.get("models", [])
        return [str(model.get("name", "")) for model in models if model.get("name")]
