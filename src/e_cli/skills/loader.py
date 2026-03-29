"""Dynamic skill module loading with safety isolation."""
import importlib
from typing import Any
from e_cli.skills.base import BaseSkill

class SkillLoader:
    def load(self, entrypoint: str, manifest: dict[str, Any]) -> BaseSkill:
        """Dynamically load a skill class from entrypoint."""
        module_name, _, class_name = entrypoint.rpartition(".")
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        return cls(manifest)
