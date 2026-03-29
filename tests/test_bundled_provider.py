"""Tests for BundledModelClient integration with asset manager and runtime."""
from e_cli.models.providers.bundled import BundledModelClient
from e_cli.models.base import ModelResponse
import pytest

def test_bundled_model_client_chat_assets_missing(monkeypatch):
    class FakeAssetManager:
        def ensure_assets(self):
            return False
    class FakeRuntime:
        def status(self):
            return "running"
    monkeypatch.setattr("e_cli.models.providers.bundled.BundledAssetManager", lambda: FakeAssetManager())
    monkeypatch.setattr("e_cli.models.providers.bundled.BundledRuntime", lambda: FakeRuntime())
    client = BundledModelClient(endpoint="http://localhost")
    resp = client.chat("qwen2.5-coder-3b", [], 10)
    assert "assets missing" in resp.content

def test_bundled_model_client_chat_runtime_not_running(monkeypatch):
    class FakeAssetManager:
        def ensure_assets(self):
            return True
    class FakeRuntime:
        def status(self):
            return "stopped"
    monkeypatch.setattr("e_cli.models.providers.bundled.BundledAssetManager", lambda: FakeAssetManager())
    monkeypatch.setattr("e_cli.models.providers.bundled.BundledRuntime", lambda: FakeRuntime())
    client = BundledModelClient(endpoint="http://localhost")
    resp = client.chat("qwen2.5-coder-3b", [], 10)
    assert "runtime not running" in resp.content

def test_bundled_model_client_chat_happy(monkeypatch):
    class FakeAssetManager:
        def ensure_assets(self):
            return True
    class FakeRuntime:
        def status(self):
            return "running"
    monkeypatch.setattr("e_cli.models.providers.bundled.BundledAssetManager", lambda: FakeAssetManager())
    monkeypatch.setattr("e_cli.models.providers.bundled.BundledRuntime", lambda: FakeRuntime())
    client = BundledModelClient(endpoint="http://localhost")
    resp = client.chat("qwen2.5-coder-3b", [], 10)
    assert "stub reply" in resp.content

def test_bundled_model_client_list_models_assets_missing(monkeypatch):
    class FakeAssetManager:
        def ensure_assets(self):
            return False
    monkeypatch.setattr("e_cli.models.providers.bundled.BundledAssetManager", lambda: FakeAssetManager())
    client = BundledModelClient(endpoint="http://localhost")
    models = client.list_models(10)
    assert models == []

def test_bundled_model_client_list_models_happy(monkeypatch):
    class FakeAssetManager:
        def ensure_assets(self):
            return True
    monkeypatch.setattr("e_cli.models.providers.bundled.BundledAssetManager", lambda: FakeAssetManager())
    client = BundledModelClient(endpoint="http://localhost")
    models = client.list_models(10)
    assert "qwen2.5-coder-3b" in models
