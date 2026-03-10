# E-CLI

E-CLI is a terminal-native LLM agent that runs with local or LAN-served models.

## Features
- Local + LAN model support: Ollama, LM Studio, vLLM (OpenAI-compatible)
- JSON tool-calling loop
- Shell execution with safe mode defaults
- File read/write tools with workspace boundary checks
- SQLite-backed persistent memory

## Install
```bash
pip install -e .[dev]
```

## Quick Start
```bash
e-cli doctor
e-cli config show
e-cli config set --provider ollama --model llama3
e-cli models list
e-cli models test
e-cli tools list
e-cli tools run --tool shell --command "echo hello"
e-cli ask "debug why nginx isn't starting"
```

## Safety
- Safe mode defaults to `on`
- Trusted read-only shell commands auto-run
- Mutating commands require approval
