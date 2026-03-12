"""Tests for curl-like HTTP helper behavior."""

from e_cli.tools.curl_tool import CurlTool


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "ok", headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"content-type": "text/plain"}

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


def test_curl_request_supports_post(monkeypatch) -> None:
    """Ensures curl helper forwards method, headers, and body."""

    monkeypatch.setattr(
        "e_cli.tools.curl_tool.requests.request",
        lambda method, url, headers, data, timeout: _FakeResponse(status_code=201, text="created"),
    )
    result = CurlTool.request(
        url="https://example.com/api",
        timeout_seconds=3,
        method="POST",
        headers={"Authorization": "Bearer token"},
        content="{}",
    )
    assert result.ok is True
    assert "method=POST" in result.output
    assert "status=201" in result.output


def test_curl_request_rejects_invalid_method() -> None:
    """Ensures curl helper validates HTTP methods."""

    result = CurlTool.request(url="https://example.com", timeout_seconds=3, method="TRACE")
    assert result.ok is False
