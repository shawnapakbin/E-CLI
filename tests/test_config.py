"""Tests for config persistence and default loading."""

import json
from pathlib import Path

from e_cli.config import AppConfig, get_config_path, load_config, load_config_with_env_overrides, save_config


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
    inputConfig = AppConfig(
        provider="vllm",
        model="m1",
        endpoint="http://1.2.3.4:8000",
        temperature=0.6,
        providerOptions={"seed": 9},
        ragCorpusDefault="workspace",
        ragTopK=4,
    )
    save_config(inputConfig)

    loadedJson = json.loads(get_config_path().read_text(encoding="utf-8"))
    assert loadedJson["provider"] == "vllm"
    assert loadedJson["model"] == "m1"
    assert loadedJson["temperature"] == 0.6
    assert loadedJson["providerOptions"] == {"seed": 9}
    assert loadedJson["ragCorpusDefault"] == "workspace"
    assert loadedJson["ragTopK"] == 4


def test_env_overrides_apply(monkeypatch, tmp_path: Path) -> None:
    """Ensures ECLI_* env vars are merged over the persisted config."""

    monkeypatch.setenv("APPDATA", str(tmp_path))
    # Persist a base config first so the file exists.
    save_config(AppConfig(provider="ollama", model="base-model"))

    monkeypatch.setenv("ECLI_PROVIDER", "vllm")
    monkeypatch.setenv("ECLI_MODEL", "override-model")
    monkeypatch.setenv("ECLI_MAX_TURNS", "16")
    monkeypatch.setenv("ECLI_SAFE_MODE", "false")

    config = load_config_with_env_overrides()
    assert config.provider == "vllm"
    assert config.model == "override-model"
    assert config.maxTurns == 16
    assert config.safeMode is False


def test_env_overrides_invalid_value_keeps_original(monkeypatch, tmp_path: Path) -> None:
    """Ensures an invalid ECLI_* value leaves config intact instead of crashing."""

    monkeypatch.setenv("APPDATA", str(tmp_path))
    save_config(AppConfig(provider="ollama", maxTurns=5))

    monkeypatch.setenv("ECLI_PROVIDER", "not-a-valid-provider")
    config = load_config_with_env_overrides()
    # Provider is a Literal; invalid value causes ValidationError → fallback to original
    assert config.provider == "ollama"
    assert config.maxTurns == 5


def test_env_overrides_no_env_vars_returns_persisted(monkeypatch, tmp_path: Path) -> None:
    """Ensures load_config_with_env_overrides returns persisted values when no env vars set."""

    monkeypatch.setenv("APPDATA", str(tmp_path))
    for key in [
        "ECLI_PROVIDER", "ECLI_MODEL", "ECLI_ENDPOINT", "ECLI_SAFE_MODE",
        "ECLI_APPROVAL_MODE", "ECLI_MAX_TURNS", "ECLI_TIMEOUT_SECONDS",
        "ECLI_STREAMING", "ECLI_TOKEN_BUDGET", "ECLI_SUMMARY_BUDGET", "ECLI_MEMORY_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)

    save_config(AppConfig(provider="lmstudio", model="persisted-model", maxTurns=3))
    config = load_config_with_env_overrides()
    assert config.provider == "lmstudio"
    assert config.model == "persisted-model"
    assert config.maxTurns == 3
