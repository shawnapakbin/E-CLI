"""Skill discovery, manifest validation, and allowlist."""
import json
from pathlib import Path
from typing import Any

class SkillRegistry:
    def __init__(self, skills_dir: str = "~/.e-cli/skills"):
        self.skills_dir = Path(skills_dir).expanduser()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.skills = []

    def discover(self):
        """Discover skill manifests in the skills directory."""
        self.skills = []
        for manifest_path in self.skills_dir.glob("*/manifest.json"):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                self.skills.append(manifest)
            except Exception:
                continue
        return self.skills

    def validate_manifest(self, manifest: dict[str, Any]) -> bool:
        required = ["name", "version", "description", "capabilities", "safetyClass", "tools", "entrypoint"]
        return all(k in manifest for k in required)
