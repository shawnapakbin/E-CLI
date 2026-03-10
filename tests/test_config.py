"""Tests for config persistence and default loading."""

import json
from pathlib import Path

from e_cli.config import AppConfig, get_config_path, load_config, save_config


def test_load_config_creates_default(monkeypatch, tmp_path: Path) -> None:
    """Ensures first load creates a default config file."""

    monkeypatch.setenv("APPDATA", str(tmp_path))
    config = load_config()
    assert isinstance(config, AppConfig)
    assert get_config_path().exists()


def test_load_config_recovers_invalid_json(monkeypatch, tmp_path: Path) -> None:
    """Ensures invalid config payload is replaced by valid defaults."""

    monkeypatch.setenv("APPDATA", str(tmp_path))
    configPath = get_config_path()
    configPath.parent.mkdir(parents=True, exist_ok=True)
    configPath.write_text("not-json", encoding="utf-8")

    config = load_config()
    assert config.provider in {"ollama", "lmstudio", "vllm"}


def test_save_and_reload_config(monkeypatch, tmp_path: Path) -> None:
    """Ensures saved configuration values are persisted and reloaded."""

    monkeypatch.setenv("APPDATA", str(tmp_path))
    inputConfig = AppConfig(provider="vllm", model="m1", endpoint="http://1.2.3.4:8000")
    save_config(inputConfig)

    loadedJson = json.loads(get_config_path().read_text(encoding="utf-8"))
    assert loadedJson["provider"] == "vllm"
    assert loadedJson["model"] == "m1"
