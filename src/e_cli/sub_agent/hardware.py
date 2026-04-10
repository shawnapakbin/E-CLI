"""Hardware probe for deriving the sub-agent concurrency limit.

Reads CPU core count and available RAM via psutil and applies the formula:
    max(1, min(cpu // 2, ram_gb // 2))

Falls back to concurrency_limit=1 with a WARNING log if psutil is unavailable.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def probe_concurrency_limit(
    env_override: int | None = None,
    config_override: int = 0,
) -> int:
    """Derive the concurrency limit for the Sub_Agent_Pool.

    Priority order: env_override > config_override > hardware_limit.

    Args:
        env_override: Value already parsed from ECLI_MAX_SUB_AGENTS (caller's
            responsibility to read the env var). Capped at 16.
        config_override: Value from AppConfig.subAgentMaxConcurrency. Used when
            positive and env_override is not set.

    Returns:
        The effective concurrency limit (always >= 1).
    """
    try:
        import psutil

        cpu = psutil.cpu_count(logical=True) or 1
        ram_gb = psutil.virtual_memory().available // (1024**3)
        hardware_limit = max(1, min(cpu // 2, ram_gb // 2))

        logger.info(
            "Hardware probe: cpu_cores=%d, available_ram_gb=%d, hardware_limit=%d",
            cpu,
            ram_gb,
            hardware_limit,
        )
    except ImportError:
        logger.warning(
            "psutil is not available; falling back to concurrency_limit=1"
        )
        hardware_limit = 1
        cpu = 1
        ram_gb = 0

    if env_override is not None and env_override > 0:
        limit = min(env_override, 16)
        logger.info(
            "Concurrency limit set by env override: %d (raw=%d, cap=16)",
            limit,
            env_override,
        )
        return limit

    if config_override > 0:
        logger.info(
            "Concurrency limit set by config override: %d",
            config_override,
        )
        return config_override

    logger.info("Concurrency limit (hardware-derived): %d", hardware_limit)
    return hardware_limit
