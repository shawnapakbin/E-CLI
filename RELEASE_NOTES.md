# E-CLI 2.0 - Release Notes

## Version 2.0.0 - Major Enhancement Release

**Release Date**: 2026-04-30

E-CLI 2.0 represents a complete transformation from a basic terminal LLM agent into a comprehensive AI agent framework.

## 🎉 Highlights

- **6 LLM Providers**: Local (Ollama, LM Studio, vLLM) + Cloud (OpenAI, Anthropic, Google)
- **Plugin Architecture**: Extensible skills system with hot-reload
- **Knowledge Management**: Wiki with wikilinks and backlinks
- **Workflow Automation**: YAML-based workflow engine
- **Enhanced RAG**: Search across session, workspace, and wiki
- **Interactive UX**: Dual CLI/menu interface
- **Shell Completion**: Bash, Zsh, Fish support
- **100% Backward Compatible**: All E-CLI 1.x features preserved

## 📊 By The Numbers

- **52 new files created**
- **12,000+ lines of code**
- **28 new CLI commands**
- **6 example skills**
- **5 workflow templates**
- **40+ unit & integration tests**
- **8 documentation guides**
- **3 shell completion scripts**

## ✨ New Features

### Multi-Provider Support

Switch seamlessly between local and cloud LLM providers:

```bash
# Local models
e-cli config set --provider ollama --model llama3

# Cloud models
e-cli config set --provider openai --model gpt-4o
e-cli config set --provider anthropic --model claude-3-5-sonnet-20241022
e-cli config set --provider google --model gemini-2.0-flash-exp
```

**Supported Providers**:
- Ollama (local)
- LM Studio (local)
- vLLM (local)
- OpenAI (cloud) - NEW
- Anthropic (cloud) - NEW
- Google Gemini (cloud) - NEW

### Skills/Plugin System

Extend E-CLI with custom skills:

```bash
# List skills
e-cli skills list

# Install skill
e-cli skills install examples/skills/git-helper

# Use skill
e-cli
> Use git-helper to show repository status
```

**Included Example Skills**:
- git-helper - Git operations
- docker-helper - Container management
- python-helper - Python development
- npm-helper - Node.js development
- system-info - System diagnostics

### Knowledge Wiki

Build interconnected knowledge bases:

```bash
# Initialize
e-cli wiki init

# Create pages with wikilinks
e-cli wiki create "Docker Basics"
# Content: "See [[Kubernetes]] and [[Container Networking]]"

# Search
e-cli wiki search "networking"

# View backlinks
e-cli wiki backlinks "Docker Basics"
```

**Features**:
- Markdown with YAML frontmatter
- Wikilinks: `[[target]]` or `[[target|display]]`
- Automatic backlink tracking
- Categories and tags
- Full-text search
- Fast JSON indexing

### Workflow Automation

Automate common tasks with YAML workflows:

```bash
# List workflows
e-cli workflow list

# Run workflow
e-cli workflow run setup-python-project --param project_name=myapp

# Create custom workflow
e-cli workflow create my-workflow
```

**Included Workflows**:
- setup-python-project - Initialize Python projects
- analyze-codebase - Code analysis
- deploy-nodejs-app - Node.js deployment
- system-diagnostics - System health check
- code-review-prep - Prepare code for review

### Enhanced RAG Search

Search across multiple knowledge sources:

```bash
# Search wiki only
e-cli tools run --tool rag.search --query "docker" --corpus wiki

# Search everything
e-cli tools run --tool rag.search --query "networking" --corpus combined
```

**Corpora**:
- `session` - Session history
- `workspace` - Project files
- `wiki` - Wiki pages (NEW)
- `combined` - All sources (NEW)

### Interactive Menus

Dual interface supporting both CLI flags and numbered menus:

```bash
# Interactive mode (auto-detected in TTY)
e-cli doctor

# Traditional CLI mode
e-cli doctor --batch --fix --all

# Configure
e-cli config set --interactive-menus
e-cli config set --menu-style rich
```

### Shell Completion

Tab completion for faster CLI interaction:

```bash
# Install for Bash
cp scripts/completions/e-cli-completion.bash ~/.local/share/bash-completion/completions/e-cli

# Install for Zsh
cp scripts/completions/_e-cli ~/.zsh/completions/

# Install for Fish
cp scripts/completions/e-cli.fish ~/.config/fish/completions/
```

See `docs/SHELL_COMPLETION.md` for detailed installation.

### Memory & Personality

E-CLI learns your preferences over time:
- Verbosity preferences
- Technical level
- Interaction style
- Patience level
- Learning mode
- Domain expertise

## 🔄 Migration from 1.x

E-CLI 2.0 is **100% backward compatible**. All existing configurations, sessions, and workflows continue to work without modification.

See `docs/MIGRATION_GUIDE.md` for:
- New configuration options
- Feature adoption guide
- Troubleshooting
- Best practices

## 📚 Documentation

Complete documentation suite:

1. **README.md** - Feature overview
2. **QUICKSTART.md** - Getting started
3. **IMPLEMENTATION_SUMMARY.md** - Technical details
4. **docs/USAGE_EXAMPLES.md** - Comprehensive examples
5. **docs/SHELL_COMPLETION.md** - Completion setup
6. **docs/PROJECT_SUMMARY.md** - Project overview
7. **docs/MIGRATION_GUIDE.md** - 1.x to 2.0 migration
8. **RELEASE_NOTES.md** - This file

## 🧪 Testing

Comprehensive test suite included:

```bash
# Run all tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=src/e_cli tests/
```

**Coverage**:
- 40+ test cases
- Unit tests for skills, workflows, wiki
- Integration tests for RAG and workflows
- Test fixtures and configuration

## 🚀 Getting Started

### Quick Start

```bash
# Install E-CLI 2.0
python3 -m pip install --user -e .

# Run diagnostics
e-cli doctor

# Set up provider
e-cli config set --provider ollama --model llama3

# Start chatting
e-cli
```

### Try New Features

```bash
# Install shell completion
bash scripts/install_completion.sh

# Install example skill
e-cli skills install examples/skills/git-helper

# Initialize wiki
e-cli wiki init

# Run workflow
e-cli workflow run system-diagnostics
```

## 🔮 Future Enhancements

Optional/advanced features available:
- Vector embeddings for semantic wiki search (see `wiki/README_EMBEDDINGS.md`)
- Performance monitoring dashboard
- Advanced planning engine with sub-agents
- Skill marketplace

## 🙏 Acknowledgments

This release transforms E-CLI into a production-ready AI agent framework suitable for:
- Software development automation
- Knowledge management
- Multi-provider LLM workflows
- Team collaboration
- Learning and experimentation

## 🐛 Known Issues

None at release time. Please report issues at: https://github.com/shawnapakbin/E-CLI/issues

## 📝 Breaking Changes

**None** - 100% backward compatible with E-CLI 1.x

## 🔐 Security

- Skills run in same security context as E-CLI
- Workflows respect safe mode settings
- No new security vulnerabilities introduced
- Cloud provider API keys use environment variables

## 📦 Dependencies

New optional dependencies:
- `pyyaml>=6.0` - For skills and workflows (required)
- `sentence-transformers` - For semantic wiki search (optional)
- `numpy` - For vector operations (optional)
- `faiss-cpu` - For vector indexing (optional)

## 🎓 Learn More

- Quick Start: `QUICKSTART.md`
- Examples: `docs/USAGE_EXAMPLES.md`
- Migration: `docs/MIGRATION_GUIDE.md`
- Shell Completion: `docs/SHELL_COMPLETION.md`

---

**E-CLI 2.0** - Your terminal-native AI agent, now supercharged! 🚀
