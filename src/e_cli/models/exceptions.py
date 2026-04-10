"""Shared exception types for model provider errors."""

from __future__ import annotations


class ConfigurationError(Exception):
    """Raised when a required configuration value is missing or invalid."""


class ProviderRateLimitError(Exception):
    """Raised when a provider returns HTTP 429 (rate limit) or 529 (overloaded)."""


class ProviderConnectionError(Exception):
    """Raised when a provider endpoint is unreachable or refuses the connection."""
