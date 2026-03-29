# E-CLI

E-CLI is a terminal-native LLM agent that runs with local or LAN-served models.

## Features
- Local + LAN model support: Ollama, LM Studio, vLLM (OpenAI-compatible)
- Streaming model responses for supported providers
- JSON tool-calling loop
- Shell execution with safe mode defaults
- File read/write tools with workspace boundary checks
- Native `git.diff`, `http.get`, `browser`, `ssh`, `curl`, and `rag.search` tools for web inspection, retrieval, and remote execution
- SQLite-backed persistent memory
- Token-budgeted conversation recall with automatic summary compaction
- Explicit `sessions compact` command to condense older session history into reusable summaries
- Session audit log for approvals and tool executions
- Configurable inference parameters: temperature, top-p, max output tokens, and provider-specific raw options

## Install
If Python may not be installed yet, use the bootstrap installers.

Linux/macOS:

```bash
bash scripts/bootstrap_install.sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_install.ps1
```

Both bootstrap installers:
- Check whether Python is available
- Attempt to install Python when it is missing
- Launch the E-CLI installer automatically after Python is ready

If Python is already installed, you can run the E-CLI installer directly:

```bash
python3 scripts/install_ecli.py
```

Windows (PowerShell or Command Prompt):

```powershell
py -3 scripts/install_ecli.py
```

Install with development extras:

```bash
python3 scripts/install_ecli.py --dev
```

Windows (PowerShell or Command Prompt):

```powershell
py -3 scripts/install_ecli.py --dev
```

What the installer does:
- Installs E-CLI and dependencies with `pip --user`
- Detects your Python user scripts directory
- Adds that directory to your `PATH` on Linux, macOS, and Windows
- Prints a quick-start checklist when installation finishes

If you prefer manual install:

```bash
python3 -m pip install --user .
```

Windows (PowerShell or Command Prompt):

```powershell
py -3 -m pip install --user .
```

Verify:

```bash
e-cli --help
```

If `e-cli` is still not found in the current shell, open a new terminal.

Next steps:
1. Ensure a model host is running (for example `http://localhost:11434` for Ollama).
2. Run `e-cli models list`.
3. Select the desired model.
4. Run `e-cli`.

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
e-cli tools run --tool browser --url "https://example.com"
e-cli tools run --tool ssh --host example.com --command "uptime"
e-cli tools run --tool curl --url "https://api.example.com" --method GET
e-cli tools run --tool curl --url "https://api.example.com" --method POST --header "Authorization=Bearer token" --content '{"ok":true}'
e-cli tools run --tool rag.search --query "router execute" --corpus workspace --top-k 5
e-cli config set --temperature 0.7 --top-p 0.9 --max-output-tokens 512 --provider-option seed=42
e-cli config set --rag-corpus-default combined --rag-top-k 5
e-cli ask "debug why nginx isn't starting"
e-cli sessions compact --last --dry-run
e-cli sessions compact --last
e-cli sessions audit --last
```

## Configuration Guide

Use `e-cli config show` to inspect the active configuration, then update one or more fields with `e-cli config set`.

### Command Syntax Quick Reference
- Subcommands use hyphens, not concatenated words:
	- Correct: `e-cli safe-mode status`
	- Correct: `e-cli safe-mode set false`
	- Incorrect: `e-cli safemode status`
- `safe-mode` and `approval` are top-level command groups. They are not part of `config set` unless you are using flags.
- Boolean flags under `config set` use toggle-style options:
	- `--safe-mode` to enable
	- `--no-safe-mode` to disable
	- `--streaming-enabled` to enable streaming
	- `--no-streaming-enabled` to disable streaming

Examples:
```bash
e-cli safe-mode status
e-cli safe-mode set false
e-cli safe-mode set true

e-cli config set --no-safe-mode
e-cli config set --safe-mode --approval-mode interactive

e-cli config set --no-streaming-enabled
e-cli config set --streaming-enabled
```

Common mistakes and fixes:
- `e-cli safemode disable`
	- Use: `e-cli safe-mode set false`
- `e-cli config set --safe-mode false`
	- Use: `e-cli config set --no-safe-mode`

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
e-cli config set --safe-mode --approval-mode interactive
e-cli config set --no-safe-mode
e-cli safe-mode set false
e-cli safe-mode set true
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

### RAG Retrieval Defaults
- `ragCorpusDefault`: Default corpus for `rag.search` (`session`, `workspace`, or `combined`)
- `ragTopK`: Default number of ranked snippets returned by `rag.search` (1-10)

Examples:
```bash
e-cli config set --rag-corpus-default combined --rag-top-k 5
e-cli tools run --tool rag.search --query "session summary"
e-cli tools run --tool rag.search --query "ToolRouter execute" --corpus workspace --top-k 3
```

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
- Tool intent steps are shown as `AI Thinking: { ... }` lines before execution

### Troubleshooting Configuration
```bash
e-cli config show
e-cli doctor
e-cli models test
```

If model replies are too random, lower `temperature`. If responses are cut short, increase `maxOutputTokens` (if your provider supports it).


Use `e-cli tools list` to inspect the active safety policy for all tools.

---

## Documentation Index

See the following documents in the `docs/` folder for more details:

- [architecture.md](docs/architecture.md): Architecture overview
- [safety-model.md](docs/safety-model.md): Safety policy and enforcement
- [skill-authoring.md](docs/skill-authoring.md): Skill/plugin authoring guide
- [bundled-runtime.md](docs/bundled-runtime.md): Bundled helper model/runtime
- [offline-mode.md](docs/offline-mode.md): Offline/air-gapped deployment
- [connected-mode.md](docs/connected-mode.md): Connected/cloud mode
- [troubleshooting.md](docs/troubleshooting.md): Troubleshooting and FAQ
