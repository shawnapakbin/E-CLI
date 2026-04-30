# Git Helper Skill

A comprehensive git repository helper skill for E-CLI that provides quick access to common git operations.

## Features

- Quick git status check
- View commit logs with customizable limits
- Show diffs for branches or HEAD
- List branches with tracking information
- Display remote repositories

## Installation

```bash
# Copy to your skills directory
cp -r examples/skills/git-helper ~/.e-cli/skills/

# Or install directly
e-cli skills install examples/skills/git-helper

# Verify installation
e-cli skills info git-helper
```

## Usage

### Via CLI

```bash
# Get git status
e-cli
> Use git-helper to show repository status

# View last 5 commits
e-cli
> Use git-helper to show last 5 log entries

# Show diff for specific branch
e-cli
> Use git-helper to show diff for main branch
```

### In Workflows

```yaml
steps:
  - name: Check git status
    tool: skill:git-helper
    parameters:
      operation: status

  - name: View recent commits
    tool: skill:git-helper
    parameters:
      operation: log
      limit: 20

  - name: Compare with main
    tool: skill:git-helper
    parameters:
      operation: diff
      branch: main
```

## Parameters

- **operation** (required): Git operation to perform
  - `status`: Show repository status
  - `log`: View commit history
  - `diff`: Show differences
  - `branch`: List branches
  - `remote`: Show remote repositories

- **branch** (optional): Branch name for log/diff operations

- **limit** (optional): Number of log entries (default: 10)

## Examples

```python
# Using the skill programmatically
from e_cli.skills.manager import SkillManager

manager = SkillManager()
manager.initialize()

# Get git status
result = manager.execute_skill("git-helper", operation="status")
print(result.output)

# View last 15 commits
result = manager.execute_skill("git-helper", operation="log", limit=15)
print(result.output)

# Diff against develop branch
result = manager.execute_skill("git-helper", operation="diff", branch="develop")
print(result.output)
```

## Requirements

- Git must be installed and in PATH
- Must be run from within a git repository

## License

Part of E-CLI project
