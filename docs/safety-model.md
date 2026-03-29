# E-CLI Safety Model

E-CLI enforces strict safety boundaries for all tool and skill executions. The default is safe mode ON, requiring approval for any mutating or potentially dangerous operation.

## Safety Classes
- **read-only**: No approval required (e.g., file.read, http.get, rag.search)
- **mutating**: Approval required (e.g., file.write, curl POST, webhook)
- **elevated**: Explicit grant + approval, can spawn sub-agents (e.g., scheduler)

## Policy Enforcement
- All tool calls are checked against the active safety policy.
- Mutating/elevated tools require explicit user approval unless auto-approve is enabled.
- All approvals and denials are logged in the session audit log.

## Simulation Mode
- `e-cli tools run --dry-run` shows what would be allowed/blocked without executing.

## Approval Grants
- Per-tool, per-session, and time-limited grants are supported (Phase 6).

## Audit
- Every tool execution and approval is auditable via `e-cli sessions audit`.
