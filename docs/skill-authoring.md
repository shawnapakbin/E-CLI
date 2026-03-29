# E-CLI Skill Authoring Guide

E-CLI supports a plugin/skill system for extending its capabilities. Skills are Python packages with a manifest and entrypoint.

## Skill Manifest Schema
```json
{
  "name": "github",
  "version": "1.0.0",
  "description": "GitHub workflow automation",
  "capabilities": ["issues", "prs", "ci-status"],
  "safetyClass": "mutating",
  "tools": ["http.get", "curl"],
  "entrypoint": "skills.github.main"
}
```

## Safety Classes
- `read-only`: No approval required
- `mutating`: Approval required
- `elevated`: Approval + explicit grant, can spawn sub-agents

## Entrypoint
- The entrypoint must expose a `BaseSkill` subclass with a `schema`, `policy`, and `execute()` method.

## Example
See `src/e_cli/skills/builtin/` for first-party skill examples.
