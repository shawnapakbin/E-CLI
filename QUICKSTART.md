# E-CLI Quick Start Guide

## Installation

```bash
# Using bootstrap installer (recommended)
bash scripts/bootstrap_install.sh

# Or direct install with Python
python3 scripts/install_ecli.py

# Or manual install
python3 -m pip install --user -e .
```

## First Steps

### 1. Run Doctor to Check Setup

```bash
e-cli doctor
```

Interactive menu will guide you through diagnostics and fixes.

### 2. Configure Your LLM Provider

#### Local (Ollama - Recommended for Beginners)
```bash
# Start Ollama first
e-cli models list --choose
e-cli models test
```

#### Cloud (OpenAI)
```bash
export OPENAI_API_KEY="your-api-key"
e-cli config set --provider openai --model gpt-4o
```

#### Cloud (Anthropic Claude)
```bash
export ANTHROPIC_API_KEY="your-api-key"
e-cli config set --provider anthropic --model claude-3-5-sonnet-20241022
```

#### Cloud (Google Gemini)
```bash
export GOOGLE_API_KEY="your-api-key"
e-cli config set --provider google --model gemini-2.0-flash-exp
```

### 3. Start Chatting

```bash
e-cli chat
# or simply
e-cli
```

## Key Features

### Interactive Menus

Most commands support interactive menus:

```bash
e-cli doctor           # Shows diagnostic menu
e-cli doctor --batch   # Use traditional CLI mode
```

### Skills Management

```bash
e-cli skills list              # List all skills
e-cli skills search python     # Search for skills
e-cli skills info shell        # Get skill details
e-cli skills stats             # Show statistics
```

### Knowledge Wiki

```bash
e-cli wiki init                          # Initialize wiki
e-cli wiki create "Python Async"         # Create a page
e-cli wiki list                          # List all pages
e-cli wiki search "docker"               # Search pages
e-cli wiki show "Python Async"           # Show page info
e-cli wiki backlinks "Python Async"      # Show backlinks
```

### Multiple Provider Support

E-CLI supports 6 LLM providers:

**Local:**
- Ollama (recommended for beginners)
- LM Studio
- vLLM

**Cloud:**
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude 3.5, Claude 3)
- Google (Gemini 2.0, Gemini 1.5)

### Configuration

```bash
# View current configuration
e-cli config show

# Set model parameters
e-cli config set --temperature 0.7 --top-p 0.9 --max-output-tokens 2048

# Enable/disable features
e-cli config set --safe-mode           # Enable safe mode
e-cli config set --no-safe-mode        # Disable safe mode
e-cli config set --streaming-enabled   # Enable streaming
```

### Session Management

```bash
e-cli sessions list             # List all sessions
e-cli sessions show --last      # Show last session
e-cli sessions compact --last   # Compact session memory
e-cli sessions audit --last     # View session audit log
```

### Tools

```bash
e-cli tools list                                    # List available tools
e-cli tools run --tool shell --command "ls -la"     # Run a tool
e-cli tools run --tool http.get --url "https://example.com"
```

## Advanced Features

### Personality Adaptation

E-CLI learns your preferences over time:
- Response verbosity
- Technical level
- Interaction style
- Domain expertise

### Wiki with Wikilinks

Create interconnected knowledge:

```markdown
---
title: Docker Networking
tags: [docker, networking]
---

# Docker Networking

Docker uses [[Container Networking]] to connect containers.

See also: [[Docker Compose]], [[Kubernetes]]
```

### Workflows

Create reusable workflows for common tasks:

```bash
# Example workflows included:
# - setup-python-project.yaml
# - analyze-codebase.yaml
```

## Tips

1. **Use Interactive Mode**: Run commands without flags to see interactive menus
2. **Explore Skills**: Skills make E-CLI extensible - create your own!
3. **Build Your Wiki**: Document what you learn in the wiki for future reference
4. **Try Different Providers**: Each LLM has different strengths
5. **Use Safe Mode**: Keeps you safe by requiring approval for dangerous commands

## Common Workflows

### Set Up a New Project

```bash
# Interactive
e-cli doctor
e-cli config set --provider ollama --model llama3
e-cli chat

# Or use workflow (when implemented)
e-cli workflow run setup-python-project --project-name myapp
```

### Daily Development

```bash
# Start your day
e-cli wiki create "Today's Goals" --category sessions

# Work with LLM assistance
e-cli chat

# Document learnings
e-cli wiki create "What I Learned" --category sessions
```

## Getting Help

```bash
e-cli --help              # Main help
e-cli skills --help       # Skills help
e-cli wiki --help         # Wiki help
e-cli doctor              # Run diagnostics
```

## Next Steps

1. ✅ Complete initial setup with `e-cli doctor`
2. ✅ Configure your preferred LLM provider
3. ✅ Create your first wiki page
4. ✅ Explore available skills
5. ✅ Start using E-CLI for your daily tasks!

For more information, see:
- `README.md` - Full documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- GitHub repository for latest updates
