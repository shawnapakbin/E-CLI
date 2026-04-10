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


# ---------------------------------------------------------------------------
# BundledAssetManager tests
# ---------------------------------------------------------------------------

import hashlib
from pathlib import Path
from e_cli.models.bundled_assets import BundledAssetManager


def test_verify_checksum_correct(tmp_path):
    """verify_checksum returns True when the file matches the expected hash."""
    asset_file = tmp_path / "model.bin"
    content = b"fake model data"
    asset_file.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    manager = BundledAssetManager(asset_dir=str(tmp_path))
    assert manager.verify_checksum(asset_file, expected) is True


def test_verify_checksum_wrong_hash(tmp_path):
    """verify_checksum returns False when the hash doesn't match."""
    asset_file = tmp_path / "model.bin"
    asset_file.write_bytes(b"some data")
    manager = BundledAssetManager(asset_dir=str(tmp_path))
    assert manager.verify_checksum(asset_file, "wronghash") is False


def test_verify_checksum_missing_file(tmp_path):
    """verify_checksum returns False when the file doesn't exist."""
    manager = BundledAssetManager(asset_dir=str(tmp_path))
    assert manager.verify_checksum(tmp_path / "nonexistent.bin", "anyhash") is False


def test_ensure_assets_download_failure(tmp_path, monkeypatch):
    """ensure_assets returns False when download fails for all assets."""
    import urllib.request
    def fake_retrieve(url, path):
        raise OSError("network error")
    monkeypatch.setattr(urllib.request, "urlretrieve", fake_retrieve)
    manager = BundledAssetManager(asset_dir=str(tmp_path))
    result = manager.ensure_assets()
    assert result is False


def test_ensure_assets_all_present_and_valid(tmp_path, monkeypatch):
    """ensure_assets returns True when all assets exist with correct checksums."""
    from e_cli.models.bundled_assets import ASSET_MANIFEST
    # Create fake files with matching checksums
    for asset in ASSET_MANIFEST:
        content = b"fake"
        path = tmp_path / asset["name"]
        path.write_bytes(content)
        # Patch the manifest sha256 to match our fake content
        asset["sha256"] = hashlib.sha256(content).hexdigest()

    manager = BundledAssetManager(asset_dir=str(tmp_path))
    result = manager.ensure_assets()
    assert result is True


def test_bundled_asset_manager_creates_dir(tmp_path):
    """BundledAssetManager creates the asset directory if it doesn't exist."""
    new_dir = tmp_path / "new" / "nested"
    manager = BundledAssetManager(asset_dir=str(new_dir))
    assert new_dir.exists()
