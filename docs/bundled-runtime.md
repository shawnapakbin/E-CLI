# Bundled Helper Runtime

E-CLI includes an optional bundled helper model for setup, debug, and environment tasks. It is never auto-activated and must be started explicitly by the user.

## Overview

- Vulkan-capable inference runtime (cross-GPU, no CUDA required)
- Model weights are downloaded on first use — not bundled in the wheel
- Managed by `BundledRuntime` and `BundledAssetManager` classes

## CLI Commands

```bash
e-cli helper status             # show runtime status (running/stopped)
e-cli helper start              # start the bundled runtime
e-cli helper stop               # stop the bundled runtime
e-cli helper download-assets    # download and verify all model assets
e-cli helper verify-assets      # verify checksums for all downloaded assets
```

## Asset Management

Model weights are stored in `~/.e-cli/bundled-assets/`. The `BundledAssetManager` downloads assets from the configured URLs and verifies SHA-256 checksums.

```bash
e-cli helper download-assets    # downloads missing or invalid assets
e-cli helper verify-assets      # checks checksums without downloading
```

If a download fails, the asset is skipped and `ensure_assets()` returns `False`. The runtime will not start if assets are missing or invalid.

## Using the Bundled Model

Once assets are downloaded and the runtime is running, select it as your provider:

```bash
e-cli config set --provider bundled --model qwen2.5-coder-3b
```

Available bundled models:
- `qwen2.5-coder-3b` — lightweight coding assistant
- `qwen2.5-coder-7b` — more capable coding assistant

## Safety

- Only read-privileged tools are enabled by default when using the bundled provider
- Mutating tools require explicit approval (same as all other providers)
- The bundled runtime runs entirely locally — no network calls are made for inference

## Offline Use

The bundled runtime is the recommended provider for fully air-gapped deployments. See [offline-mode.md](offline-mode.md) for details.
