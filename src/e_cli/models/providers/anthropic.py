"""Anthropic Claude API provider implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from e_cli.models.base import ModelMessage, ModelResponse


@dataclass
class AnthropicProvider:
    """Anthropic Claude API provider."""

    provider_name: str = "anthropic"
    endpoint: str = "https://api.anthropic.com/v1"
    api_key: str = ""
    model_parameters: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Initialize provider with API key from environment if not provided."""
        if not self.api_key:
            import os
            self.api_key = os.getenv("ANTHROPIC_API_KEY", "")

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        """Send chat request to Anthropic API."""
        import requests

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Separate system message from conversation
        system_message = ""
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": conversation_messages,
            "max_tokens": 4096,
        }

        if system_message:
            payload["system"] = system_message

        if self.model_parameters:
            # Filter out parameters that Claude doesn't support
            for key in ["temperature", "top_p", "max_tokens"]:
                if key in self.model_parameters:
                    payload[key] = self.model_parameters[key]

        response = requests.post(
            f"{self.endpoint}/messages",
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )

        response.raise_for_status()
        data = response.json()

        content = data.get("content", [{}])[0].get("text", "")
        return ModelResponse(content=content, streamed=False)

    def stream_chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> Iterator[str]:
        """Stream chat response from Anthropic API."""
        import requests

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        system_message = ""
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": conversation_messages,
            "max_tokens": 4096,
            "stream": True,
        }

        if system_message:
            payload["system"] = system_message

        if self.model_parameters:
            for key in ["temperature", "top_p", "max_tokens"]:
                if key in self.model_parameters:
                    payload[key] = self.model_parameters[key]

        response = requests.post(
            f"{self.endpoint}/messages",
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

            data_str = line_str[6:]

            try:
                import json
                data = json.loads(data_str)

                if data.get("type") == "content_block_delta":
                    delta = data.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield text

            except Exception:
                continue

    def list_models(self, timeout_seconds: int) -> list[str]:
        """List available Anthropic models."""
        # Anthropic doesn't have a models endpoint, return known models
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]
