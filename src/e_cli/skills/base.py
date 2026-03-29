"""Abstract base class for E-CLI skills."""
from typing import Any

class BaseSkill:
    name: str
    version: str
    description: str
    capabilities: list[str]
    safetyClass: str
    tools: list[str]
    entrypoint: str

    def __init__(self, manifest: dict[str, Any]):
        self.manifest = manifest
        self.name = manifest.get("name", "")
        self.version = manifest.get("version", "")
        self.description = manifest.get("description", "")
        self.capabilities = manifest.get("capabilities", [])
        self.safetyClass = manifest.get("safetyClass", "read-only")
        self.tools = manifest.get("tools", [])
        self.entrypoint = manifest.get("entrypoint", "")

    def execute(self, *args, **kwargs):
        raise NotImplementedError()
