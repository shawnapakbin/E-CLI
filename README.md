# E-CLI

E-CLI is a terminal-native LLM agent that runs with local or LAN-served models.

## Features
- Local + LAN model support: Ollama, LM Studio, vLLM (OpenAI-compatible)
- Streaming model responses for supported providers
- JSON tool-calling loop
- Shell execution with safe mode defaults
- File read/write tools with workspace boundary checks
- Native `git.diff` and `http.get` tools for read-only inspection tasks
- SQLite-backed persistent memory
- Token-budgeted conversation recall with automatic summary compaction
- Explicit `sessions compact` command to condense older session history into reusable summaries
- Session audit log for approvals and tool executions
- Configurable inference parameters: temperature, top-p, max output tokens, and provider-specific raw options

## Install
```bash
1. run 'pip install -e .[dev]'
2. ensure you have a host running on "http://localhost:xxxxx"
3. run 'e-cli models list'
4. select the desired model
5. run 'e-cli'
```

## Quick Start
```bash
e-cli doctor
e-cli config show
e-cli config set --provider ollama --model llama3
e-cli models list
e-cli models list --choose
e-cli models test
e-cli chat
e-cli tools list
e-cli tools run --tool shell --command "echo hello"
e-cli tools run --tool git.diff --path README.md
e-cli tools run --tool http.get --url "https://example.com"
e-cli config set --temperature 0.7 --top-p 0.9 --max-output-tokens 512 --provider-option seed=42
e-cli ask "debug why nginx isn't starting"
e-cli sessions compact --last --dry-run
e-cli sessions compact --last
e-cli sessions audit --last
```

## Configuration Guide

Use `e-cli config show` to inspect the active configuration, then update one or more fields with `e-cli config set`.

### Core Runtime Settings
- `provider`: Model backend (`ollama`, `lmstudio`, `vllm`)
- `model`: Active model name/id
- `endpoint`: Provider base URL
- `maxTurns`: Maximum reasoning/tool turns per prompt
- `timeoutSeconds`: Timeout for model/tool calls

Example:
```bash
e-cli config set --provider lmstudio --endpoint http://localhost:1234 --model ibm/granite-4-h-tiny
```

### Safety And Approvals
- `safeMode`: Enable/disable safety policy checks
- `approvalMode`: `interactive`, `auto-approve`, or `deny`

Examples:
```bash
e-cli config set --safe-mode true --approval-mode interactive
e-cli safe-mode status
e-cli approval status
```

### Inference Tuning
- `temperature`: Sampling creativity (lower = more deterministic)
- `topP`: Nucleus sampling cutoff
- `maxOutputTokens`: Max generated tokens (`0` lets provider defaults apply)

Examples:
```bash
e-cli config set --temperature 0.2 --top-p 1.0
e-cli config set --temperature 0.7 --top-p 0.9 --max-output-tokens 512
```

### Provider-Specific Raw Options
Use repeated `--provider-option key=value` flags for backend-specific controls.

Examples:
```bash
e-cli config set --provider-option seed=42 --provider-option use_beam_search=true
e-cli config set --provider-option num_ctx=8192
```

Notes:
- Values are auto-parsed as `bool`, `int`, `float`, then `string`.
- Provider options are merged into the existing map (not fully replaced).

### Memory And Context Budget
- `memoryPath`: SQLite memory database path
- `conversationTokenBudget`: Approximate context budget loaded from memory
- `conversationSummaryBudget`: Budget reserved for compacted summary context

Example:
```bash
e-cli config set --memory-path ~/.e-cli/memory.db --conversation-token-budget 3200 --conversation-summary-budget 800
```

### Session Compaction
Use explicit compaction when a long-running session has accumulated too much low-value raw history and you want to preserve the important context in summarized form.

Examples:
```bash
e-cli sessions compact --last --dry-run
e-cli sessions compact --session-id d123488f-81ff-4c29-aa88-332ef5ce385c --keep-recent 10 --target-tokens 2400
e-cli sessions show --last
e-cli sessions audit --last
```

Notes:
- `sessions compact` rewrites stored session memory; it does not change the model's real context-window size.
- Older raw entries are summarized and pruned, while recent entries remain available verbatim.
- `--dry-run` previews what would be compacted before mutating the session.
- `sessions show` surfaces persisted summary coverage after compaction.

### Chat Session Behavior
- `e-cli` (no subcommand): Starts interactive chat by default
- `e-cli chat --last`: Resume last session id
- In chat: `/help`, `/session`, `/new`, `/exit`

### Troubleshooting Configuration
```bash
e-cli config show
e-cli doctor
e-cli models test
```

If model replies are too random, lower `temperature`. If responses are cut short, increase `maxOutputTokens` (if your provider supports it).

## Safety
- Safe mode defaults to `on`
- Trusted read-only shell commands auto-run
- Mutating commands require approval
