# E-CLI Architecture

E-CLI is a terminal-native LLM agent designed for local-first, offline-capable operation with optional connected/cloud mode. Its architecture is modular, supporting pluggable model providers, a robust tool/skill ecosystem, MCP server integration, and strong safety boundaries.

## High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI (Typer)                                   │
│  ask | chat | models | config | sessions | tools | docs | helper    │
│  --no-tui flag routes to legacy Rich output path                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      Textual TUI Layer                               │
│  ECLIApp (textual.App)                                               │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │  ChatPanel  │  │ ToolOutputPanel  │  │      StatusBar         │ │
│  │ (RichLog)   │  │  (DataTable)     │  │ session|provider|model │ │
│  └─────────────┘  └──────────────────┘  └────────────────────────┘ │
│  AgentWorker (textual Worker thread — runs AgentLoop async)         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                         AgentLoop                                    │
│  emits: TokenMessage, ToolStartMessage, ToolEndMessage              │
│  fallbackChain: tries providers in order on unreachable endpoint    │
└──────┬───────────────────────┬──────────────────────────────────────┘
       │                       │
┌──────▼──────┐        ┌───────▼──────────────────────────────────────┐
│  Model      │        │              ToolRouter                       │
│  Factory    │        │  native tools + MCP tools + skill tools       │
│  ┌────────┐ │        └───────┬──────────────┬────────────────────────┘
│  │Ollama  │ │                │              │
│  │LMStudio│ │        ┌───────▼──────┐ ┌────▼──────────┐
│  │Anthropic│ │       │  MCP_Bridge  │ │ SkillExecutor │
│  │Bundled │ │        │  (stdio)     │ │               │
│  └────────┘ │        └──────────────┘ └───────────────┘
└─────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────────┐
│  Native Tools                                                        │
│  shell | file | git | http | browser | ssh | curl | rag.search      │
│  playwright_tool.py  |  system_tool.py  |  doc_indexer.py           │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

### Agent Loop (`src/e_cli/agent/loop.py`)
Multi-step reasoning and tool-calling execution. Handles streaming tokens, tool dispatch, memory recall, safety checks, and session persistence. Supports a `fallbackChain` to automatically switch providers when the primary endpoint is unreachable.

### Config System (`src/e_cli/config.py`)
Pydantic-based config persisted at `~/.e-cli/config.json`. Supports env-var overlays (`ECLI_*`). Key fields added in v1:
- `anthropicApiKey` — Anthropic API key (also read from `ANTHROPIC_API_KEY` env var)
- `fallbackChain` — ordered list of provider names to try on failure
- `mcpServers` — list of MCP stdio server definitions

### Model Factory (`src/e_cli/models/factory.py`)
Dispatches to the correct `ModelClient` implementation based on `provider`:
- `ollama` → `OllamaClient`
- `lmstudio` → `LMStudioClient` (OpenAI-compatible)
- `vllm` → `VllmClient` (OpenAI-compatible)
- `bundled` → `BundledModelClient`
- `anthropic` → `AnthropicClient`

### Anthropic Provider (`src/e_cli/models/providers/anthropic.py`)
Implements the `ModelClient` protocol against the Anthropic Messages API. API key resolved from `ANTHROPIC_API_KEY` env var then `config.anthropicApiKey`. Rate-limit errors (429/529) trigger exponential back-off retry (delays `[1,2,4]`s, max 4 attempts). Static model list: `claude-opus-4-5`, `claude-sonnet-4-5`, `claude-haiku-3-5`.

### Textual TUI (`src/e_cli/ui/tui.py`)
`ECLIApp(textual.App)` with:
- `ChatPanel` (`RichLog`) — incremental streaming token display
- `ToolOutputPanel` (`DataTable`) — live tool call status with columns: tool, args preview, status, result preview
- `StatusBar` (`Footer`) — session ID, provider, model, turn counter
- `InputBar` (`Input`) — user message entry
- `AgentWorker` — background thread running `AgentLoop`, posting `TokenMessage`/`ToolStartMessage`/`ToolEndMessage`

Bypassed with `--no-tui` flag on `e-cli chat` and `e-cli ask`.

### MCP Bridge (`src/e_cli/mcp/bridge.py`)
Manages external MCP server subprocesses over stdio JSON-RPC 2.0:
- Launches servers at session start, calls `tools/list` to register tools
- 5-second startup timeout; failed servers are skipped without aborting the session
- One-restart logic on unexpected server exit; marks tools unavailable if restart fails
- Graceful shutdown: sends `shutdown` notification, terminates within 3 seconds
- Native tool schemas exposed as MCP definitions (`src/e_cli/mcp/native_schemas.py`)

### Playwright Tool (`src/e_cli/tools/playwright_tool.py`)
Session-scoped headless Chromium via `playwright.async_api`. Actions: `navigate`, `click`, `type`, `screenshot`, `evaluate`, `get_text`, `get_html`, `wait_for_selector`, `close`, `handoff_to_user`. All locator calls use `timeout=10_000`ms; `TimeoutError` returns `ToolResult(ok=False)`. Interactive handoff pauses agent control and opens a headed browser window.

### System Tool (`src/e_cli/tools/system_tool.py`)
Cross-platform OS management using `psutil` and subprocess calls. Actions: `get_system_info`, `list_processes`, `kill_process`, `get_logs`, `list_packages`, `install_package`, `uninstall_package`, `list_drivers`. OS dispatch: `journalctl`/`log show`/`wevtutil` for logs; `apt-get`/`dnf`/`brew`/`winget` for packages; `lsmod`/`driverquery` for drivers.

### Skills Execution Engine (`src/e_cli/skills/executor.py`)
Scans `~/.e-cli/skills/` at session start. Validates `manifest.json` against required fields, selects the correct OS variant entrypoint via `platform.system()`, dynamically imports the skill class, and registers its tools in `ToolRouter`. Unhandled skill exceptions are caught and returned as `ToolResult(ok=False)`. Each skill receives a `_ScopedToolRouter` that enforces `SafetyPolicy` before any native tool call.

### Documentation Indexer (`src/e_cli/docs/indexer.py`)
Fetches HTML pages, extracts visible text via `html.parser`, splits into 512-token chunks (word-boundary, 1 token ≈ 4 chars), and stores chunks in the RAG store. Tracks `lastIndexedAt` timestamps in `~/.e-cli/doc_index/manifest.json`. `refresh_stale` re-indexes URLs older than 24 hours.

### Memory (`src/e_cli/memory/`)
SQLite-backed persistent memory with token-budgeted conversation recall and automatic summary compaction. `MemoryService` wraps `MemoryStore` for session listing, entry loading, and compaction.

### Safety (`src/e_cli/safety/`)
`SafetyPolicy` classifies tool calls as `read-only`, `mutating`, or `elevated`. `requestApproval`/`requestApprovalWithMode` handle interactive, auto-approve, and deny modes. All approvals and denials are logged in the session audit log.

## File Layout

```
src/e_cli/
├── agent/
│   ├── loop.py          — multi-turn agent loop
│   └── protocol.py      — ToolCall / ToolResult / parse_tool_call
├── cli.py               — Typer CLI entry point
├── config.py            — AppConfig, MCPServerConfig, load/save
├── docs/
│   └── indexer.py       — DocIndexer
├── logging.py           — Rich-based logging setup
├── mcp/
│   ├── bridge.py        — MCPBridge
│   └── native_schemas.py — JSON schemas for 9 native tools
├── memory/
│   ├── service.py       — MemoryService
│   └── store.py         — MemoryStore (SQLite)
├── models/
│   ├── base.py          — ModelClient protocol, ModelMessage, ModelResponse
│   ├── discovery.py     — ModelDiscovery
│   ├── factory.py       — create_model_client()
│   └── providers/
│       ├── anthropic.py — AnthropicClient
│       ├── bundled.py   — BundledModelClient
│       ├── lmstudio.py  — LMStudioClient
│       ├── ollama.py    — OllamaClient
│       └── vllm.py      — VllmClient
├── safety/
│   ├── approval.py      — requestApproval / requestApprovalWithMode
│   └── policy.py        — SafetyPolicy / SafetyDecision
├── skills/
│   ├── base.py          — BaseSkill, SkillManifest, ToolDefinition
│   ├── executor.py      — SkillExecutor, _ScopedToolRouter, _SkillContext
│   ├── loader.py        — SkillLoader (dynamic import helper)
│   └── registry.py      — SkillRegistry (manifest discovery)
├── tools/
│   ├── browser_tool.py  — BrowserTool (simple headless)
│   ├── curl_tool.py     — CurlTool
│   ├── file_tool.py     — FileTool
│   ├── git_tool.py      — GitTool
│   ├── http_tool.py     — HttpTool
│   ├── playwright_tool.py — PlaywrightTool
│   ├── rag_tool.py      — RagTool
│   ├── router.py        — ToolRouter
│   ├── shell_tool.py    — ShellTool
│   ├── ssh_tool.py      — SshTool
│   └── system_tool.py   — SystemTool
└── ui/
    ├── messages.py      — printInfo / printError / printQuickTip
    └── tui.py           — ECLIApp, ChatPanel, ToolOutputPanel, StatusBar, InputBar

tests/
├── conftest.py          — shared fixtures
├── test_anthropic_client.py
├── test_doc_indexer.py
├── test_factory_and_router.py
├── test_mcp_bridge.py
├── test_playwright_tool.py
├── test_skill_executor.py
├── test_system_tool.py
├── test_tui.py
└── ...                  — additional unit/integration tests
```

## Dependencies

```toml
textual = ">=0.60.0"      # TUI framework
anthropic = ">=0.25.0"    # Anthropic Claude provider (optional)
playwright = ">=1.44.0"   # Browser automation (requires: playwright install chromium)
psutil = ">=6.0.0"        # Cross-platform system tool
```

Dev dependencies include `pytest`, `pytest-cov`, `pytest-asyncio`, `mypy`, and `ruff`. Test coverage target: ≥80% line coverage across all modules.

## Safety Model

See [safety-model.md](safety-model.md) for full details.

Safety classes:
- `read-only` — no approval required (e.g. `file.read`, `http.get`, `rag.search`, `get_system_info`)
- `mutating` — approval required in safe mode (e.g. `file.write`, `shell`, `browser.playwright`)
- `elevated` — always requires approval regardless of safe mode (e.g. `install_package`, `kill_process`, `list_drivers`)

MCP tools without a declared `safetyClass` default to `"mutating"`.
