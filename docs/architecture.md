# E-CLI Architecture

E-CLI is a terminal-native LLM agent designed for local-first, offline-capable operation with optional connected mode. Its architecture is modular, supporting pluggable model providers, a robust tool/skill ecosystem, and strong safety boundaries.

## Core Components
- **Agent Loop**: Multi-step reasoning and tool-calling execution (`src/e_cli/agent/loop.py`).
- **Config System**: Pydantic-based config with env overlays (`src/e_cli/config.py`).
- **Provider Abstraction**: Modular model client interface (`src/e_cli/models/base.py`, `factory.py`).
- **Bundled Runtime**: Optional helper model with Vulkan backend (`src/e_cli/models/bundled_runtime.py`).
- **Skills Ecosystem**: Plugin/skill discovery, loading, and execution (`src/e_cli/skills/`).
- **Tool Layer**: Native tools (shell, file, git, http, browser, rag, etc.) with safety policy enforcement.
- **Memory**: SQLite-backed persistent memory and session compaction.
- **CLI**: Typer-based CLI with subcommands for all major features.

## Routing & Orchestration
- **Multi-provider routing**: Per-task and fallback chain config.
- **Sub-agent orchestration**: Parallel/isolated agent loops for automation and scheduling.

## Safety
- **Safety policy**: Approval, audit, and simulation modes.
- **Scoped tool access**: Per-tool, per-session, and time-limited grants.

See `docs/safety-model.md` for details.
