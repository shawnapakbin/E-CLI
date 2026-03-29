# Connected Mode

E-CLI supports optional connected mode for cloud-based model providers and remote tool execution.

## Enabling Connected Mode
- Configure a provider endpoint (OpenAI-compatible, vLLM, etc.)
- Use `e-cli config set --provider openai --endpoint https://api.openai.com` (example)

## Safety
- Connected mode is always opt-in
- No cloud calls are made unless explicitly configured
- All safety policies and audit logging remain in effect
