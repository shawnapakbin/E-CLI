# E-CLI Skill Authoring Guide

Skills are drop-in plugins stored under `~/.e-cli/skills/<name>/`. E-CLI discovers and loads them automatically at session start — no core code changes required.

## Directory Layout

```
~/.e-cli/skills/
└── my-skill/
    ├── manifest.json
    └── skill.py          ← entrypoint (or skill_win.py / skill_linux.py / skill_mac.py)
```

## Manifest Schema

```json
{
  "name": "my-skill",
  "version": "1.0.0",
  "description": "Does something useful",
  "capabilities": ["example"],
  "safetyClass": "read-only",
  "tools": [
    {
      "name": "my.tool",
      "description": "A tool exposed by this skill",
      "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}
    }
  ],
  "entrypoint": "skill.Skill",
  "osVariants": {
    "windows": "skill_win.py",
    "linux": "skill_linux.py",
    "macos": "skill_mac.py"
  },
  "knowledgeUrls": [
    "https://example.com/docs"
  ]
}
```

### Required Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Unique skill identifier |
| `version` | string | Semver version string |
| `description` | string | Human-readable description |
| `capabilities` | list[string] | Tags describing what the skill does |
| `safetyClass` | string | `"read-only"`, `"mutating"`, or `"elevated"` |
| `tools` | list[object] | Tool definitions exposed to the agent |
| `entrypoint` | string | Dotted module path (`pkg.module.ClassName`) or `.py` filename |

### Optional Fields

| Field | Type | Description |
|---|---|---|
| `osVariants` | dict | Per-OS entrypoint overrides: `"windows"`, `"linux"`, `"macos"` |
| `knowledgeUrls` | list[string] | Documentation URLs indexed by `e-cli docs index --skill <name>` |

## Safety Classes

| Class | Approval required | Use when |
|---|---|---|
| `read-only` | Never | Skill only reads data |
| `mutating` | In safe mode | Skill writes files, calls APIs, etc. |
| `elevated` | Always | Skill installs software, kills processes, etc. |

The `SkillExecutor` enforces the declared `safetyClass` via `SafetyPolicy` before calling `execute()`. Elevated skills are always blocked when `safeMode=True` (no interactive approval gate in the skill executor).

## Entrypoint

The entrypoint must be a `BaseSkill` subclass with an `execute()` method:

```python
# skill.py
from e_cli.skills.base import BaseSkill
from e_cli.agent.protocol import ToolCall, ToolResult

class Skill(BaseSkill):
    def execute(self, tool_call: ToolCall, router) -> ToolResult:
        query = tool_call.query or ""
        return ToolResult(ok=True, output=f"Result for: {query}")
```

- `tool_call` — the `ToolCall` instance dispatched by the agent
- `router` — a `_ScopedToolRouter` that lets the skill call native tools (shell, file, http, etc.) while still enforcing `SafetyPolicy`

Unhandled exceptions are caught by `SkillExecutor`, logged with full traceback, and returned as `ToolResult(ok=False)` — the agent session continues.

## Per-OS Variants

When `osVariants` is declared, `SkillExecutor` selects the matching entrypoint using `platform.system()`:

| `platform.system()` | `osVariants` key |
|---|---|
| `Windows` | `windows` |
| `Linux` | `linux` |
| `Darwin` | `macos` |

If no variant matches the current OS, the default `entrypoint` is used. If neither matches, the skill is skipped with a warning.

The current OS identifier is also available at runtime via `context.os` (passed as the `router` argument's `_SkillContext`).

## Knowledge URLs

List documentation URLs in `knowledgeUrls` and they will be indexed into the RAG store when the user runs:

```bash
e-cli docs index --skill my-skill
```

The agent can then retrieve relevant documentation chunks via `rag.search`.

## Calling Native Tools from a Skill

Use the `router` argument to call native tools:

```python
from e_cli.agent.protocol import ToolCall, ToolResult

class Skill(BaseSkill):
    def execute(self, tool_call: ToolCall, router) -> ToolResult:
        if router is not None:
            result = router.execute(ToolCall(tool="shell", command="uname -a"))
            return ToolResult(ok=result.ok, output=result.output)
        return ToolResult(ok=False, output="No router available")
```

The scoped router enforces `SafetyPolicy` — calls that require approval are auto-denied to avoid blocking the skill execution loop.

## Example: Read-Only Skill

```json
{
  "name": "disk-usage",
  "version": "1.0.0",
  "description": "Reports disk usage for a path",
  "capabilities": ["system"],
  "safetyClass": "read-only",
  "tools": [{"name": "disk.usage", "description": "Get disk usage for a path"}],
  "entrypoint": "skill.Skill"
}
```

```python
# skill.py
import shutil
from e_cli.skills.base import BaseSkill
from e_cli.agent.protocol import ToolCall, ToolResult

class Skill(BaseSkill):
    def execute(self, tool_call: ToolCall, router) -> ToolResult:
        path = tool_call.path or "/"
        usage = shutil.disk_usage(path)
        return ToolResult(
            ok=True,
            output=f"total={usage.total // 1024**3}GB used={usage.used // 1024**3}GB free={usage.free // 1024**3}GB"
        )
```

## Validation

`SkillExecutor` validates manifests at load time. Missing required fields produce a warning and the skill is skipped. Invalid JSON also produces a warning. Neither aborts the session.

To inspect loaded skills:

```bash
e-cli tools skills-list
```
