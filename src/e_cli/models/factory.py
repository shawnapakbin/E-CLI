"""Model client factory and provider dispatch."""

from __future__ import annotations

from typing import Any

from e_cli.config import ProviderType
from e_cli.models.base import ModelClient
from e_cli.models.providers.lmstudio import LMStudioClient
from e_cli.models.providers.ollama import OllamaClient
from e_cli.models.providers.vllm import VllmClient
from e_cli.models.providers.openai import OpenAIProvider
from e_cli.models.providers.anthropic import AnthropicProvider
from e_cli.models.providers.google import GoogleProvider


def create_model_client(
    provider: ProviderType,
    endpoint: str,
    api_key: str = "",
    modelParameters: dict[str, Any] | None = None,
) -> ModelClient:
    """Create provider-specific client implementation based on selected provider."""

    if provider == "ollama":
        return OllamaClient(endpoint, modelParameters=modelParameters)
    if provider == "lmstudio":
        return LMStudioClient(endpoint, api_key=api_key, modelParameters=modelParameters)
    if provider == "vllm":
        return VllmClient(endpoint, api_key=api_key, modelParameters=modelParameters)
    if provider == "openai":
        return OpenAIProvider(endpoint=endpoint, api_key=api_key, model_parameters=modelParameters)
    if provider == "anthropic":
        return AnthropicProvider(endpoint=endpoint, api_key=api_key, model_parameters=modelParameters)
    if provider == "google":
        return GoogleProvider(endpoint=endpoint, api_key=api_key, model_parameters=modelParameters)

    # Default fallback
    return VllmClient(endpoint, api_key=api_key, modelParameters=modelParameters)
