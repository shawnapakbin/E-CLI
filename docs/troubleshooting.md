# Troubleshooting E-CLI

## Common Issues

### E-CLI not found after install
- Open a new terminal after install
- Ensure the Python user scripts directory is in your `PATH`
- Run `e-cli doctor` to check the environment

### Model not responding
- Check that the model server is running and reachable
- Run `e-cli models list` and `e-cli models test`
- For Anthropic: verify `ANTHROPIC_API_KEY` is set and valid

### Anthropic rate limit errors
- E-CLI automatically retries with exponential back-off (up to 4 attempts)
- If errors persist, check your Anthropic account quota
- Consider switching to a smaller model: `e-cli config set --model claude-haiku-3-5`

### TUI not rendering correctly
- Use `--no-tui` to fall back to plain Rich output: `e-cli chat --no-tui`
- Ensure your terminal supports 256-colour mode
- Textual requires a terminal width of at least 80 columns

### Playwright browser tool not working
- Run `playwright install chromium` once after install
- Verify Playwright is installed: `python -m playwright --version`
- Check that the `playwright` package is installed: `pip show playwright`

### MCP server not connecting
- Check the `command` and `args` in your `mcpServers` config
- The server must start within 5 seconds; slow servers are skipped
- Run `e-cli doctor` to see if the session initialised correctly
- Check that the MCP server binary is on your `PATH`

### Tool or skill not working
- Run `e-cli tools list` to inspect available tools and their safety policy
- Run `e-cli tools skills-list` to inspect loaded skills
- Check `~/.e-cli/skills/<name>/manifest.json` for validation errors (missing required fields cause the skill to be skipped with a warning in the logs)

### System tool package manager not found
- `install_package` requires `apt-get` (Debian/Ubuntu), `dnf` (Fedora/RHEL), `brew` (macOS), or `winget` (Windows)
- If none is detected, the tool returns an error listing the expected package managers

### Permission or approval errors
- Check safe mode and approval mode: `e-cli safe-mode status` and `e-cli approval status`
- For elevated operations (install, kill, drivers), safe mode must be disabled or approval mode set to `auto-approve`
- Skills with `safetyClass: "elevated"` are always blocked when `safeMode=True`

### Memory or session issues
- Run `e-cli doctor` to check the memory database
- Run `e-cli sessions compact --last` to reduce memory usage
- If the database is corrupted, delete `~/.e-cli/memory.db` and restart

### Documentation indexer not finding chunks
- Run `e-cli docs index --url <url>` to index a specific page
- Run `e-cli docs refresh` to re-index stale entries (older than 24 hours)
- Check that the URL returns HTTP 200; 4xx/5xx responses are skipped with a warning

### Coverage / test failures
- Run `python -m pytest tests/ --cov=src/e_cli -q` to check coverage
- Coverage target is ≥80% line coverage across all modules
- Async tests require `pytest-asyncio` (already in dev dependencies)

## Diagnostic Commands

```bash
e-cli doctor                    # full environment check
e-cli config show               # inspect active configuration
e-cli models list               # discover available model endpoints
e-cli models test               # send a smoke-test prompt to the selected model
e-cli safe-mode status          # check safe mode setting
e-cli approval status           # check approval mode setting
e-cli tools list                # list tools and their safety policy
e-cli tools skills-list         # list loaded skills
e-cli sessions list             # list recent sessions
e-cli sessions audit --last     # view audit log for last session
```
