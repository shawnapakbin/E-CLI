# E-CLI Safety Model

E-CLI enforces strict safety boundaries for all tool and skill executions. The default is safe mode ON, requiring approval for any mutating or potentially dangerous operation.

## Safety Classes

| Class | Approval required | Examples |
|---|---|---|
| `read-only` | Never | `file.read`, `http.get`, `git.diff`, `rag.search`, `get_system_info`, `list_processes`, `get_logs`, `list_packages` |
| `mutating` | In safe mode | `file.write`, `shell`, `curl POST`, `browser.playwright`, MCP tools without declared class |
| `elevated` | Always (regardless of safe mode) | `system.install_package`, `system.uninstall_package`, `system.kill_process`, `system.list_drivers`, `ssh` |

## Policy Enforcement

All tool calls pass through `SafetyPolicy.evaluate()` before execution. The decision is one of:
- `allowed=True, requiresApproval=False` — executed immediately
- `allowed=True, requiresApproval=True` — routed through the approval gate
- `allowed=False` — rejected with an error result, never executed

Blocked shell patterns (e.g. `rm -rf /`, `format c:`, `dd if=`) are always denied regardless of safe mode.

## Approval Gate

Three approval modes are supported:

| Mode | Behaviour |
|---|---|
| `interactive` | Prompts the user in the terminal; `y`/`yes` approves, anything else denies |
| `auto-approve` | All mutating/elevated calls are approved without prompting |
| `deny` | All mutating/elevated calls are denied without prompting |

```bash
e-cli config set --approval-mode interactive
e-cli config set --approval-mode auto-approve
e-cli config set --approval-mode deny
```

## MCP Tool Safety

MCP tools inherit their `safetyClass` from the `safetyClass` field in the tool's `inputSchema`. Tools without a declared class default to `"mutating"` and require approval when safe mode is enabled.

## Skill Safety

Skills declare their `safetyClass` in `manifest.json`. The `SkillExecutor` enforces this class before calling `execute()`:
- `read-only` skills are always allowed
- `mutating` skills are blocked if `SafetyPolicy` denies the call
- `elevated` skills are always blocked when `safeMode=True` (the skill executor has no interactive approval gate; use `approvalMode=auto-approve` or disable safe mode for elevated skills)

Each skill receives a `_ScopedToolRouter` that re-enforces `SafetyPolicy` for any native tool calls the skill makes internally. Calls requiring approval are auto-denied in the scoped router.

## Audit Log

Every tool execution and approval decision is recorded in the session audit log:

```bash
e-cli sessions audit --last
e-cli sessions audit --session-id <id>
```

## Simulation / Dry Run

Preview what would be allowed or blocked without executing:

```bash
e-cli tools run --tool shell --command "rm -rf /tmp/test" --dry-run
```

## Trusted Read Commands

A set of shell commands are pre-trusted as read-only and never require approval even in safe mode:

```
ls, dir, pwd, Get-Location, cat, type, head, tail, echo,
systemctl status, journalctl, tasklist, ps
```

Additional trusted prefixes can be added via `SafetyPolicy(trustedReadCommands=(...))` in code.
