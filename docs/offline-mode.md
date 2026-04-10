# Offline Mode

E-CLI is designed for full offline operation. All core workflows — chat, tools, skills, memory, and documentation indexing — work without internet access once dependencies are installed.

## Local-First Principles

- No external network calls unless explicitly configured
- All model providers can run locally: Ollama, LM Studio, vLLM, bundled helper
- Skills and tools are loaded from local disk
- Memory and RAG store are SQLite-backed, stored in `~/.e-cli/`
- Documentation index is stored locally at `~/.e-cli/doc_index/manifest.json`

## Air-Gapped Deployment

1. Pre-install all Python dependencies on a connected machine:
   ```bash
   pip download -r requirements.txt -d ./wheels
   ```
2. Transfer the wheel directory to the air-gapped machine
3. Install offline:
   ```bash
   pip install --no-index --find-links ./wheels e-cli
   ```
4. Download Playwright Chromium on a connected machine and transfer:
   ```bash
   playwright install chromium
   # Copy ~/.cache/ms-playwright/ to the air-gapped machine
   ```
5. Download bundled model assets on a connected machine:
   ```bash
   e-cli helper download-assets
   # Copy ~/.e-cli/bundled-assets/ to the air-gapped machine
   ```

## Recommended Offline Provider

Use the bundled helper runtime for fully offline inference:

```bash
e-cli helper start
e-cli config set --provider bundled --model qwen2.5-coder-3b
```

See [bundled-runtime.md](bundled-runtime.md) for setup details.

## No Telemetry

E-CLI has no telemetry, analytics, or background network activity. The only outbound connections are:
- Model inference calls to the configured provider endpoint
- Tool calls that explicitly fetch URLs (`http.get`, `browser`, `curl`, `browser.playwright`)
- MCP server subprocesses (which may make their own network calls)
- Documentation indexer fetches (`e-cli docs index --url`)

All of these are user-initiated and logged in the session audit log.
