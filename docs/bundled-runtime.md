# Bundled Helper Runtime

E-CLI includes an optional bundled helper model for setup, debug, and environment tasks. It is never auto-activated and must be started by the user.

## Features
- Vulkan-capable inference runtime (cross-GPU)
- Model weights are downloaded on first use, not bundled in the wheel
- Managed by `BundledRuntime` class: start, health-check, idle-shutdown, upgrade

## CLI Commands
- `e-cli helper install [--profile slim|standard]`
- `e-cli helper uninstall`
- `e-cli helper status`
- `e-cli helper start / stop`
- `e-cli helper hardware-check`
- `e-cli helper use`

## Safety
- Only read-privileged tools are enabled by default
- Mutating tools require explicit approval
