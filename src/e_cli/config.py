"""Configuration models and loading for E-CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

ProviderType = Literal["ollama", "lmstudio", "vllm"]
ApprovalMode = Literal["interactive", "auto-approve", "deny"]


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
