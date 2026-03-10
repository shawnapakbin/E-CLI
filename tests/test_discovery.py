"""Tests for local and LAN endpoint discovery logic."""

import requests

from e_cli.models.discovery import ModelDiscovery


class FakeResponse:
    """Simple fake response object for request probe tests."""

    def __init__(self, ok: bool) -> None:
        """Stores success status for endpoint checks."""

        self.ok = ok


def test_discover_returns_reachable(monkeypatch) -> None:
    """Ensures discover returns endpoints that respond with OK."""

    def fakeGet(url: str, timeout: float):
        _ = timeout
        if url.endswith("/api/tags") or url.endswith("/v1/models"):
            return FakeResponse(ok=True)
        return FakeResponse(ok=False)

    monkeypatch.setattr("e_cli.models.discovery.requests.get", fakeGet)
    monkeypatch.setattr("e_cli.models.discovery.socket.gethostbyname", lambda _name: "192.168.1.55")
    monkeypatch.setattr("e_cli.models.discovery.socket.gethostname", lambda: "host")

    discovered = ModelDiscovery.discover()
    assert len(discovered) >= 3


def test_discover_handles_request_errors(monkeypatch) -> None:
    """Ensures failed probes are handled without raising exceptions."""

    def fakeGet(url: str, timeout: float):
        _ = (url, timeout)
        raise requests.RequestException("network down")

    monkeypatch.setattr("e_cli.models.discovery.requests.get", fakeGet)
    discovered = ModelDiscovery.discover()
    assert discovered == []
