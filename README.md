# E-CLI

E-CLI is a terminal-native LLM agent that runs with local, LAN-served, or cloud models.

## Features

- Local + LAN model support: Ollama, LM Studio, vLLM (OpenAI-compatible)
- Cloud model support: Anthropic Claude (claude-opus-4-5, claude-sonnet-4-5, claude-haiku-3-5)
- Provider fallback chain: automatically tries the next provider when the primary is unreachable
- Textual TUI with chat panel, tool-output panel, and status bar (use `--no-tui` for plain Rich output)
- Streaming model responses for all supported providers
- JSON tool-calling loop with multi-turn reasoning
- Shell execution with safe mode defaults
- File read/write tools with workspace boundary checks
- Native tools: `git.diff`, `http.get`, `browser`, `ssh`, `curl`, `rag.search`, `system`, `browser.playwright`
- MCP (Model Context Protocol) stdio server support — connect any MCP-compatible tool server
- Playwright browser automation with interactive handoff (`browser.handoff_to_user`)
- Cross-platform system tools: process management, logs, package install/uninstall, driver listing
- Skills execution engine: drop skill folders into `~/.e-cli/skills/` for zero-code extensibility
- Per-OS skill variants: skills declare `windows`/`linux`/`macos` entrypoints automatically selected at runtime
- Documentation indexer: fetch and store docs into the RAG store for agent knowledge (`e-cli docs index`)
- SQLite-backed persistent memory with token-budgeted recall and automatic summary compaction
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

Windows:

```powershell
py -3 scripts/install_ecli.py
```

Install with development extras:

```bash
python3 scripts/install_ecli.py --dev
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

After installing, run the following once to download the Chromium browser used by the Playwright browser tool:

```bash
playwright install chromium
```

Verify:

```bash
e-cli --help
```

If `e-cli` is still not found in the current shell, open a new terminal.

Next steps:
1. Ensure a model host is running (e.g. `http://localhost:11434` for Ollama) or set `ANTHROPIC_API_KEY` for Claude.
2. Run `e-cli models list`.
3. Select the desired model.
4. Run `e-cli`.

## Quick Start

```bash
e-cli doctor
e-cli config show
e-cli config set --provider ollama --model llama3
e-cli config set --provider anthropic --model claude-sonnet-4-5
e-cli models list
e-cli models list --choose
e-cli models test
e-cli chat
e-cli chat --no-tui
e-cli ask "debug why nginx isn't starting"
e-cli ask --no-tui "summarise this repo"
e-cli tools list
e-cli tools run --tool shell --command "echo hello"
e-cli tools run --tool git.diff --path README.md
e-cli tools run --tool http.get --url "https://example.com"
e-cli tools run --tool browser --url "https://example.com"
e-cli tools run --tool ssh --host example.com --command "uptime"
e-cli tools run --tool curl --url "https://api.example.com" --method GET
e-cli tools run --tool rag.search --query "router execute" --corpus workspace --top-k 5
e-cli tools run --tool system --action get_system_info
e-cli docs index --url "https://docs.anthropic.com/en/api/getting-started"
e-cli docs index --skill my-skill
e-cli docs refresh
e-cli config set --temperature 0.7 --top-p 0.9 --max-output-tokens 512
e-cli sessions compact --last --dry-run
e-cli sessions compact --last
e-cli sessions audit --last
```

## Configuration Guide

Use `e-cli config show` to inspect the active configuration, then update fields with `e-cli config set`.

### Command Syntax Quick Reference

- Subcommands use hyphens: `e-cli safe-mode status`, not `e-cli safemode status`
- Boolean flags under `config set` use toggle-style options:
  - `--safe-mode` / `--no-safe-mode`
  - `--streaming-enabled` / `--no-streaming-enabled`

Examples:
```bash
e-cli safe-mode status
e-cli safe-mode set false
e-cli safe-mode set true
e-cli config set --no-safe-mode
e-cli config set --safe-mode --approval-mode interactive
```

### Core Runtime Settings

- `provider`: Model backend (`ollama`, `lmstudio`, `vllm`, `bundled`, `anthropic`)
- `model`: Active model name/id
- `endpoint`: Provider base URL
- `maxTurns`: Maximum reasoning/tool turns per prompt
- `timeoutSeconds`: Timeout for model/tool calls
- `fallbackChain`: Ordered list of providers to try when the primary is unreachable (default: `["ollama","lmstudio","bundled"]`)

Example:
```bash
e-cli config set --provider anthropic --model claude-sonnet-4-5
e-cli config set --provider lmstudio --endpoint http://localhost:1234 --model ibm/granite-4-h-tiny
```

### Anthropic Claude

Set your API key via environment variable or config:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
e-cli config set --provider anthropic --model claude-sonnet-4-5
```

Available models: `claude-opus-4-5`, `claude-sonnet-4-5`, `claude-haiku-3-5`

Rate-limit errors (HTTP 429/529) are automatically retried with exponential back-off (up to 4 attempts).

### MCP Servers

Add external MCP stdio servers to `~/.e-cli/config.json`:

```json
{
  "mcpServers": [
    {
      "name": "my-server",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {}
    }
  ]
}
```

Tools exposed by MCP servers are automatically registered and callable by the agent. Tools without a declared `safetyClass` default to `"mutating"` and require approval.

### Safety And Approvals

- `safeMode`: Enable/disable safety policy checks
- `approvalMode`: `interactive`, `auto-approve`, or `deny`

```bash
e-cli config set --safe-mode --approval-mode interactive
e-cli config set --no-safe-mode
e-cli approval status
```

### System Tool

The `system` tool provides cross-platform OS management:

```bash
e-cli tools run --tool system --action get_system_info
e-cli tools run --tool system --action list_processes
e-cli tools run --tool system --action get_logs --lines 50
e-cli tools run --tool system --action list_packages
e-cli tools run --tool system --action install_package --package curl
e-cli tools run --tool system --action list_drivers   # Linux/Windows only
```

Safety classifications:
- `read-only`: `list_processes`, `get_logs`, `get_system_info`, `list_packages`
- `elevated` (always requires approval): `install_package`, `uninstall_package`, `kill_process`, `list_drivers`

### Playwright Browser Tool

The `browser.playwright` tool drives a real headless Chromium browser:

```bash
e-cli tools run --tool browser.playwright --action navigate --url "https://example.com"
e-cli tools run --tool browser.playwright --action screenshot --path /tmp/shot.png
e-cli tools run --tool browser.playwright --action get_text --selector "h1"
e-cli tools run --tool browser.playwright --action evaluate --expression "document.title"
e-cli tools run --tool browser.playwright --action handoff_to_user
```

All Playwright actions are classified as `"mutating"` and require approval when `safeMode` is enabled.

### Documentation Indexer

Index documentation pages into the RAG store for agent knowledge:

```bash
e-cli docs index --url "https://docs.anthropic.com/en/api/getting-started"
e-cli docs index --url "https://playwright.dev/python/docs/intro" --corpus playwright-docs
e-cli docs index --skill my-skill          # indexes knowledgeUrls from skill manifest
e-cli docs refresh                         # re-indexes URLs older than 24 hours
e-cli docs refresh --max-age 12            # re-index if older than 12 hours
```

### Skills

Drop a skill folder into `~/.e-cli/skills/<name>/` with a `manifest.json`:

```json
{
  "name": "my-skill",
  "version": "1.0.0",
  "description": "Does something useful",
  "capabilities": ["example"],
  "safetyClass": "read-only",
  "tools": [{"name": "my.tool", "description": "A tool"}],
  "entrypoint": "skill.Skill",
  "osVariants": {
    "windows": "skill_win.py",
    "linux": "skill_linux.py",
    "macos": "skill_mac.py"
  },
  "knowledgeUrls": ["https://example.com/docs"]
}
```

See [docs/skill-authoring.md](docs/skill-authoring.md) for the full authoring guide.

### Inference Tuning

```bash
e-cli config set --temperature 0.2 --top-p 1.0
e-cli config set --temperature 0.7 --top-p 0.9 --max-output-tokens 512
e-cli config set --provider-option seed=42 --provider-option num_ctx=8192
```

### RAG Retrieval Defaults

```bash
e-cli config set --rag-corpus-default combined --rag-top-k 5
e-cli tools run --tool rag.search --query "session summary"
e-cli tools run --tool rag.search --query "ToolRouter execute" --corpus workspace --top-k 3
```

### Session Compaction

```bash
e-cli sessions compact --last --dry-run
e-cli sessions compact --session-id <id> --keep-recent 10 --target-tokens 2400
e-cli sessions show --last
e-cli sessions audit --last
```

### Troubleshooting Configuration

```bash
e-cli config show
e-cli doctor
e-cli models test
```

---

## Documentation Index

- [architecture.md](docs/architecture.md): Architecture overview
- [safety-model.md](docs/safety-model.md): Safety policy and enforcement
- [skill-authoring.md](docs/skill-authoring.md): Skill/plugin authoring guide
- [bundled-runtime.md](docs/bundled-runtime.md): Bundled helper model/runtime
- [offline-mode.md](docs/offline-mode.md): Offline/air-gapped deployment
- [connected-mode.md](docs/connected-mode.md): Connected/cloud mode
- [troubleshooting.md](docs/troubleshooting.md): Troubleshooting and FAQ
