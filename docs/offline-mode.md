# Offline Mode

E-CLI is designed for full offline operation. All core workflows (chat, tools, skills, memory) work without internet access.

## Local-First Principles
- No external network calls unless explicitly configured
- All model providers can run locally (Ollama, LM Studio, vLLM, bundled helper)
- Skills and tools are loaded from local disk

## Air-Gapped Deployment
- No telemetry or background network activity
- All dependencies can be pre-fetched and installed offline
- See `docs/bundled-runtime.md` for helper model details
