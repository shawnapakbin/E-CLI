"""Google Gemini API provider implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from e_cli.models.base import ModelClient, ModelMessage, ModelResponse


@dataclass
class GoogleProvider:
    """Google Gemini API provider."""

    provider_name: str = "google"
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta"
    api_key: str = ""
    model_parameters: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Initialize provider with API key from environment if not provided."""
        if not self.api_key:
            import os
            self.api_key = os.getenv("GOOGLE_API_KEY", "")

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        """Send chat request to Google Gemini API."""
        import requests

        # Convert messages to Gemini format
        gemini_messages = []
        for msg in messages:
            role = "user" if msg.role in ["user", "system"] else "model"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        payload: dict[str, Any] = {
            "contents": gemini_messages,
        }

        # Add generation config if parameters provided
        if self.model_parameters:
            generation_config = {}
            if "temperature" in self.model_parameters:
                generation_config["temperature"] = self.model_parameters["temperature"]
            if "top_p" in self.model_parameters:
                generation_config["topP"] = self.model_parameters["top_p"]
            if "max_output_tokens" in self.model_parameters:
                generation_config["maxOutputTokens"] = self.model_parameters["max_output_tokens"]

            if generation_config:
                payload["generationConfig"] = generation_config

        url = f"{self.endpoint}/models/{model_name}:generateContent?key={self.api_key}"

        response = requests.post(
            url,
            json=payload,
            timeout=timeout_seconds,
        )

        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return ModelResponse(content=content, streamed=False)

        return ModelResponse(content="", streamed=False)

    def stream_chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> Iterator[str]:
        """Stream chat response from Google Gemini API."""
        import requests

        gemini_messages = []
        for msg in messages:
            role = "user" if msg.role in ["user", "system"] else "model"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        payload: dict[str, Any] = {
            "contents": gemini_messages,
        }

        if self.model_parameters:
            generation_config = {}
            if "temperature" in self.model_parameters:
                generation_config["temperature"] = self.model_parameters["temperature"]
            if "top_p" in self.model_parameters:
                generation_config["topP"] = self.model_parameters["top_p"]
            if "max_output_tokens" in self.model_parameters:
                generation_config["maxOutputTokens"] = self.model_parameters["max_output_tokens"]

            if generation_config:
                payload["generationConfig"] = generation_config

        url = f"{self.endpoint}/models/{model_name}:streamGenerateContent?key={self.api_key}&alt=sse"

        response = requests.post(
            url,
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
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if content:
                        yield content
            except Exception:
                continue

    def list_models(self, timeout_seconds: int) -> list[str]:
        """List available Google Gemini models."""
        import requests

        try:
            url = f"{self.endpoint}/models?key={self.api_key}"
            response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            data = response.json()

            models = [
                model["name"].replace("models/", "")
                for model in data.get("models", [])
                if "generateContent" in model.get("supportedGenerationMethods", [])
            ]
            return sorted(models)

        except Exception:
            # Return common models as fallback
            return [
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ]
