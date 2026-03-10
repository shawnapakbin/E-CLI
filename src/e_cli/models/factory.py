"""Model client factory and provider dispatch."""

from __future__ import annotations

from e_cli.config import ProviderType
from e_cli.models.base import ModelClient
from e_cli.models.providers.lmstudio import LMStudioClient
from e_cli.models.providers.ollama import OllamaClient
from e_cli.models.providers.vllm import VllmClient


def create_model_client(provider: ProviderType, endpoint: str, api_key: str = "") -> ModelClient:
    """Create provider-specific client implementation based on selected provider."""

    if provider == "ollama":
        return OllamaClient(endpoint)
    if provider == "lmstudio":
        return LMStudioClient(endpoint, api_key=api_key)
    return VllmClient(endpoint, api_key=api_key)
