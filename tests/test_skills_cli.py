"""Test skill registry and CLI skills-list command."""
import json
import tempfile
from pathlib import Path
from e_cli.cli import skills_list
import pytest

def test_skills_list(monkeypatch):
    # Create a fake skills directory with a manifest
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "github"
        skill_dir.mkdir(parents=True)
        manifest = {
            "name": "github",
            "version": "1.0.0",
            "description": "GitHub workflow automation",
            "capabilities": ["issues"],
            "safetyClass": "mutating",
            "tools": ["http.get"],
            "entrypoint": "skills.github.main"
        }
        with open(skill_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        # Patch SkillRegistry to use this directory
        monkeypatch.setattr("e_cli.skills.registry.SkillRegistry.__init__", lambda self, skills_dir=tmpdir: setattr(self, "skills_dir", Path(skills_dir)))
        monkeypatch.setattr("e_cli.skills.registry.SkillRegistry.discover", lambda self: [manifest])
        results = []
        monkeypatch.setattr("e_cli.cli.printInfo", lambda m: results.append(m))
        skills_list()
        assert any("github v1.0.0" in m for m in results)
