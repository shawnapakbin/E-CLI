"""Provider and model discovery helpers for local and LAN endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import os
import socket

import requests

from e_cli.config import ProviderType


@dataclass(slots=True)
class DiscoveredEndpoint:
    """Represents one reachable endpoint candidate and its provider type."""

    provider: ProviderType
    endpoint: str


DEFAULT_ENDPOINTS = [
    DiscoveredEndpoint(provider="ollama", endpoint="http://127.0.0.1:11434"),
    DiscoveredEndpoint(provider="lmstudio", endpoint="http://127.0.0.1:1234"),
    DiscoveredEndpoint(provider="vllm", endpoint="http://127.0.0.1:8000"),
]

# Sentinel endpoint value used for static (no-network) providers like Anthropic.
_STATIC_ENDPOINT = "static"


class ModelDiscovery:
    """Discovers reachable model endpoints and available models with lightweight probes."""

    @staticmethod
    def _buildLanHosts() -> list[str]:
        """Build LAN host candidates from environment overrides and local subnet hints."""

        try:
            envHosts = os.getenv("ECLI_LAN_HOSTS", "")
            parsedHosts = [host.strip() for host in envHosts.split(",") if host.strip()]

            localIp = socket.gethostbyname(socket.gethostname())
            subnetPrefix = ".".join(localIp.split(".")[:3])
            defaultHosts = [
                f"{subnetPrefix}.1",
                f"{subnetPrefix}.10",
                f"{subnetPrefix}.20",
                f"{subnetPrefix}.100",
            ]
            hostSet = {"localhost", "127.0.0.1", *defaultHosts, *parsedHosts}
            return sorted(hostSet)
        except Exception:
            return ["localhost", "127.0.0.1"]

    @staticmethod
    def _buildCandidates(extraEndpoints: list[DiscoveredEndpoint] | None = None) -> list[DiscoveredEndpoint]:
        """Build candidate endpoint list including local and LAN hosts."""

        try:
            hosts = ModelDiscovery._buildLanHosts()
            candidates: list[DiscoveredEndpoint] = []
            for host in hosts:
                candidates.extend(
                    [
                        DiscoveredEndpoint(provider="ollama", endpoint=f"http://{host}:11434"),
                        DiscoveredEndpoint(provider="lmstudio", endpoint=f"http://{host}:1234"),
                        DiscoveredEndpoint(provider="vllm", endpoint=f"http://{host}:8000"),
                    ]
                )

            if extraEndpoints:
                candidates.extend(extraEndpoints)

            uniqueByUrl: dict[str, DiscoveredEndpoint] = {
                endpoint.endpoint: endpoint for endpoint in candidates
            }
            return list(uniqueByUrl.values())
        except Exception:
            fallback = list(DEFAULT_ENDPOINTS)
            if extraEndpoints:
                fallback.extend(extraEndpoints)
            return fallback

    @staticmethod
    def discover(extra_endpoints: list[DiscoveredEndpoint] | None = None) -> list[DiscoveredEndpoint]:
        """Return endpoints that respond successfully to provider health/model checks."""

        candidates = ModelDiscovery._buildCandidates(extraEndpoints=extra_endpoints)

        reachable: list[DiscoveredEndpoint] = []
        for candidate in candidates:
            try:
                if candidate.provider == "ollama":
                    response = requests.get(f"{candidate.endpoint}/api/tags", timeout=1.5)
                else:
                    response = requests.get(f"{candidate.endpoint}/v1/models", timeout=1.5)
                if response.ok:
                    reachable.append(candidate)
            except requests.RequestException:
                continue

        # Include Anthropic static endpoint when API key is available (no network call).
        if os.getenv("ANTHROPIC_API_KEY"):
            reachable.append(DiscoveredEndpoint(provider="anthropic", endpoint=_STATIC_ENDPOINT))

        return reachable
