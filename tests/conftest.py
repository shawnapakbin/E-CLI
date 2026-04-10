"""Shared pytest fixtures for the e-cli test suite."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from e_cli.config import AppConfig
from e_cli.safety.policy import SafetyPolicy


# ---------------------------------------------------------------------------
# Filesystem fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_skills_dir(tmp_path: Path) -> Path:
    """Return a temporary skills directory (empty, ready for skill subdirs)."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


# ---------------------------------------------------------------------------
# Config / policy fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_config() -> AppConfig:
    """Return a default AppConfig instance with safe defaults."""
    return AppConfig()


@pytest.fixture()
def safe_policy() -> SafetyPolicy:
    """Return a SafetyPolicy with safeMode=True."""
    return SafetyPolicy(safeMode=True, trustedReadCommands=())


@pytest.fixture()
def unsafe_policy() -> SafetyPolicy:
    """Return a SafetyPolicy with safeMode=False (all tools allowed)."""
    return SafetyPolicy(safeMode=False, trustedReadCommands=())


# ---------------------------------------------------------------------------
# RAG store fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_rag_store() -> MagicMock:
    """Return a mock RAG store with an add_chunks method that records calls."""
    store = MagicMock()
    store.add_chunks = MagicMock(return_value=None)
    store.search = MagicMock(return_value=[])
    return store


# ---------------------------------------------------------------------------
# Skill manifest helper
# ---------------------------------------------------------------------------


def make_skill_manifest(
    name: str = "test-skill",
    version: str = "1.0.0",
    description: str = "A test skill",
    capabilities: list[str] | None = None,
    safety_class: str = "read-only",
    tools: list[dict[str, Any]] | None = None,
    entrypoint: str = "skills.test.Skill",
    os_variants: dict[str, str] | None = None,
    knowledge_urls: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal valid skill manifest dict."""
    manifest: dict[str, Any] = {
        "name": name,
        "version": version,
        "description": description,
        "capabilities": capabilities or ["test"],
        "safetyClass": safety_class,
        "tools": tools or [{"name": "test.tool", "description": "A test tool"}],
        "entrypoint": entrypoint,
    }
    if os_variants is not None:
        manifest["osVariants"] = os_variants
    if knowledge_urls is not None:
        manifest["knowledgeUrls"] = knowledge_urls
    return manifest


@pytest.fixture()
def skill_manifest() -> dict[str, Any]:
    """Return a default valid skill manifest dict."""
    return make_skill_manifest()


def write_skill_manifest(skill_dir: Path, manifest: dict[str, Any]) -> None:
    """Write a manifest dict to skill_dir/manifest.json."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
