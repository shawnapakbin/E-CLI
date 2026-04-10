"""Skills Execution Engine — loads, validates, and dispatches skill tool calls."""
from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import platform
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from e_cli.agent.protocol import ToolCall, ToolResult
from e_cli.safety.policy import SafetyPolicy
from e_cli.skills.base import BaseSkill, SkillManifest, ToolDefinition

if TYPE_CHECKING:
    from e_cli.tools.router import ToolRouter

_log = logging.getLogger(__name__)

# Maps platform.system() values to the osVariants key used in manifests.
_OS_MAP: dict[str, str] = {
    "Windows": "windows",
    "Linux": "linux",
    "Darwin": "macos",
}

_REQUIRED_FIELDS = {"name", "version", "description", "capabilities", "safetyClass", "tools", "entrypoint"}


class _ScopedToolRouter:
    """Thin wrapper around ToolRouter that enforces SafetyPolicy before every call."""

    def __init__(self, router: "ToolRouter", policy: SafetyPolicy) -> None:
        self._router = router
        self._policy = policy

    def execute(self, tool_call: ToolCall, timeout_seconds: int = 30) -> ToolResult:
        decision = self._policy.evaluate(tool_call)
        if not decision.allowed:
            return ToolResult(ok=False, output=f"Blocked by safety policy: {decision.reason}")
        if decision.requiresApproval:
            # In the scoped router we auto-deny elevated calls that require interactive approval
            # to avoid blocking the skill execution loop.  Callers that need interactive approval
            # should use the top-level AgentLoop approval gate instead.
            return ToolResult(
                ok=False,
                output=f"Skill tool call requires approval: {decision.reason}",
            )
        return self._router.execute(tool_call, timeout_seconds)


class _SkillContext:
    """Runtime context passed to each skill so it can inspect the current OS."""

    def __init__(self, os_id: str) -> None:
        self.os = os_id


class SkillExecutor:
    """Discovers, loads, and executes skills from ~/.e-cli/skills/."""

    def __init__(
        self,
        skills_dir: str | Path = "~/.e-cli/skills",
        router: "ToolRouter | None" = None,
        safety_policy: SafetyPolicy | None = None,
    ) -> None:
        self._skills_dir = Path(skills_dir).expanduser()
        self._router = router
        self._safety_policy = safety_policy or SafetyPolicy(
            safeMode=True,
            trustedReadCommands=(),
        )
        # Maps tool_name → (skill_instance, manifest)
        self._tool_map: dict[str, tuple[BaseSkill, SkillManifest]] = {}
        self._manifests: list[SkillManifest] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all(self) -> None:
        """Scan skills directory and load all valid skills.  Called at session start."""
        self._tool_map.clear()
        self._manifests.clear()

        if not self._skills_dir.exists():
            _log.debug("Skills directory does not exist: %s", self._skills_dir)
            return

        for manifest_path in sorted(self._skills_dir.glob("*/manifest.json")):
            skill_dir = manifest_path.parent
            skill = self._load_skill(skill_dir)
            if skill is None:
                continue
            # Retrieve the manifest we stored during _load_skill
            manifest = self._manifests[-1] if self._manifests else None
            if manifest is None:
                continue
            for tool_def in manifest.tools:
                self._tool_map[tool_def.name] = (skill, manifest)

    def registered_tools(self) -> list[ToolDefinition]:
        """Return all tool definitions registered from loaded skills."""
        seen: dict[str, ToolDefinition] = {}
        for manifest in self._manifests:
            for tool_def in manifest.tools:
                seen[tool_def.name] = tool_def
        return list(seen.values())

    def execute(self, tool_name: str, args: dict) -> ToolResult:
        """Dispatch a tool call to the owning skill, enforcing SafetyPolicy first."""
        entry = self._tool_map.get(tool_name)
        if entry is None:
            return ToolResult(ok=False, output=f"Unknown skill tool: {tool_name}")

        skill, manifest = entry

        # Build a synthetic ToolCall so we can run it through SafetyPolicy.
        # We use "shell" as a proxy tool name for policy evaluation when the
        # skill tool name is not natively known; the safetyClass on the manifest
        # is the authoritative classification.
        synthetic_call = ToolCall(tool="shell", command=tool_name, reason=f"skill:{manifest.name}")

        # Override policy decision based on manifest safetyClass.
        if manifest.safetyClass == "elevated":
            # Always route through policy; deny if policy says DENY or requires approval
            # (the skill executor has no interactive approval gate).
            decision = self._safety_policy.evaluate(synthetic_call)
            if not decision.allowed or decision.requiresApproval:
                return ToolResult(ok=False, output=f"Blocked by safety policy: {decision.reason}")
        elif manifest.safetyClass == "mutating":
            decision = self._safety_policy.evaluate(synthetic_call)
            if not decision.allowed:
                return ToolResult(ok=False, output=f"Blocked by safety policy: {decision.reason}")
        # "read-only" skills are always allowed.

        # Build scoped router for the skill.
        scoped_router: _ScopedToolRouter | None = None
        if self._router is not None:
            scoped_router = _ScopedToolRouter(self._router, self._safety_policy)

        # Build context with current OS identifier.
        os_id = _OS_MAP.get(platform.system(), platform.system().lower())
        context = _SkillContext(os_id=os_id)

        try:
            # Build a ToolCall for the skill's execute method.
            skill_call = ToolCall(tool="shell", command=tool_name, **{
                k: v for k, v in args.items()
                if k in ToolCall.model_fields and k not in ("tool", "command")
            })
            result = skill.execute(skill_call, scoped_router)
            if not isinstance(result, ToolResult):
                return ToolResult(ok=True, output=str(result))
            return result
        except Exception as exc:
            _log.error(
                "Skill '%s' raised an unhandled exception for tool '%s': %s\n%s",
                manifest.name,
                tool_name,
                exc,
                traceback.format_exc(),
            )
            return ToolResult(ok=False, output=f"Skill error: {exc}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_skill(self, skill_dir: Path) -> BaseSkill | None:
        """Load and validate a single skill from its directory.  Returns None on failure."""
        manifest_path = skill_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        # Parse raw JSON.
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _log.warning("Skill at '%s': failed to parse manifest.json: %s", skill_dir, exc)
            return None

        # Check required fields before Pydantic validation so we can report missing ones.
        if isinstance(raw, dict):
            missing = _REQUIRED_FIELDS - raw.keys()
            if missing:
                _log.warning(
                    "Skill at '%s': manifest missing required fields: %s — skipping.",
                    skill_dir,
                    sorted(missing),
                )
                return None

        # Validate with Pydantic.
        try:
            manifest = SkillManifest(**raw)
        except (ValidationError, TypeError) as exc:
            _log.warning("Skill at '%s': manifest validation failed: %s — skipping.", skill_dir, exc)
            return None

        # Select the correct entrypoint for the current OS.
        entrypoint = self._select_entrypoint(manifest)
        if entrypoint is None:
            os_id = _OS_MAP.get(platform.system(), platform.system().lower())
            _log.warning(
                "Skill '%s' at '%s': no compatible variant for OS '%s' and no default entrypoint — skipping.",
                manifest.name,
                skill_dir,
                os_id,
            )
            return None

        # Dynamically import the entrypoint module.
        try:
            skill_instance = self._import_entrypoint(entrypoint, skill_dir, manifest)
        except Exception as exc:
            _log.warning(
                "Skill '%s' at '%s': failed to import entrypoint '%s': %s — skipping.",
                manifest.name,
                skill_dir,
                entrypoint,
                exc,
            )
            return None

        self._manifests.append(manifest)
        _log.debug("Loaded skill '%s' v%s from '%s'.", manifest.name, manifest.version, skill_dir)
        return skill_instance

    def _select_entrypoint(self, manifest: SkillManifest) -> str | None:
        """Return the entrypoint string for the current OS, or None if unavailable.

        This is a pure function — it only reads manifest data and platform.system().
        """
        os_map = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}
        current = os_map.get(platform.system(), "")
        return manifest.osVariants.get(current) or manifest.entrypoint or None

    def _import_entrypoint(
        self, entrypoint: str, skill_dir: Path, manifest: SkillManifest
    ) -> BaseSkill:
        """Dynamically import a skill class from a dotted module path or a .py file path."""
        raw_manifest = manifest.model_dump()

        # If entrypoint looks like a file path (ends with .py), load as a file-based module.
        if entrypoint.endswith(".py"):
            module_path = skill_dir / entrypoint
            spec = importlib.util.spec_from_file_location(
                f"_skill_{manifest.name}", module_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create module spec for '{module_path}'")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            # Expect a class named 'Skill' or matching the manifest name (PascalCase).
            cls_name = "Skill"
            if not hasattr(mod, cls_name):
                # Try PascalCase of manifest name.
                cls_name = manifest.name.replace("-", "_").replace(" ", "_").title().replace("_", "")
            cls = getattr(mod, cls_name)
            return cls(raw_manifest)

        # Otherwise treat as dotted module path: "package.module.ClassName"
        module_name, _, class_name = entrypoint.rpartition(".")
        if not module_name:
            raise ImportError(f"Invalid entrypoint format: '{entrypoint}'")
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        return cls(raw_manifest)
