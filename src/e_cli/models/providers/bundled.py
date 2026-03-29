"""BundledModelClient: OpenAI-compatible client for the bundled setup-helper model."""


from e_cli.models.base import ModelClient, ModelResponse
from e_cli.models.bundled_assets import BundledAssetManager
from e_cli.models.bundled_runtime import BundledRuntime
from typing import Any

class BundledModelClient(ModelClient):
    def __init__(self, endpoint: str, modelParameters: dict[str, Any] | None = None):
        self.endpoint = endpoint
        self.modelParameters = modelParameters or {}
        self.asset_manager = BundledAssetManager()
        self.runtime = BundledRuntime()

    def chat(self, model_name: str, messages: list, timeout_seconds: int) -> ModelResponse:
        # Ensure assets are present and runtime is running before chat
        if not self.asset_manager.ensure_assets():
            return ModelResponse(content="[BundledModelClient: assets missing or failed to verify]", streamed=False)
        if self.runtime.status() != "running":
            return ModelResponse(content="[BundledModelClient: runtime not running]", streamed=False)
        # TODO: Implement HTTP call to local bundled runtime
        return ModelResponse(content="[BundledModelClient stub reply]", streamed=False)

    def list_models(self, timeout_seconds: int) -> list[str]:
        # Ensure assets are present before listing models
        if not self.asset_manager.ensure_assets():
            return []
        # TODO: Query the local runtime for available models
        return ["qwen2.5-coder-3b", "qwen2.5-coder-7b"]
