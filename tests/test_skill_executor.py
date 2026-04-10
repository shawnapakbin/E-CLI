"""Unit tests for SkillExecutor — manifest validation, OS variant selection,
safety enforcement, and exception isolation.

Validates: Requirements 9 and 10
"""
from __future__ import annotations

import json
import platform
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from e_cli.agent.protocol import ToolCall, ToolResult
from e_cli.safety.policy import SafetyPolicy
from e_cli.skills.base import BaseSkill, SkillManifest, ToolDefinition
from e_cli.skills.executor import SkillExecutor, _OS_MAP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest(
    name: str = "test-skill",
    version: str = "1.0.0",
    description: str = "A test skill",
    capabilities: list[str] | None = None,
    safety_class: str = "read-only",
    tools: list[dict] | None = None,
    entrypoint: str = "skills.test.Skill",
    os_variants: dict[str, str] | None = None,
    knowledge_urls: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "version": version,
        "description": description,
        "capabilities": capabilities or ["test"],
        "safetyClass": safety_class,
        "tools": tools or [{"name": "test.tool", "description": "A test tool"}],
        "entrypoint": entrypoint,
        **({"osVariants": os_variants} if os_variants is not None else {}),
        **({"knowledgeUrls": knowledge_urls} if knowledge_urls is not None else {}),
    }


def _write_manifest(skill_dir: Path, manifest: dict[str, Any]) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class _DummySkill(BaseSkill):
    """Minimal skill that returns ok=True for any call."""

    def execute(self, tool_call: ToolCall, router: Any) -> ToolResult:
        return ToolResult(ok=True, output="dummy-ok")


class _RaisingSkill(BaseSkill):
    """Skill that always raises an exception."""

    def execute(self, tool_call: ToolCall, router: Any) -> ToolResult:
        raise RuntimeError("skill exploded")


# ---------------------------------------------------------------------------
# SkillManifest model tests
# ---------------------------------------------------------------------------

class TestSkillManifest:
    def test_valid_manifest_parses(self):
        m = SkillManifest(**_make_manifest())
        assert m.name == "test-skill"
        assert m.version == "1.0.0"
        assert m.safetyClass == "read-only"
        assert m.osVariants == {}
        assert m.knowledgeUrls == []

    def test_os_variants_and_knowledge_urls(self):
        m = SkillManifest(**_make_manifest(
            os_variants={"windows": "skill_win.py", "linux": "skill_linux.py"},
            knowledge_urls=["https://example.com/docs"],
        ))
        assert m.osVariants["windows"] == "skill_win.py"
        assert m.knowledgeUrls == ["https://example.com/docs"]

    def test_invalid_safety_class_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SkillManifest(**_make_manifest(safety_class="unknown"))

    def test_tools_are_tool_definitions(self):
        m = SkillManifest(**_make_manifest(
            tools=[{"name": "my.tool", "description": "desc", "inputSchema": {"type": "object"}}]
        ))
        assert isinstance(m.tools[0], ToolDefinition)
        assert m.tools[0].name == "my.tool"


# ---------------------------------------------------------------------------
# Manifest validation in _load_skill
# ---------------------------------------------------------------------------

class TestManifestValidation:
    def test_missing_required_field_skips_skill(self, tmp_path, caplog):
        """Skill with missing 'version' field should be skipped with a warning."""
        skill_dir = tmp_path / "bad-skill"
        manifest = _make_manifest()
        del manifest["version"]
        _write_manifest(skill_dir, manifest)

        executor = SkillExecutor(skills_dir=tmp_path)
        with caplog.at_level("WARNING"):
            result = executor._load_skill(skill_dir)

        assert result is None
        assert "missing required fields" in caplog.text.lower() or "version" in caplog.text

    def test_invalid_json_skips_skill(self, tmp_path, caplog):
        skill_dir = tmp_path / "bad-json"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")

        executor = SkillExecutor(skills_dir=tmp_path)
        with caplog.at_level("WARNING"):
            result = executor._load_skill(skill_dir)

        assert result is None

    def test_missing_manifest_returns_none(self, tmp_path):
        skill_dir = tmp_path / "no-manifest"
        skill_dir.mkdir(parents=True)

        executor = SkillExecutor(skills_dir=tmp_path)
        result = executor._load_skill(skill_dir)
        assert result is None

    def test_all_required_fields_present_proceeds(self, tmp_path):
        """A manifest with all required fields should not be skipped at validation stage."""
        skill_dir = tmp_path / "good-skill"
        _write_manifest(skill_dir, _make_manifest())

        executor = SkillExecutor(skills_dir=tmp_path)
        # _load_skill will fail at import stage (entrypoint doesn't exist), but NOT at validation.
        # We just verify it doesn't return None due to validation failure.
        # Patch _import_entrypoint to avoid real import.
        dummy = _DummySkill(_make_manifest())
        with patch.object(executor, "_import_entrypoint", return_value=dummy):
            result = executor._load_skill(skill_dir)
        assert result is not None


# ---------------------------------------------------------------------------
# OS variant selection
# ---------------------------------------------------------------------------

class TestSelectEntrypoint:
    def _manifest(self, entrypoint: str = "", os_variants: dict | None = None) -> SkillManifest:
        return SkillManifest(**_make_manifest(entrypoint=entrypoint, os_variants=os_variants or {}))

    def test_returns_os_variant_when_available(self):
        executor = SkillExecutor()
        manifest = self._manifest(
            entrypoint="default.py",
            os_variants={"windows": "win.py", "linux": "linux.py", "macos": "mac.py"},
        )
        with patch("platform.system", return_value="Linux"):
            result = executor._select_entrypoint(manifest)
        assert result == "linux.py"

    def test_falls_back_to_default_entrypoint(self):
        executor = SkillExecutor()
        manifest = self._manifest(entrypoint="default.py", os_variants={"windows": "win.py"})
        with patch("platform.system", return_value="Linux"):
            result = executor._select_entrypoint(manifest)
        assert result == "default.py"

    def test_returns_none_when_no_variant_and_no_default(self):
        executor = SkillExecutor()
        manifest = self._manifest(entrypoint="", os_variants={"windows": "win.py"})
        with patch("platform.system", return_value="Linux"):
            result = executor._select_entrypoint(manifest)
        assert result is None

    def test_deterministic_for_same_os(self):
        """_select_entrypoint is a pure function — same inputs always give same output."""
        executor = SkillExecutor()
        manifest = self._manifest(
            entrypoint="default.py",
            os_variants={"linux": "linux.py"},
        )
        with patch("platform.system", return_value="Linux"):
            results = [executor._select_entrypoint(manifest) for _ in range(10)]
        assert len(set(results)) == 1

    def test_windows_variant(self):
        executor = SkillExecutor()
        manifest = self._manifest(os_variants={"windows": "win.py"})
        with patch("platform.system", return_value="Windows"):
            result = executor._select_entrypoint(manifest)
        assert result == "win.py"

    def test_macos_variant(self):
        executor = SkillExecutor()
        manifest = self._manifest(os_variants={"macos": "mac.py"})
        with patch("platform.system", return_value="Darwin"):
            result = executor._select_entrypoint(manifest)
        assert result == "mac.py"

    def test_unknown_os_falls_back_to_default(self):
        executor = SkillExecutor()
        manifest = self._manifest(entrypoint="default.py", os_variants={"linux": "linux.py"})
        with patch("platform.system", return_value="FreeBSD"):
            result = executor._select_entrypoint(manifest)
        assert result == "default.py"


# ---------------------------------------------------------------------------
# load_all and registered_tools
# ---------------------------------------------------------------------------

class TestLoadAll:
    def test_empty_skills_dir_loads_nothing(self, tmp_path):
        executor = SkillExecutor(skills_dir=tmp_path)
        executor.load_all()
        assert executor.registered_tools() == []

    def test_nonexistent_skills_dir_loads_nothing(self, tmp_path):
        executor = SkillExecutor(skills_dir=tmp_path / "nonexistent")
        executor.load_all()
        assert executor.registered_tools() == []

    def test_valid_skill_registers_tools(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        _write_manifest(skill_dir, _make_manifest(
            tools=[{"name": "my.tool", "description": "desc"}]
        ))
        executor = SkillExecutor(skills_dir=tmp_path)
        dummy = _DummySkill(_make_manifest())
        with patch.object(executor, "_import_entrypoint", return_value=dummy):
            executor.load_all()

        tools = executor.registered_tools()
        assert any(t.name == "my.tool" for t in tools)

    def test_invalid_skill_does_not_abort_load(self, tmp_path):
        # One bad skill, one good skill.
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "manifest.json").write_text("{bad json", encoding="utf-8")

        good_dir = tmp_path / "good"
        _write_manifest(good_dir, _make_manifest(
            name="good-skill",
            tools=[{"name": "good.tool", "description": "desc"}],
        ))

        executor = SkillExecutor(skills_dir=tmp_path)
        dummy = _DummySkill(_make_manifest(name="good-skill"))
        with patch.object(executor, "_import_entrypoint", return_value=dummy):
            executor.load_all()

        tools = executor.registered_tools()
        assert any(t.name == "good.tool" for t in tools)


# ---------------------------------------------------------------------------
# execute — dispatch and exception isolation
# ---------------------------------------------------------------------------

class TestExecute:
    def _executor_with_skill(
        self,
        skill: BaseSkill,
        manifest_overrides: dict | None = None,
        safety_policy: SafetyPolicy | None = None,
    ) -> SkillExecutor:
        raw = _make_manifest(**(manifest_overrides or {}))
        manifest = SkillManifest(**raw)
        executor = SkillExecutor(
            safety_policy=safety_policy or SafetyPolicy(
                safeMode=False, trustedReadCommands=()
            )
        )
        # Manually inject the skill.
        for tool_def in manifest.tools:
            executor._tool_map[tool_def.name] = (skill, manifest)
        executor._manifests.append(manifest)
        return executor

    def test_unknown_tool_returns_error(self):
        executor = SkillExecutor()
        result = executor.execute("nonexistent.tool", {})
        assert result.ok is False
        assert "Unknown skill tool" in result.output

    def test_successful_execute_returns_ok(self):
        skill = _DummySkill(_make_manifest())
        executor = self._executor_with_skill(skill)
        result = executor.execute("test.tool", {})
        assert result.ok is True
        assert result.output == "dummy-ok"

    def test_exception_in_skill_returns_error_result(self):
        skill = _RaisingSkill(_make_manifest())
        executor = self._executor_with_skill(skill)
        result = executor.execute("test.tool", {})
        assert result.ok is False
        assert "skill exploded" in result.output

    def test_exception_does_not_propagate(self):
        """Unhandled skill exceptions must never propagate out of execute()."""
        skill = _RaisingSkill(_make_manifest())
        executor = self._executor_with_skill(skill)
        # Should not raise.
        result = executor.execute("test.tool", {})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# Safety enforcement
# ---------------------------------------------------------------------------

class TestSafetyEnforcement:
    def _make_policy(self, safe_mode: bool = True) -> SafetyPolicy:
        return SafetyPolicy(safeMode=safe_mode, trustedReadCommands=())

    def test_elevated_skill_blocked_when_policy_denies(self):
        """For elevated skills, SafetyPolicy is always consulted.

        Validates: Requirements 9.6 — Skill safety enforcement property.
        """
        skill = _DummySkill(_make_manifest(safety_class="elevated"))
        policy = self._make_policy(safe_mode=True)
        executor = SkillExecutor(safety_policy=policy)

        raw = _make_manifest(safety_class="elevated")
        manifest = SkillManifest(**raw)
        for tool_def in manifest.tools:
            executor._tool_map[tool_def.name] = (skill, manifest)
        executor._manifests.append(manifest)

        # With safe_mode=True the shell tool requires approval, so the scoped
        # router will block it.  The execute() method should NOT call skill.execute
        # when the policy blocks the call.
        # We verify by patching skill.execute to detect if it was called.
        called = []
        original_execute = skill.execute

        def spy_execute(tc, router):
            called.append(True)
            return original_execute(tc, router)

        skill.execute = spy_execute  # type: ignore[method-assign]

        # With safe_mode=True, shell commands require approval (not outright blocked).
        # The policy returns allowed=True, requiresApproval=True for shell.
        # Our executor treats requiresApproval as a deny for skill calls.
        result = executor.execute("test.tool", {})
        # With safe_mode=True, elevated skills require approval which the executor
        # treats as a deny — skill.execute must NOT be called.
        assert not called, "skill.execute should not be called for elevated skill with safe_mode=True"
        assert result.ok is False

    def test_read_only_skill_always_allowed(self):
        """Read-only skills bypass the approval gate."""
        skill = _DummySkill(_make_manifest(safety_class="read-only"))
        policy = self._make_policy(safe_mode=True)
        executor = SkillExecutor(safety_policy=policy)

        raw = _make_manifest(safety_class="read-only")
        manifest = SkillManifest(**raw)
        for tool_def in manifest.tools:
            executor._tool_map[tool_def.name] = (skill, manifest)
        executor._manifests.append(manifest)

        result = executor.execute("test.tool", {})
        assert result.ok is True

    def test_elevated_skill_allowed_when_safe_mode_off(self):
        """With safe_mode=False, elevated skills are allowed through."""
        skill = _DummySkill(_make_manifest(safety_class="elevated"))
        policy = self._make_policy(safe_mode=False)
        executor = SkillExecutor(safety_policy=policy)

        raw = _make_manifest(safety_class="elevated")
        manifest = SkillManifest(**raw)
        for tool_def in manifest.tools:
            executor._tool_map[tool_def.name] = (skill, manifest)
        executor._manifests.append(manifest)

        result = executor.execute("test.tool", {})
        assert result.ok is True


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    _HAS_HYPOTHESIS = True
except ImportError:
    _HAS_HYPOTHESIS = False


if _HAS_HYPOTHESIS:
    _os_names = st.sampled_from(["Windows", "Linux", "Darwin", "FreeBSD", "SunOS"])
    _os_variant_keys = st.sampled_from(["windows", "linux", "macos"])
    _entrypoint_str = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="._-"))

    @given(
        os_name=_os_names,
        os_variants=st.dictionaries(_os_variant_keys, _entrypoint_str, max_size=3),
        default_ep=_entrypoint_str | st.just(""),
    )
    @settings(max_examples=200)
    def test_select_entrypoint_deterministic(os_name, os_variants, default_ep):
        """**Validates: Requirements 10.2**

        OS variant selection is a pure function — same manifest + same OS always
        returns the same entrypoint string (no side effects).
        """
        executor = SkillExecutor()
        manifest = SkillManifest(
            name="prop-skill",
            version="1.0",
            description="prop test",
            capabilities=["test"],
            safetyClass="read-only",
            tools=[],
            entrypoint=default_ep,
            osVariants=os_variants,
        )
        with patch("platform.system", return_value=os_name):
            result1 = executor._select_entrypoint(manifest)
            result2 = executor._select_entrypoint(manifest)

        assert result1 == result2, (
            f"Non-deterministic: got '{result1}' then '{result2}' for OS={os_name}"
        )

    @given(
        os_name=_os_names,
        os_variants=st.dictionaries(_os_variant_keys, _entrypoint_str, max_size=3),
        default_ep=_entrypoint_str | st.just(""),
    )
    @settings(max_examples=200)
    def test_select_entrypoint_correctness(os_name, os_variants, default_ep):
        """**Validates: Requirements 10.2, 10.3, 10.4**

        The returned entrypoint is always either:
        - The OS-specific variant (if one exists for the current OS)
        - The default entrypoint (if no variant matches but default is non-empty)
        - None (if neither variant nor default is available)
        """
        executor = SkillExecutor()
        manifest = SkillManifest(
            name="prop-skill",
            version="1.0",
            description="prop test",
            capabilities=["test"],
            safetyClass="read-only",
            tools=[],
            entrypoint=default_ep,
            osVariants=os_variants,
        )
        with patch("platform.system", return_value=os_name):
            result = executor._select_entrypoint(manifest)

        os_key = _OS_MAP.get(os_name, "")
        expected_variant = os_variants.get(os_key, "")
        if expected_variant:
            assert result == expected_variant
        elif default_ep:
            assert result == default_ep
        else:
            assert result is None


# ---------------------------------------------------------------------------
# SkillLoader tests
# ---------------------------------------------------------------------------

class TestSkillLoader:
    """Tests for SkillLoader.load() dynamic import."""

    def test_load_valid_entrypoint(self):
        """SkillLoader can load a class from a dotted module path."""
        from e_cli.skills.loader import SkillLoader
        loader = SkillLoader()
        # Load OllamaClient which takes (endpoint, ...) as a simple class
        # We use a class that accepts a dict as first arg: BaseSkill subclass
        # Use _DummySkill from this test module via its full path
        manifest = _make_manifest()
        # _DummySkill is defined in this test file; use a known importable class
        # that accepts a dict: SkillManifest(**manifest) works, but loader calls cls(manifest)
        # Use a simple class from e_cli that accepts a dict
        # Actually test with a real BaseSkill subclass by patching importlib
        from unittest.mock import patch, MagicMock
        mock_cls = MagicMock(return_value=MagicMock())
        mock_mod = MagicMock()
        mock_mod.MySkill = mock_cls
        with patch("importlib.import_module", return_value=mock_mod):
            result = loader.load("some.module.MySkill", manifest)
        assert result is not None
        mock_cls.assert_called_once_with(manifest)

    def test_load_invalid_module_raises(self):
        """SkillLoader raises ImportError for a non-existent module."""
        from e_cli.skills.loader import SkillLoader
        loader = SkillLoader()
        with pytest.raises((ImportError, ModuleNotFoundError, AttributeError)):
            loader.load("nonexistent.module.ClassName", {})

    def test_load_invalid_class_raises(self):
        """SkillLoader raises AttributeError for a missing class in a valid module."""
        from e_cli.skills.loader import SkillLoader
        loader = SkillLoader()
        with pytest.raises(AttributeError):
            loader.load("e_cli.skills.base.NonExistentClass", {})


# ---------------------------------------------------------------------------
# SkillRegistry tests
# ---------------------------------------------------------------------------

class TestSkillRegistry:
    """Tests for SkillRegistry.discover() and validate_manifest()."""

    def test_discover_empty_dir(self, tmp_path):
        from e_cli.skills.registry import SkillRegistry
        registry = SkillRegistry(skills_dir=str(tmp_path))
        skills = registry.discover()
        assert skills == []

    def test_discover_finds_valid_manifests(self, tmp_path):
        from e_cli.skills.registry import SkillRegistry
        skill_dir = tmp_path / "my-skill"
        _write_manifest(skill_dir, _make_manifest(name="my-skill"))
        registry = SkillRegistry(skills_dir=str(tmp_path))
        skills = registry.discover()
        assert len(skills) == 1
        assert skills[0]["name"] == "my-skill"

    def test_discover_skips_invalid_json(self, tmp_path):
        from e_cli.skills.registry import SkillRegistry
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "manifest.json").write_text("{bad json", encoding="utf-8")
        registry = SkillRegistry(skills_dir=str(tmp_path))
        skills = registry.discover()
        assert skills == []

    def test_discover_multiple_skills(self, tmp_path):
        from e_cli.skills.registry import SkillRegistry
        for i in range(3):
            _write_manifest(tmp_path / f"skill-{i}", _make_manifest(name=f"skill-{i}"))
        registry = SkillRegistry(skills_dir=str(tmp_path))
        skills = registry.discover()
        assert len(skills) == 3

    def test_validate_manifest_valid(self):
        from e_cli.skills.registry import SkillRegistry
        registry = SkillRegistry.__new__(SkillRegistry)
        assert registry.validate_manifest(_make_manifest()) is True

    def test_validate_manifest_missing_field(self):
        from e_cli.skills.registry import SkillRegistry
        registry = SkillRegistry.__new__(SkillRegistry)
        manifest = _make_manifest()
        del manifest["version"]
        assert registry.validate_manifest(manifest) is False

    def test_validate_manifest_all_required_fields(self):
        from e_cli.skills.registry import SkillRegistry
        registry = SkillRegistry.__new__(SkillRegistry)
        required = ["name", "version", "description", "capabilities", "safetyClass", "tools", "entrypoint"]
        for field in required:
            m = _make_manifest()
            del m[field]
            assert registry.validate_manifest(m) is False, f"Should fail without {field}"

    def test_discover_stores_results_on_instance(self, tmp_path):
        from e_cli.skills.registry import SkillRegistry
        _write_manifest(tmp_path / "s1", _make_manifest(name="s1"))
        registry = SkillRegistry(skills_dir=str(tmp_path))
        registry.discover()
        assert len(registry.skills) == 1


# ---------------------------------------------------------------------------
# _ScopedToolRouter tests
# ---------------------------------------------------------------------------

class TestScopedToolRouter:
    """Tests for the _ScopedToolRouter wrapper."""

    def test_blocked_call_returns_error(self):
        from e_cli.skills.executor import _ScopedToolRouter
        from e_cli.tools.router import ToolRouter
        from pathlib import Path

        router = ToolRouter(workspaceRoot=Path.cwd())
        policy = SafetyPolicy(safeMode=True, trustedReadCommands=())
        scoped = _ScopedToolRouter(router, policy)

        # file.write requires approval in safe mode — should be denied by scoped router
        tc = ToolCall(tool="file.write", path="x.txt", content="data")
        result = scoped.execute(tc)
        assert result.ok is False

    def test_allowed_call_passes_through(self, monkeypatch):
        from e_cli.skills.executor import _ScopedToolRouter
        from e_cli.tools.router import ToolRouter
        from pathlib import Path

        router = ToolRouter(workspaceRoot=Path.cwd())
        policy = SafetyPolicy(safeMode=True, trustedReadCommands=())
        scoped = _ScopedToolRouter(router, policy)

        # git.diff is read-only and always allowed
        monkeypatch.setattr(
            "e_cli.tools.router.GitTool.diff",
            lambda self, path, timeout_seconds: type("R", (), {"ok": True, "output": "diff"})(),
        )
        tc = ToolCall(tool="git.diff", path="README.md")
        result = scoped.execute(tc)
        assert result.ok is True

    def test_denied_call_returns_blocked_message(self):
        from e_cli.skills.executor import _ScopedToolRouter
        from e_cli.tools.router import ToolRouter
        from pathlib import Path

        router = ToolRouter(workspaceRoot=Path.cwd())
        # Use a policy that blocks shell with dangerous pattern
        policy = SafetyPolicy(
            safeMode=True,
            trustedReadCommands=(),
            blockedShellPatterns=("rm -rf /",),
        )
        scoped = _ScopedToolRouter(router, policy)
        tc = ToolCall(tool="shell", command="sudo rm -rf / --no-preserve-root")
        result = scoped.execute(tc)
        assert result.ok is False
        assert "Blocked" in result.output


# ---------------------------------------------------------------------------
# Additional executor tests for missing coverage
# ---------------------------------------------------------------------------

class TestExecutorAdditional:
    """Additional tests to cover missing executor.py lines."""

    def test_mutating_skill_allowed_when_safe_mode_off(self):
        """Mutating skill is allowed when safe mode is off."""
        skill = _DummySkill(_make_manifest(safety_class="mutating"))
        policy = SafetyPolicy(safeMode=False, trustedReadCommands=())
        executor = SkillExecutor(safety_policy=policy)
        raw = _make_manifest(safety_class="mutating")
        manifest = SkillManifest(**raw)
        for tool_def in manifest.tools:
            executor._tool_map[tool_def.name] = (skill, manifest)
        executor._manifests.append(manifest)
        result = executor.execute("test.tool", {})
        assert result.ok is True

    def test_skill_returning_non_tool_result(self):
        """Skill returning a non-ToolResult value is wrapped in ToolResult."""
        class _StringSkill(BaseSkill):
            def execute(self, tool_call, router):
                return "plain string result"

        skill = _StringSkill(_make_manifest())
        executor = SkillExecutor(safety_policy=SafetyPolicy(safeMode=False, trustedReadCommands=()))
        raw = _make_manifest()
        manifest = SkillManifest(**raw)
        for tool_def in manifest.tools:
            executor._tool_map[tool_def.name] = (skill, manifest)
        executor._manifests.append(manifest)
        result = executor.execute("test.tool", {})
        assert result.ok is True
        assert "plain string result" in result.output

    def test_execute_with_router_creates_scoped_router(self, tmp_path):
        """When a router is provided, execute creates a scoped router for the skill."""
        from pathlib import Path
        from e_cli.tools.router import ToolRouter

        router = ToolRouter(workspaceRoot=Path.cwd())
        skill = _DummySkill(_make_manifest())
        policy = SafetyPolicy(safeMode=False, trustedReadCommands=())
        executor = SkillExecutor(router=router, safety_policy=policy)
        raw = _make_manifest()
        manifest = SkillManifest(**raw)
        for tool_def in manifest.tools:
            executor._tool_map[tool_def.name] = (skill, manifest)
        executor._manifests.append(manifest)
        result = executor.execute("test.tool", {})
        assert result.ok is True

    def test_load_skill_no_compatible_variant_no_default(self, tmp_path, caplog):
        """Skill with osVariants but no match and no default entrypoint is skipped."""
        skill_dir = tmp_path / "variant-skill"
        manifest = _make_manifest(
            entrypoint="",
            os_variants={"windows": "win.py"},
        )
        _write_manifest(skill_dir, manifest)
        executor = SkillExecutor(skills_dir=tmp_path)
        with patch("platform.system", return_value="Linux"):
            with caplog.at_level("WARNING"):
                result = executor._load_skill(skill_dir)
        assert result is None

    def test_load_skill_import_failure_skips(self, tmp_path, caplog):
        """Skill that fails to import entrypoint is skipped with a warning."""
        skill_dir = tmp_path / "import-fail-skill"
        _write_manifest(skill_dir, _make_manifest(entrypoint="nonexistent.module.Class"))
        executor = SkillExecutor(skills_dir=tmp_path)
        with caplog.at_level("WARNING"):
            result = executor._load_skill(skill_dir)
        assert result is None

    def test_import_entrypoint_py_file(self, tmp_path):
        """_import_entrypoint loads a .py file-based skill."""
        # Create a minimal skill .py file
        skill_dir = tmp_path / "file-skill"
        skill_dir.mkdir()
        skill_py = skill_dir / "skill.py"
        skill_py.write_text(
            "from e_cli.skills.base import BaseSkill\n"
            "from e_cli.agent.protocol import ToolCall, ToolResult\n"
            "class Skill(BaseSkill):\n"
            "    def execute(self, tc, router):\n"
            "        return ToolResult(ok=True, output='file-skill')\n",
            encoding="utf-8",
        )
        manifest = SkillManifest(**_make_manifest(name="file-skill", entrypoint="skill.py"))
        executor = SkillExecutor(skills_dir=tmp_path)
        skill = executor._import_entrypoint("skill.py", skill_dir, manifest)
        assert skill is not None

    def test_import_entrypoint_invalid_format_raises(self):
        """_import_entrypoint raises ImportError for invalid dotted path."""
        executor = SkillExecutor()
        manifest = SkillManifest(**_make_manifest())
        with pytest.raises(ImportError):
            executor._import_entrypoint("NoDotsHere", Path("."), manifest)

    def test_skill_context_os_attribute(self):
        """_SkillContext exposes the os attribute."""
        from e_cli.skills.executor import _SkillContext
        ctx = _SkillContext(os_id="linux")
        assert ctx.os == "linux"
