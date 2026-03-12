"""Tests for browser helper behavior."""

import requests

from e_cli.tools.browser_tool import BrowserTool


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self.calls = 0

    def get(self, url: str, timeout: int, allow_redirects: bool) -> _FakeResponse:
        _ = (url, timeout, allow_redirects)
        index = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        return self._responses[index]


def test_browser_open_extracts_title(monkeypatch) -> None:
    """Ensures browser tool extracts title and text from HTML."""

    BrowserTool._SESSION = _FakeSession([_FakeResponse("<html><title>Example</title><body>Hello</body></html>")])
    result = BrowserTool.open("https://example.com", timeout_seconds=3)
    assert result.ok is True
    assert "title=Example" in result.output
    assert "Hello" in result.output


def test_browser_open_rejects_non_http_url() -> None:
    """Ensures browser tool validates URL scheme."""

    result = BrowserTool.open("ftp://example.com", timeout_seconds=3)
    assert result.ok is False


def test_browser_open_retries_on_429_then_succeeds(monkeypatch) -> None:
    """Ensures browser tool retries transient rate limits before failing."""

    monkeypatch.setattr("e_cli.tools.browser_tool.time.sleep", lambda _seconds: None)
    BrowserTool._SESSION = _FakeSession(
        [
            _FakeResponse("<html><title>Busy</title></html>", status_code=429, headers={"Retry-After": "1"}),
            _FakeResponse("<html><title>Yahoo</title><body>News</body></html>", status_code=200),
        ]
    )

    result = BrowserTool.open("https://www.yahoo.com", timeout_seconds=3)
    assert result.ok is True
    assert "title=Yahoo" in result.output


def test_browser_open_reports_clean_429_message(monkeypatch) -> None:
    """Ensures browser tool returns actionable guidance when still rate limited."""

    monkeypatch.setattr("e_cli.tools.browser_tool.time.sleep", lambda _seconds: None)
    BrowserTool._SESSION = _FakeSession(
        [
            _FakeResponse("<html><title>Busy</title></html>", status_code=429),
            _FakeResponse("<html><title>Busy</title></html>", status_code=429),
            _FakeResponse("<html><title>Busy</title></html>", status_code=429),
        ]
    )

    result = BrowserTool.open("https://www.yahoo.com", timeout_seconds=3)
    assert result.ok is False
    assert "HTTP 429" in result.output
