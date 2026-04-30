# E-CLI Usage Examples and Guides

This guide provides practical examples for using E-CLI's advanced features.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Multi-Provider Configuration](#multi-provider-configuration)
3. [Skills System](#skills-system)
4. [Knowledge Wiki](#knowledge-wiki)
5. [Workflows](#workflows)
6. [Interactive Menus](#interactive-menus)
7. [Session Management](#session-management)
8. [Advanced Scenarios](#advanced-scenarios)

## Getting Started

### Initial Setup

```bash
# Run diagnostics to check your setup
e-cli doctor

# The doctor will show you:
# - Python version
# - E-CLI installation status
# - Model provider availability
# - Memory system health
# - Configuration status
```

### First Configuration

```bash
# Configure for local Ollama
e-cli config set --provider ollama --model llama3

# Test the connection
e-cli models test

# Start chatting
e-cli
```

## Multi-Provider Configuration

### Local Providers

#### Ollama
```bash
# Configure Ollama
e-cli config set --provider ollama \
  --endpoint http://localhost:11434 \
  --model llama3

# List available models
e-cli models list

# Choose interactively
e-cli models list --choose

# Test the model
e-cli models test
```

#### LM Studio
```bash
# Configure LM Studio
e-cli config set --provider lmstudio \
  --endpoint http://localhost:1234 \
  --model ibm/granite-4-h-tiny

# Test connection
e-cli models test
```

#### vLLM
```bash
# Configure vLLM server
e-cli config set --provider vllm \
  --endpoint http://localhost:8000 \
  --model meta-llama/Llama-3-8b

# Test connection
e-cli models test
```

### Cloud Providers

#### OpenAI
```bash
# Set API key (do this first)
export OPENAI_API_KEY="sk-..."

# Configure OpenAI
e-cli config set --provider openai --model gpt-4o

# Or GPT-3.5 for faster responses
e-cli config set --provider openai --model gpt-3.5-turbo

# Test connection
e-cli models test
```

#### Anthropic Claude
```bash
# Set API key (do this first)
export ANTHROPIC_API_KEY="sk-ant-..."

# Configure Claude 3.5 Sonnet
e-cli config set --provider anthropic \
  --model claude-3-5-sonnet-20241022

# Or Claude 3 Opus for most capable
e-cli config set --provider anthropic \
  --model claude-3-opus-20240229

# Test connection
e-cli models test
```

#### Google Gemini
```bash
# Set API key (do this first)
export GOOGLE_API_KEY="..."

# Configure Gemini 2.0 Flash (fastest)
e-cli config set --provider google \
  --model gemini-2.0-flash-exp

# Or Gemini 1.5 Pro for complex tasks
e-cli config set --provider google \
  --model gemini-1.5-pro

# Test connection
e-cli models test
```

### Switching Between Providers

```bash
# Quick switch to different provider
e-cli config set --provider ollama --model llama3
e-cli chat

# Switch to cloud for complex task
e-cli config set --provider anthropic --model claude-3-5-sonnet-20241022
e-cli chat

# Switch back to local
e-cli config set --provider ollama --model llama3
```

## Skills System

### Creating a Custom Skill

1. **Create skill directory:**
```bash
mkdir -p ~/.e-cli/skills/git-helper
cd ~/.e-cli/skills/git-helper
```

2. **Create `skill.yaml`:**
```yaml
name: git-helper
version: 1.0.0
description: Git repository helper utilities
author: your-name
category: development
tags:
  - git
  - vcs
  - development
parameters:
  - name: operation
    type: string
    required: true
    choices: [status, log, diff]
  - name: branch
    type: string
    required: false
```

3. **Create `skill.py`:**
```python
"""Git helper skill implementation."""

from dataclasses import dataclass
from typing import Any

from e_cli.skills.base import BaseSkill, SkillMetadata, SkillResult

@dataclass
class GitHelperSkill(BaseSkill):
    """Git repository helper utilities."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="git-helper",
            version="1.0.0",
            description="Git repository helper utilities",
            author="your-name",
            category="development",
            tags=["git", "vcs", "development"],
        )

    def validate_input(self, **kwargs: Any) -> tuple[bool, str]:
        """Validate input parameters."""
        operation = kwargs.get("operation")

        if not operation:
            return False, "operation parameter is required"

        if operation not in ["status", "log", "diff"]:
            return False, f"Invalid operation: {operation}"

        return True, ""

    def execute(self, **kwargs: Any) -> SkillResult:
        """Execute git operation."""
        import subprocess

        operation = kwargs["operation"]
        branch = kwargs.get("branch")

        # Build git command
        if operation == "status":
            cmd = ["git", "status"]
        elif operation == "log":
            cmd = ["git", "log", "--oneline", "-10"]
            if branch:
                cmd.append(branch)
        elif operation == "diff":
            cmd = ["git", "diff"]
            if branch:
                cmd.append(branch)

        # Execute command
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            return SkillResult(
                success=True,
                output=result.stdout,
                metadata={"operation": operation},
            )
        except subprocess.CalledProcessError as e:
            return SkillResult(
                success=False,
                error=f"Git command failed: {e.stderr}",
            )

    def get_schema(self) -> dict[str, Any]:
        """Get JSON schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["status", "log", "diff"],
                    "description": "Git operation to perform",
                },
                "branch": {
                    "type": "string",
                    "description": "Optional branch name",
                },
            },
            "required": ["operation"],
        }

# Export the skill
skill = GitHelperSkill()
```

4. **Install and use:**
```bash
# Install the skill
e-cli skills install ~/.e-cli/skills/git-helper

# List skills to verify
e-cli skills list

# Get skill info
e-cli skills info git-helper

# Use in conversation
e-cli
> Can you check the git status using the git-helper skill?
```

### Managing Skills

```bash
# List all skills
e-cli skills list

# List by category
e-cli skills list --category development

# Search skills
e-cli skills search git

# Show skill details
e-cli skills info git-helper

# Enable/disable skills
e-cli skills enable git-helper
e-cli skills disable git-helper

# Reload after modifying skill code
e-cli skills reload git-helper

# View statistics
e-cli skills stats
```

## Knowledge Wiki

### Basic Wiki Usage

```bash
# Initialize wiki (creates directory structure)
e-cli wiki init

# Create a page
e-cli wiki create "Getting Started with Docker"

# This opens your $EDITOR. Write:
---
title: Getting Started with Docker
tags: [docker, containers, tutorial]
category: tutorials
---

# Getting Started with Docker

Docker is a containerization platform that makes it easy to package and deploy applications.

## Key Concepts

- [[Docker Images]]
- [[Docker Containers]]
- [[Docker Compose]]

## Installation

See [[Docker Installation Guide]] for platform-specific instructions.

## Basic Commands

```bash
docker run hello-world
docker ps
docker images
```

Related: [[Kubernetes]], [[Container Networking]]
```

### Wiki Workflows

**Daily Knowledge Capture:**
```bash
# Start of day - create goals page
e-cli wiki create "$(date +%Y-%m-%d) Goals" --category daily

# During work - document learnings
e-cli wiki create "TIL: Docker Volume Mounts" --category til

# Link to related pages
# In editor, use: See also [[Docker Basics]], [[Linux Filesystems]]
```

**Building a Documentation System:**
```bash
# Create main index
e-cli wiki create "Documentation Index" --category index

# Create category pages
e-cli wiki create "Python Development" --category guides
e-cli wiki create "Docker & Containers" --category guides
e-cli wiki create "Git Workflows" --category guides

# Create detailed pages with wikilinks
e-cli wiki create "Python Virtual Environments"
# Content: See [[Python Development]] for overview
```

### Wiki Search and Navigation

```bash
# Search for content
e-cli wiki search "docker compose"

# List all pages
e-cli wiki list

# List by category
e-cli wiki list --category tutorials

# List by tag
e-cli wiki list --tag docker

# Show page details
e-cli wiki show "Getting Started with Docker"

# Find what links to a page
e-cli wiki backlinks "Docker Images"

# Rebuild search index after bulk changes
e-cli wiki index

# View statistics
e-cli wiki stats
```

### Advanced Wiki Patterns

**Zettelkasten Method:**
```bash
# Create atomic notes with unique IDs
e-cli wiki create "202501-Docker-Volumes"

# Content uses wikilinks to connect ideas:
# Links to: [[202501-Docker-Images]], [[202501-Linux-Filesystems]]
# Backlinks from: [[202501-Container-Data-Management]]
```

**Project Documentation:**
```bash
# Project structure
e-cli wiki create "MyApp/Architecture" --category projects
e-cli wiki create "MyApp/API-Reference" --category projects
e-cli wiki create "MyApp/Deployment" --category projects

# Link them together with wikilinks
# [[MyApp/Architecture]] -> [[MyApp/API-Reference]] -> [[MyApp/Deployment]]
```

## Workflows

### Using Built-in Workflows

```bash
# List available workflows
e-cli workflow list

# View workflow details
e-cli workflow show setup-python-project

# Run with parameters
e-cli workflow run setup-python-project \
  --param project_name=myapp \
  --param include_tests=true

# Dry run to preview
e-cli workflow run setup-python-project \
  --param project_name=myapp \
  --dry-run
```

### Creating Custom Workflows

**Example: Project Setup Workflow**

Create `~/.e-cli/workflows/setup-node-project.yaml`:

```yaml
name: setup-node-project
version: 1.0.0
description: Initialize a new Node.js project with TypeScript
author: me
tags: [nodejs, typescript, setup]

parameters:
  - name: project_name
    type: string
    required: true
    description: Name of the project
  - name: use_typescript
    type: boolean
    default: true
    description: Use TypeScript
  - name: add_eslint
    type: boolean
    default: true
    description: Add ESLint configuration

steps:
  - name: Create project directory
    tool: shell
    parameters:
      command: mkdir -p ${project_name}

  - name: Initialize npm
    tool: shell
    parameters:
      command: cd ${project_name} && npm init -y

  - name: Install TypeScript
    tool: shell
    parameters:
      command: cd ${project_name} && npm install --save-dev typescript @types/node
    condition: ${use_typescript}

  - name: Create tsconfig.json
    tool: file.write
    parameters:
      path: ${project_name}/tsconfig.json
      content: |
        {
          "compilerOptions": {
            "target": "ES2020",
            "module": "commonjs",
            "outDir": "./dist",
            "rootDir": "./src",
            "strict": true,
            "esModuleInterop": true
          }
        }
    condition: ${use_typescript}

  - name: Install ESLint
    tool: shell
    parameters:
      command: cd ${project_name} && npm install --save-dev eslint
    condition: ${add_eslint}

  - name: Create source directory
    tool: shell
    parameters:
      command: mkdir -p ${project_name}/src

  - name: Create .gitignore
    tool: file.write
    parameters:
      path: ${project_name}/.gitignore
      content: |
        node_modules/
        dist/
        .env
        *.log

  - name: Initialize git
    tool: shell
    parameters:
      command: cd ${project_name} && git init
```

**Run the workflow:**
```bash
e-cli workflow run setup-node-project \
  --param project_name=my-api \
  --param use_typescript=true \
  --param add_eslint=true
```

### Workflow Best Practices

1. **Use descriptive names:** `setup-python-project` not `setup1`
2. **Add tags:** Makes workflows discoverable
3. **Validate parameters:** Use `required` and `choices`
4. **Use conditions:** `condition: ${use_typescript}`
5. **Provide defaults:** `default: true`
6. **Test with dry-run:** `--dry-run` before real execution

## Interactive Menus

### Using Interactive Mode

```bash
# Doctor command shows interactive menu
e-cli doctor

# You'll see:
# ┌─────────────────────────────────────┐
# │  E-CLI Doctor - Diagnostics Menu   │
# └─────────────────────────────────────┘
#
# 1. Run basic diagnostics
# 2. Run autofix
# 3. Test model connections
# 4. Check API connectivity
# 5. Verify tool availability
# 6. Check memory system
# 7. Validate configuration
#
# b. Back
# x. Exit
#
# Select option [1-7, b, x]:
```

### Configuring Menus

```bash
# Enable/disable interactive menus
e-cli config set --interactive-menus
e-cli config set --no-interactive-menus

# Change menu style
e-cli config set --menu-style rich      # Full formatting
e-cli config set --menu-style standard  # Simple boxes
e-cli config set --menu-style minimal   # Text only

# Set menu timeout (seconds)
e-cli config set --menu-timeout 300

# Toggle keyboard shortcuts
e-cli config set --show-shortcuts
e-cli config set --no-show-shortcuts
```

### Force Batch Mode

```bash
# Use traditional flags instead of menu
e-cli doctor --batch --fix --all
```

## Session Management

### Working with Sessions

```bash
# Start a new chat (creates new session)
e-cli chat

# Resume last session
e-cli chat --last

# List all sessions
e-cli sessions list

# Show session details
e-cli sessions show --last
e-cli sessions show --id abc123...

# View session statistics
e-cli sessions stats
```

### Session Compaction

```bash
# Preview compaction (doesn't modify)
e-cli sessions compact --last --dry-run

# Compact last session
e-cli sessions compact --last

# Compact specific session
e-cli sessions compact --session-id abc123...

# Keep more recent messages verbatim
e-cli sessions compact --last --keep-recent 20

# Target specific token budget
e-cli sessions compact --last --target-tokens 3000
```

### Session Audit Logs

```bash
# View audit log for last session
e-cli sessions audit --last

# Shows:
# - Tool executions
# - Approvals/denials
# - Safety policy decisions
# - Timestamps
```

### Deleting Sessions

```bash
# Delete specific session
e-cli sessions delete --id abc123...

# Delete with confirmation
e-cli sessions delete --last
```

## Advanced Scenarios

### Scenario 1: Research and Documentation

```bash
# 1. Start research session
e-cli chat
> Research Docker networking best practices

# 2. During chat, capture key learnings
# Exit chat, then:
e-cli wiki create "Docker Networking Best Practices"

# 3. Link to related concepts
# In editor: See [[Docker Basics]], [[Container Security]]

# 4. Continue research in new session
e-cli chat --last

# 5. Search previous learnings
e-cli wiki search "docker network"
```

### Scenario 2: Multi-Provider Workflow

```bash
# Use fast local model for quick tasks
e-cli config set --provider ollama --model llama3
e-cli
> Write unit tests for this function

# Switch to powerful cloud model for complex analysis
e-cli config set --provider anthropic --model claude-3-5-sonnet-20241022
e-cli
> Review this architecture and suggest improvements

# Back to local for iteration
e-cli config set --provider ollama --model llama3
```

### Scenario 3: Project Automation

```bash
# 1. Create custom workflow for your stack
e-cli workflow create my-stack-setup

# 2. Edit the workflow YAML
# Add steps for: git init, package install, config files, etc.

# 3. Test with dry-run
e-cli workflow run my-stack-setup --param project_name=test --dry-run

# 4. Run for real
e-cli workflow run my-stack-setup --param project_name=real-project

# 5. Document in wiki
e-cli wiki create "My Stack Setup Process"
# Link to: [[Project Templates]], [[Development Workflow]]
```

### Scenario 4: Learning and Skill Building

```bash
# 1. Start learning session
e-cli chat
> Teach me about Kubernetes deployments

# 2. Create wiki pages as you learn
e-cli wiki create "Kubernetes Deployments" --category learning

# 3. Build skill for practice
mkdir -p ~/.e-cli/skills/k8s-helper
# Create skill.yaml and skill.py

# 4. Install and test
e-cli skills install ~/.e-cli/skills/k8s-helper
e-cli skills info k8s-helper

# 5. Use in practice
e-cli
> Use k8s-helper to check deployment status
```

### Scenario 5: Team Knowledge Base

```bash
# Set up shared wiki (in git repo)
cd ~/team-wiki
e-cli wiki init

# Create team pages
e-cli wiki create "Team/Onboarding" --category team
e-cli wiki create "Team/Architecture" --category team
e-cli wiki create "Team/Runbooks" --category team

# Link everything together with wikilinks
# [[Team/Onboarding]] -> [[Team/Architecture]] -> [[Service/API]]

# Share via git
git add .
git commit -m "Add team wiki"
git push

# Team members clone and contribute
# Wiki supports concurrent editing via git merges
```

## Tips and Tricks

### Performance Optimization

```bash
# Adjust inference parameters for speed
e-cli config set --temperature 0.3 --max-output-tokens 512

# Use faster models for simple tasks
e-cli config set --provider ollama --model llama3:8b

# Use streaming for immediate feedback
e-cli config set --streaming-enabled
```

### Safety and Approvals

```bash
# Review current safety settings
e-cli safe-mode status
e-cli approval status

# Temporarily disable for trusted operations
e-cli safe-mode set false
# ... do trusted operations ...
e-cli safe-mode set true

# Set approval mode
e-cli approval set --mode always    # Always ask
e-cli approval set --mode auto-approve  # Auto-approve safe operations
e-cli approval set --mode never     # Deny all
```

### Shell Integration

```bash
# Install completions for better UX
# See docs/SHELL_COMPLETION.md

# Use in scripts
e-cli tools run --tool shell --command "docker ps" > containers.txt

# Pipe commands
echo "Summarize this file" | e-cli ask "$(cat README.md)"
```

## Troubleshooting

```bash
# Run diagnostics
e-cli doctor

# Check configuration
e-cli config show

# Test model connection
e-cli models test

# View logs (if session fails)
e-cli sessions show --last

# Reset configuration
e-cli config reset
```

## Getting Help

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

## Next Steps

- Read [QUICKSTART.md](../QUICKSTART.md) for a quick introduction
- See [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) for technical details
- Check [SHELL_COMPLETION.md](SHELL_COMPLETION.md) for completion setup
- Join the community and share your skills and workflows!
