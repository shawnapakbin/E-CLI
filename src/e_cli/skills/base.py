"""Abstract base class and manifest model for E-CLI skills."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from e_cli.agent.protocol import ToolCall, ToolResult


class ToolDefinition(BaseModel):
    """Describes a single tool exposed by a skill."""

    name: str
    description: str
    inputSchema: dict[str, Any] = {}


class SkillManifest(BaseModel):
    """Validated manifest for a skill loaded from manifest.json."""

    name: str
    version: str
    description: str
    capabilities: list[str]
    safetyClass: Literal["read-only", "mutating", "elevated"]
    tools: list[ToolDefinition]
    entrypoint: str = ""
    osVariants: dict[str, str] = {}   # {"windows": "skill_win.py", ...}
    knowledgeUrls: list[str] = []


class BaseSkill:
    """Abstract base class that all skill implementations must subclass."""

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

    def execute(self, tool_call: ToolCall, router: Any) -> ToolResult:
        raise NotImplementedError()
