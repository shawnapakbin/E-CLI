"""Configuration models and loading for E-CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

ProviderType = Literal["ollama", "lmstudio", "vllm", "bundled"]
ApprovalMode = Literal["interactive", "auto-approve", "deny"]
RagCorpus = Literal["session", "workspace", "combined"]



class AppConfig(BaseModel):
    """Application configuration persisted in the user profile directory."""

    provider: ProviderType = Field(default="ollama")
    model: str = Field(default="")
    endpoint: str = Field(default="http://127.0.0.1:11434")
    safeMode: bool = Field(default=True)
    approvalMode: ApprovalMode = Field(default="interactive")
    memoryPath: str = Field(default="")
    lastSessionId: str = Field(default="")
    maxTurns: int = Field(default=8)
    timeoutSeconds: int = Field(default=60)
    streamingEnabled: bool = Field(default=True)
    conversationTokenBudget: int = Field(default=3200)
    conversationSummaryBudget: int = Field(default=800)
    temperature: float = Field(default=0.2)
    topP: float = Field(default=1.0)
    maxOutputTokens: int = Field(default=0)
    providerOptions: dict[str, bool | int | float | str] = Field(default_factory=dict)
    ragCorpusDefault: RagCorpus = Field(default="combined")
    ragTopK: int = Field(default=5)
    # Bundled helper config fields
    bundledHelperEnabled: bool = Field(default=False)
    bundledHelperProfile: str = Field(default="slim")
    bundledHelperAutoActivate: bool = Field(default=False)
    bundledHelperRuntimePath: str = Field(default="")

    def modelParameters(self) -> dict[str, bool | int | float | str]:
        """Return normalized model parameters for provider request payloads."""

        parameters: dict[str, bool | int | float | str] = {
            "temperature": self.temperature,
            "top_p": self.topP,
        }
        if self.maxOutputTokens > 0:
            parameters["max_output_tokens"] = self.maxOutputTokens
        parameters.update(self.providerOptions)
        return parameters


def get_app_dir() -> Path:
    """Return the OS-appropriate application data directory for E-CLI."""

    home_dir = Path.home()
    app_data = os.getenv("APPDATA")
    if app_data:
        return Path(app_data) / "e-cli"
    return home_dir / ".e-cli"


def get_config_path() -> Path:
    """Return the config file path used by the CLI."""

    return get_app_dir() / "config.json"


def get_memory_db_path() -> Path:
    """Return the memory database path, creating app directory assumptions only."""

    return get_app_dir() / "memory.db"


def load_config() -> AppConfig:
    """Load config from disk and fallback to defaults on first run or bad payload."""

    config_path = get_config_path()
    if not config_path.exists():
        default_config = AppConfig(memoryPath=str(get_memory_db_path()))
        save_config(default_config)
        return default_config

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        loaded_config = AppConfig(**config_data)
        if not loaded_config.memoryPath:
            loaded_config.memoryPath = str(get_memory_db_path())
        return loaded_config
    except (json.JSONDecodeError, OSError, ValidationError):
        fallback_config = AppConfig(memoryPath=str(get_memory_db_path()))
        save_config(fallback_config)
        return fallback_config


def save_config(config: AppConfig) -> None:
    """Persist configuration to disk with full overwrite semantics."""

    app_dir = get_app_dir()
    app_dir.mkdir(parents=True, exist_ok=True)
    config_path = get_config_path()
    config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


# Mapping from ECLI_* env-var names to the corresponding AppConfig field names.
_ENV_VAR_FIELDS: dict[str, str] = {
    "ECLI_PROVIDER": "provider",
    "ECLI_MODEL": "model",
    "ECLI_ENDPOINT": "endpoint",
    "ECLI_SAFE_MODE": "safeMode",
    "ECLI_APPROVAL_MODE": "approvalMode",
    "ECLI_MAX_TURNS": "maxTurns",
    "ECLI_TIMEOUT_SECONDS": "timeoutSeconds",
    "ECLI_STREAMING": "streamingEnabled",
    "ECLI_TOKEN_BUDGET": "conversationTokenBudget",
    "ECLI_SUMMARY_BUDGET": "conversationSummaryBudget",
    "ECLI_MEMORY_PATH": "memoryPath",
    # Bundled helper env overlays
    "ECLI_BUNDLED_HELPER_ENABLED": "bundledHelperEnabled",
    "ECLI_BUNDLED_HELPER_PROFILE": "bundledHelperProfile",
    "ECLI_BUNDLED_HELPER_AUTO_ACTIVATE": "bundledHelperAutoActivate",
    "ECLI_BUNDLED_HELPER_RUNTIME_PATH": "bundledHelperRuntimePath",
}


def load_config_with_env_overrides() -> AppConfig:
    """Load config from disk then overlay any ECLI_* environment variables.

    Env vars are applied after JSON load so they can always override per-run
    without touching the persisted config file.  Type coercion is handled
    by Pydantic – booleans accept '1'/'true'/'yes' (case-insensitive).
    """

    config = load_config()
    overrides: dict[str, object] = {}
    for env_key, field_name in _ENV_VAR_FIELDS.items():
        raw = os.getenv(env_key)
        if raw is not None:
            overrides[field_name] = raw

    if overrides:
        # Build a merged dict then re-validate through Pydantic so type coercion
        # and validation run exactly once.
        merged = config.model_dump()
        merged.update(overrides)
        try:
            config = AppConfig(**merged)
        except ValidationError:
            # If an env var contains an invalid value keep the existing config
            # and let the caller proceed; a warning is emitted but we don't crash.
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "One or more ECLI_* env vars contain invalid values and were ignored: %s",
                list(overrides.keys()),
            )

    return config
