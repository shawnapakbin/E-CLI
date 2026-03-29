"""Tests for bundled asset manager CLI commands (download-assets, verify-assets)."""

import pytest
from e_cli.cli import helper_download_assets, helper_verify_assets

def test_helper_download_assets(monkeypatch, tmp_path):
    class FakeManager:
        def __init__(self):
            self.asset_dir = tmp_path
        def ensure_assets(self):
            return True
    monkeypatch.setattr("e_cli.cli.BundledAssetManager", lambda: FakeManager())
    results = []
    monkeypatch.setattr("e_cli.cli.printInfo", lambda m: results.append(m))
    monkeypatch.setattr("e_cli.cli.printError", lambda m: results.append(m))
    helper_download_assets()
    assert any("downloaded" in m for m in results)

def test_helper_verify_assets(monkeypatch, tmp_path):
    class FakeManager:
        def __init__(self):
            self.asset_dir = tmp_path
        def verify_checksum(self, path, sha):
            return True
    monkeypatch.setattr("e_cli.cli.BundledAssetManager", lambda: FakeManager())
    monkeypatch.setattr("e_cli.models.bundled_assets.ASSET_MANIFEST", [
        {"name": "foo.bin", "sha256": "abc"},
        {"name": "bar.bin", "sha256": "def"},
    ])
    results = []
    monkeypatch.setattr("e_cli.cli.printInfo", lambda m: results.append(m))
    monkeypatch.setattr("e_cli.cli.printError", lambda m: results.append(m))
    helper_verify_assets()
    assert any("Checksum OK" in m for m in results)
    assert any("All asset checksums OK" in m for m in results)
