"""OpenAI API provider implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from e_cli.models.base import ModelClient, ModelMessage, ModelResponse


@dataclass
class OpenAIProvider:
    """OpenAI API provider for GPT models."""

    provider_name: str = "openai"
    endpoint: str = "https://api.openai.com/v1"
    api_key: str = ""
    model_parameters: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Initialize provider with API key from environment if not provided."""
        if not self.api_key:
            import os
            self.api_key = os.getenv("OPENAI_API_KEY", "")

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        """Send chat request to OpenAI API."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": openai_messages,
        }

        # Add model parameters if provided
        if self.model_parameters:
            payload.update(self.model_parameters)

        response = requests.post(
            f"{self.endpoint}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )

        response.raise_for_status()
        data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ModelResponse(content=content, streamed=False)

    def stream_chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> Iterator[str]:
        """Stream chat response from OpenAI API."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": openai_messages,
            "stream": True,
        }

        if self.model_parameters:
            payload.update(self.model_parameters)

        response = requests.post(
            f"{self.endpoint}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
            stream=True,
        )

        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode("utf-8")
            if not line_str.startswith("data: "):
                continue

            data_str = line_str[6:]  # Remove "data: " prefix
            if data_str == "[DONE]":
                break

            try:
                import json
                data = json.loads(data_str)
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
            except Exception:
                continue

    def list_models(self, timeout_seconds: int) -> list[str]:
        """List available OpenAI models."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            response = requests.get(
                f"{self.endpoint}/models",
                headers=headers,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            # Filter to only chat models
            models = [
                model["id"]
                for model in data.get("data", [])
                if "gpt" in model["id"].lower()
            ]
            return sorted(models)

        except Exception:
            # Return common models as fallback
            return [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo",
            ]
