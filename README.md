# E-CLI

E-CLI is a terminal-native LLM agent that runs with local or LAN-served models.

## Features

### Core Capabilities
- **Multi-Provider Support**: Local (Ollama, LM Studio, vLLM) + Cloud (OpenAI, Anthropic, Google Gemini)
- **Interactive Menus**: Dual interface - traditional CLI flags or numbered option menus with auto-detection
- **Streaming Responses**: Real-time streaming for supported providers
- **JSON Tool-Calling**: Robust tool execution loop with approval system
- **Safe Mode**: Safety policy with automatic approval for read-only operations
- **Persistent Memory**: SQLite-backed session memory with automatic compaction
- **Session Management**: Complete session history, audit logs, and explicit compaction commands

### Advanced Features
- **Skills System**: Extensible plugin architecture with hot-reload capability
- **Knowledge Wiki**: Markdown wiki with wikilinks (`[[target]]`) and backlink tracking
- **Workflow Engine**: YAML-based workflow/macro system for automating common tasks
- **Personality Adaptation**: Learns user preferences (verbosity, technical level, interaction style)
- **RAG Search**: Semantic search over session history and workspace files
- **Shell Completion**: Tab completion for Bash, Zsh, and Fish shells

### Built-in Tools
- Shell execution with safe mode defaults
- File read/write with workspace boundary checks
- `git.diff`, `http.get`, `browser`, `ssh`, `curl` for web inspection and remote execution
- `rag.search` for semantic retrieval over sessions and workspace
- Configurable inference parameters: temperature, top-p, max tokens, provider-specific options

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

### First Time Setup
```bash
# Run interactive diagnostics
e-cli doctor

# Configure your LLM provider
e-cli config set --provider ollama --model llama3

# Or use cloud providers
e-cli config set --provider openai --model gpt-4o
e-cli config set --provider anthropic --model claude-3-5-sonnet-20241022
e-cli config set --provider google --model gemini-2.0-flash-exp

# List and test models
e-cli models list
e-cli models test

# Start chatting
e-cli chat
# or simply
e-cli
```

### Skills and Plugins
```bash
# List available skills
e-cli skills list

# Search for specific skills
e-cli skills search python

# Get skill details
e-cli skills info shell

# View skill statistics
e-cli skills stats
```

### Knowledge Wiki
```bash
# Initialize wiki
e-cli wiki init

# Create a page
e-cli wiki create "Docker Basics" --category tutorials

# List all pages
e-cli wiki list

# Search wiki
e-cli wiki search "networking"

# Show page details and backlinks
e-cli wiki show "Docker Basics"
e-cli wiki backlinks "Docker Basics"
```

### Workflows and Automation
```bash
# List available workflows
e-cli workflow list

# View workflow details
e-cli workflow show setup-python-project

# Run a workflow
e-cli workflow run setup-python-project --param project_name=myapp

# Create custom workflow
e-cli workflow create my-workflow --description "My automation"
```

### Tools and Commands
```bash
e-cli tools list
e-cli tools run --tool shell --command "echo hello"
e-cli tools run --tool git.diff --path README.md
e-cli tools run --tool http.get --url "https://example.com"
e-cli tools run --tool browser --url "https://example.com"
e-cli tools run --tool ssh --host example.com --command "uptime"
e-cli tools run --tool curl --url "https://api.example.com" --method GET
e-cli tools run --tool rag.search --query "router execute" --corpus workspace --top-k 5
```

### Sessions and Memory
```bash
# List sessions
e-cli sessions list

# Show session details
e-cli sessions show --last

# Compact session memory
e-cli sessions compact --last --dry-run
e-cli sessions compact --last

# View audit log
e-cli sessions audit --last
```

### Configuration
```bash
# View configuration
e-cli config show

# Tune inference parameters
e-cli config set --temperature 0.7 --top-p 0.9 --max-output-tokens 512

# Configure RAG defaults
e-cli config set --rag-corpus-default combined --rag-top-k 5

# Provider-specific options
e-cli config set --provider-option seed=42
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
- `provider`: Model backend (`ollama`, `lmstudio`, `vllm`, `openai`, `anthropic`, `google`)
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

## Safety
- Safe mode defaults to `on`
- Trusted read-only shell commands auto-run
- Mutating commands require approval
- Browser (read-only page inspection) auto-allowed in safe mode
- SSH always requires approval in safe mode
- Curl read-like methods (GET/HEAD/OPTIONS) auto-allowed; mutating methods (POST/PUT/PATCH/DELETE) require approval
- `rag.search` is read-only retrieval and auto-allowed in safe mode

Use `e-cli tools list` to inspect the active safety policy for all tools.

## Advanced Features

### Interactive Menus

E-CLI supports both traditional CLI flags and interactive numbered option menus. The system automatically detects TTY and switches modes accordingly.

```bash
# Interactive mode (shows numbered menu)
e-cli doctor

# Force batch mode
e-cli doctor --batch

# Menu options
e-cli config set --interactive-menus    # Enable menus
e-cli config set --no-interactive-menus # Disable menus
e-cli config set --menu-style rich      # rich, standard, minimal
```

When in interactive mode, you'll see numbered options like:
```
1. Run basic diagnostics
2. Run autofix
3. Test model connections
...
```

### Skills and Plugin System

Create extensible skills to add new capabilities to E-CLI.

**Skill Structure:**
```
~/.e-cli/skills/
├── my-skill/
│   ├── skill.yaml          # Metadata manifest
│   ├── skill.py            # Implementation
│   └── README.md
```

**skill.yaml Example:**
```yaml
name: my-skill
version: 1.0.0
description: My custom skill
author: me
category: automation
tags:
  - custom
  - automation
parameters:
  - name: input
    type: string
    required: true
```

**Commands:**
```bash
e-cli skills list                    # List all skills
e-cli skills info my-skill           # Show details
e-cli skills enable my-skill         # Enable skill
e-cli skills disable my-skill        # Disable skill
e-cli skills reload my-skill         # Hot-reload after changes
e-cli skills install ./my-skill      # Install from directory
e-cli skills search automation       # Search by query/tags
```

### Knowledge Wiki

Build an interconnected knowledge base using markdown with wikilinks.

**Features:**
- Markdown pages with YAML frontmatter
- Wikilinks: `[[Page Name]]` or `[[Page Name|Display Text]]`
- Automatic backlink tracking
- Categories and tags
- Full-text search with relevance scoring
- Fast JSON-based indexing

**Example Page:**
```markdown
---
title: Docker Networking
tags: [docker, networking, containers]
category: tutorials
---

# Docker Networking

Docker uses [[Container Networking]] to connect containers.

Key concepts:
- [[Bridge Networks]]
- [[Host Networks]]
- [[Overlay Networks]]

See also: [[Docker Compose]], [[Kubernetes]]
```

**Commands:**
```bash
e-cli wiki init                           # Initialize wiki
e-cli wiki create "Page Title"            # Create page
e-cli wiki list --category tutorials      # List by category
e-cli wiki search "docker"                # Search pages
e-cli wiki show "Docker Networking"       # Show page info
e-cli wiki backlinks "Container Networking" # Show backlinks
e-cli wiki index                          # Rebuild search index
e-cli wiki stats                          # Show statistics
```

### Workflow Automation

Define reusable workflows for common tasks using YAML.

**Workflow Structure:**
```yaml
name: setup-python-project
version: 1.0.0
description: Initialize a new Python project
tags: [python, setup]

parameters:
  - name: project_name
    type: string
    required: true
  - name: include_tests
    type: boolean
    default: true

steps:
  - name: Create directory structure
    tool: shell
    parameters:
      command: mkdir -p ${project_name}/{src,tests,docs}

  - name: Initialize git
    tool: shell
    parameters:
      command: cd ${project_name} && git init

  - name: Create pyproject.toml
    tool: file.write
    parameters:
      path: ${project_name}/pyproject.toml
      content: |
        [project]
        name = "${project_name}"
        version = "0.1.0"
```

**Commands:**
```bash
e-cli workflow list                    # List workflows
e-cli workflow show my-workflow        # Show details
e-cli workflow run my-workflow --param key=value
e-cli workflow run my-workflow --dry-run  # Preview execution
e-cli workflow create my-workflow      # Create template
e-cli workflow delete my-workflow      # Delete workflow
```

**Workflow Locations:**
- Global: `~/.e-cli/workflows/`
- Project: `./workflows/`

### Personality Adaptation

E-CLI learns your preferences over time and adapts its behavior.

**Tracked Traits:**
- **Verbosity**: Detailed explanations vs. concise answers
- **Technical Level**: Beginner-friendly vs. expert terminology
- **Interaction Style**: Formal vs. casual communication
- **Patience Level**: Step-by-step vs. quick solutions
- **Learning Mode**: Teaching vs. doing

The system stores preferences in SQLite and generates adaptive prompts based on your interaction history.

### Shell Completion

Install tab completion for your shell:

**Bash:**
```bash
# User installation
mkdir -p ~/.local/share/bash-completion/completions
cp scripts/completions/e-cli-completion.bash ~/.local/share/bash-completion/completions/e-cli
echo 'source ~/.local/share/bash-completion/completions/e-cli' >> ~/.bashrc
source ~/.bashrc
```

**Zsh:**
```bash
# User installation
mkdir -p ~/.zsh/completions
cp scripts/completions/_e-cli ~/.zsh/completions/
echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
echo 'autoload -Uz compinit && compinit' >> ~/.zshrc
exec zsh
```

**Fish:**
```bash
mkdir -p ~/.config/fish/completions
cp scripts/completions/e-cli.fish ~/.config/fish/completions/
# Fish loads automatically
```

See `docs/SHELL_COMPLETION.md` for detailed installation instructions.

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)**: Quick start guide for new users
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)**: Technical implementation details
- **[docs/SHELL_COMPLETION.md](docs/SHELL_COMPLETION.md)**: Shell completion installation guide

## Example Workflows

E-CLI includes example workflows to get you started:

- `setup-python-project.yaml`: Initialize Python projects with best practices
- `analyze-codebase.yaml`: Analyze codebase and generate reports

Create your own workflows in `~/.e-cli/workflows/` or `./workflows/` in your project.

