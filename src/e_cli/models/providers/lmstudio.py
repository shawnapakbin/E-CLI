"""LM Studio provider wrapper using OpenAI-compatible transport."""

from __future__ import annotations

from e_cli.models.providers.openai_compatible import OpenAICompatibleClient


class LMStudioClient(OpenAICompatibleClient):
    """LM Studio client with a fixed provider name for routing."""

    provider_name = "lmstudio"
