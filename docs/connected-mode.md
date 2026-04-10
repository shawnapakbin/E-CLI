# Connected Mode

E-CLI supports optional connected mode for cloud-based model providers and remote tool execution.

## Anthropic Claude

The primary cloud provider is Anthropic Claude. Set your API key and select a model:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
e-cli config set --provider anthropic --model claude-sonnet-4-5
```

Available models (no network call required for listing):
- `claude-opus-4-5` — most capable
- `claude-sonnet-4-5` — balanced performance and cost
- `claude-haiku-3-5` — fastest and most economical

Rate-limit errors (HTTP 429 and 529) are automatically retried with exponential back-off: delays of 1, 2, and 4 seconds, up to 4 attempts total.

The API key is resolved in this order:
1. `ANTHROPIC_API_KEY` environment variable
2. `anthropicApiKey` field in `~/.e-cli/config.json`

If neither is set, `AnthropicClient` raises a `ConfigurationError` before making any network call.

## Provider Fallback Chain

When the primary provider endpoint is unreachable at session start, E-CLI automatically tries the next provider in `fallbackChain`:

```bash
e-cli config set --provider anthropic --model claude-sonnet-4-5
# fallbackChain defaults to ["ollama", "lmstudio", "bundled"]
```

Each failed attempt is logged as a warning before trying the next provider.

## Other OpenAI-Compatible Providers

Any OpenAI-compatible endpoint works via `lmstudio` or `vllm`:

```bash
e-cli config set --provider lmstudio --endpoint https://my-remote-server:1234 --model my-model
e-cli config set --provider vllm --endpoint https://my-vllm-server:8000 --model meta-llama/Llama-3-8b
```

## MCP Servers

Connect external MCP stdio servers for additional tools:

```json
{
  "mcpServers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
      "env": {}
    }
  ]
}
```

MCP servers are launched as subprocesses at session start. Their tools are registered in the agent's tool registry and callable by the model using the standard JSON tool-call format.

## Safety

- Connected mode is always opt-in — no cloud calls are made unless explicitly configured
- All safety policies and audit logging remain in effect for cloud providers
- MCP tools without a declared `safetyClass` default to `"mutating"` and require approval
- The `ANTHROPIC_API_KEY` is never logged or stored in the session audit log
