"""Base protocol and response types for model providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol


@dataclass(slots=True)
class ModelMessage:
    """Represents one chat message sent to a model endpoint."""

    role: str
    content: str


@dataclass(slots=True)
class ModelResponse:
    """Represents one model response payload after provider normalization."""

    content: str
    streamed: bool = False


class ModelClient(Protocol):
    """Provider contract for sending chat messages and receiving model responses."""

    provider_name: str

    def chat(self, model_name: str, messages: list[ModelMessage], timeout_seconds: int) -> ModelResponse:
        """Send a chat request and return the normalized response."""

    def stream_chat(
        self,
        model_name: str,
        messages: list[ModelMessage],
        timeout_seconds: int,
    ) -> Iterator[str]:
        """Yield incremental response chunks when the provider supports streaming."""

    def list_models(self, timeout_seconds: int) -> list[str]:
        """List available models for endpoint selection."""
