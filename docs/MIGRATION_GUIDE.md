# Migration Guide: E-CLI 1.x → 2.0

This guide helps existing E-CLI users migrate to version 2.0 with all the new enhancements.

## What's New in 2.0

- **Interactive Menus**: Choose between CLI flags and numbered option menus
- **Skills System**: Extensible plugin architecture
- **Multi-Provider Support**: OpenAI, Anthropic, and Google Gemini support
- **Knowledge Wiki**: Build interconnected knowledge bases
- **Workflow Automation**: YAML-based workflows for common tasks
- **Shell Completion**: Tab completion for Bash, Zsh, and Fish
- **Enhanced RAG**: Search across session, workspace, AND wiki
- **Personality Adaptation**: E-CLI learns your preferences

## Breaking Changes

### None!

E-CLI 2.0 is **100% backward compatible** with 1.x. All your existing:
- Configuration files
- Session history
- Memory databases
- Custom tools
- Workflows

...will continue to work without modification.

## New Configuration Options

E-CLI 2.0 adds new optional configuration fields:

### Interactive Menus

```bash
# Enable/disable interactive menus (default: true)
e-cli config set --interactive-menus
e-cli config set --no-interactive-menus

# Choose menu style
e-cli config set --menu-style rich      # Full formatting (default)
e-cli config set --menu-style standard  # Simple boxes
e-cli config set --menu-style minimal   # Text only
```

### Provider Options

```bash
# New cloud providers available
e-cli config set --provider openai --model gpt-4o
e-cli config set --provider anthropic --model claude-3-5-sonnet-20241022
e-cli config set --provider google --model gemini-2.0-flash-exp
```

### RAG Corpus

```bash
# Wiki now available as RAG corpus
e-cli config set --rag-corpus-default wiki
e-cli config set --rag-corpus-default combined  # session + workspace + wiki
```

## Migration Steps

### 1. Update E-CLI

```bash
cd /path/to/E-CLI
git pull origin main
python3 -m pip install --user -e .
```

### 2. Verify Installation

```bash
e-cli doctor
```

The doctor command now has an interactive menu! You can:
- Press a number to select an option
- Or use traditional `e-cli doctor --fix --all` flags

### 3. Install Shell Completion (Optional)

```bash
# For Bash
mkdir -p ~/.local/share/bash-completion/completions
cp scripts/completions/e-cli-completion.bash ~/.local/share/bash-completion/completions/e-cli
echo 'source ~/.local/share/bash-completion/completions/e-cli' >> ~/.bashrc
source ~/.bashrc

# For Zsh
mkdir -p ~/.zsh/completions
cp scripts/completions/_e-cli ~/.zsh/completions/
echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
echo 'autoload -Uz compinit && compinit' >> ~/.zshrc
exec zsh

# For Fish
mkdir -p ~/.config/fish/completions
cp scripts/completions/e-cli.fish ~/.config/fish/completions/
```

See `docs/SHELL_COMPLETION.md` for detailed instructions.

### 4. Try New Features

#### Interactive Menus

```bash
# Just run doctor - it auto-detects interactive terminal
e-cli doctor

# Force batch mode if needed
e-cli doctor --batch
```

#### Cloud Providers

```bash
# Set up OpenAI
export OPENAI_API_KEY="sk-..."
e-cli config set --provider openai --model gpt-4o
e-cli chat

# Set up Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
e-cli config set --provider anthropic --model claude-3-5-sonnet-20241022
e-cli chat

# Set up Google Gemini
export GOOGLE_API_KEY="..."
e-cli config set --provider google --model gemini-2.0-flash-exp
e-cli chat
```

#### Skills

```bash
# List available skills
e-cli skills list

# Try example skills
cp -r examples/skills/git-helper ~/.e-cli/skills/
e-cli skills info git-helper

# Use in conversation
e-cli
> Use git-helper to show repository status
```

#### Wiki

```bash
# Initialize wiki
e-cli wiki init

# Create a page
e-cli wiki create "Getting Started"

# Search wiki
e-cli wiki search "started"

# Use in RAG
e-cli tools run --tool rag.search --query "getting started" --corpus wiki
```

#### Workflows

```bash
# List workflows
e-cli workflow list

# Try example workflow
e-cli workflow run setup-python-project --param project_name=test --dry-run
```

## Upgrading Your Workflows

### Old Style (Still Works)

```bash
# Manual commands
e-cli tools run --tool shell --command "mkdir myproject"
e-cli tools run --tool shell --command "cd myproject && git init"
e-cli tools run --tool file.write --path "myproject/README.md" --content "# My Project"
```

### New Style (Recommended)

Create `~/.e-cli/workflows/my-workflow.yaml`:

```yaml
name: my-workflow
version: 1.0.0
description: My custom workflow
steps:
  - name: Create directory
    tool: shell
    parameters:
      command: mkdir ${project_name}

  - name: Initialize git
    tool: shell
    parameters:
      command: cd ${project_name} && git init

  - name: Create README
    tool: file.write
    parameters:
      path: ${project_name}/README.md
      content: "# ${project_name}"
```

Run with:
```bash
e-cli workflow run my-workflow --param project_name=myproject
```

## Updating Your Scripts

### Before (1.x)

```bash
#!/bin/bash
e-cli tools run --tool shell --command "git status"
e-cli tools run --tool shell --command "git log -5"
```

### After (2.0)

Option 1: Use workflows (recommended):
```yaml
# save as check-repo.yaml
name: check-repo
steps:
  - name: Show status
    tool: skill:git-helper
    parameters:
      operation: status

  - name: Show recent commits
    tool: skill:git-helper
    parameters:
      operation: log
      limit: 5
```

```bash
e-cli workflow run check-repo
```

Option 2: Use skills directly:
```bash
#!/bin/bash
# Copy git-helper skill to ~/.e-cli/skills/
# Then use in conversation:
e-cli chat << EOF
Use git-helper to show status and last 5 commits
EOF
```

## Common Migration Scenarios

### Scenario 1: Using Local Models

**No change needed!** Your existing Ollama/LM Studio/vLLM configuration works as-is.

You can now also add cloud providers for specific tasks:

```bash
# Keep local for general use
e-cli config set --provider ollama --model llama3

# Add cloud provider for complex tasks
# (in a script or one-off command)
e-cli config set --provider anthropic --model claude-3-5-sonnet-20241022
e-cli chat
# ... do complex task ...
# Switch back
e-cli config set --provider ollama --model llama3
```

### Scenario 2: Managing Session Memory

**No change needed!** Session management works exactly as before.

New features:
```bash
# Sessions now have personality tracking
# E-CLI learns your preferences over time

# View session stats (new command)
e-cli sessions stats

# Audit log still works
e-cli sessions audit --last
```

### Scenario 3: RAG Search

**Enhanced!** Your existing RAG searches work, plus new wiki corpus.

```bash
# Old way (still works)
e-cli tools run --tool rag.search --query "router" --corpus workspace

# New way (includes wiki)
e-cli tools run --tool rag.search --query "router" --corpus combined
```

### Scenario 4: Custom Tools

**No change needed!** Your custom tools continue to work.

You can now also create them as skills:

```bash
# Instead of adding to tools/
# Create in ~/.e-cli/skills/my-tool/
# with skill.yaml and skill.py

# Benefits:
# - Hot-reload (no restart needed)
# - Enable/disable dynamically
# - Version management
# - Easier sharing
```

## Troubleshooting

### Interactive Menus Not Showing

```bash
# Check if TTY detected
e-cli doctor --interactive

# Or disable menus
e-cli config set --no-interactive-menus
```

### Shell Completion Not Working

See `docs/SHELL_COMPLETION.md` for detailed troubleshooting.

Quick fix:
```bash
# Reload shell configuration
source ~/.bashrc  # or ~/.zshrc or fish_update_completions
```

### Cloud Provider Connection Issues

```bash
# Check API keys are set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
echo $GOOGLE_API_KEY

# Test connection
e-cli models test

# Check configuration
e-cli config show
```

### Skills Not Loading

```bash
# Check skills directory
ls ~/.e-cli/skills/

# Verify skill format
cat ~/.e-cli/skills/my-skill/skill.yaml

# Check skill status
e-cli skills list
e-cli skills info my-skill

# Reload skill
e-cli skills reload my-skill
```

### Wiki Not Initialized

```bash
# Initialize wiki
e-cli wiki init

# Verify
ls ~/.e-cli/wiki/
```

## Performance Considerations

E-CLI 2.0 is designed to be performant:

- Skills load on-demand (not all at startup)
- Wiki indexing is lazy (only when needed)
- RAG search has timeout limits
- Workflows stop on first failure

If you experience slowness:

```bash
# Disable features you don't use
e-cli config set --no-interactive-menus

# Limit RAG search
e-cli config set --rag-top-k 3

# Compact old sessions
e-cli sessions compact --last
```

## Getting Help

### Documentation

- `README.md` - Updated with all new features
- `QUICKSTART.md` - Quick start guide
- `docs/USAGE_EXAMPLES.md` - Comprehensive examples
- `docs/SHELL_COMPLETION.md` - Completion setup
- `docs/PROJECT_SUMMARY.md` - Technical overview

### Commands

```bash
# General help
e-cli --help

# Command-specific help
e-cli skills --help
e-cli wiki --help
e-cli workflow --help

# Interactive help in chat
e-cli
> /help
```

### Community

- Report issues: https://github.com/anthropics/e-cli/issues
- Discussions: https://github.com/anthropics/e-cli/discussions

## Next Steps

1. ✅ Install shell completion
2. ✅ Try interactive menus with `e-cli doctor`
3. ✅ Set up a cloud provider (optional)
4. ✅ Initialize wiki with `e-cli wiki init`
5. ✅ Install example skills from `examples/skills/`
6. ✅ Create your first workflow
7. ✅ Explore the documentation

Welcome to E-CLI 2.0! 🚀
