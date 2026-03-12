"""HTTP request helper that mirrors essential curl-like behavior."""

from __future__ import annotations

from dataclasses import dataclass
import json

import requests


@dataclass(slots=True)
class CurlResult:
    """Structured curl execution result used by the tool router."""

    ok: bool
    output: str


class CurlTool:
    """Executes bounded HTTP requests with method/header/body controls."""

    @staticmethod
    def request(
        url: str,
        timeout_seconds: int,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        content: str | None = None,
    ) -> CurlResult:
        """Execute one HTTP request and return a compact response summary."""

        try:
            if not url.startswith(("http://", "https://")):
                return CurlResult(ok=False, output="Only http:// and https:// URLs are supported.")

            normalized_method = method.strip().upper() or "GET"
            allowed_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
            if normalized_method not in allowed_methods:
                return CurlResult(ok=False, output=f"Unsupported HTTP method: {normalized_method}")

            response = requests.request(
                method=normalized_method,
                url=url,
                headers=headers or {},
                data=content if content else None,
                timeout=timeout_seconds,
            )
            content_type = response.headers.get("content-type", "")
            body_text: str
            if "application/json" in content_type.lower():
                body_text = json.dumps(response.json(), indent=2)
            else:
                body_text = response.text
            if len(body_text) > 12000:
                body_text = body_text[:12000] + "\n[truncated]"

            output = (
                f"method={normalized_method}\n"
                f"url={url}\n"
                f"status={response.status_code}\n"
                f"content-type={content_type or '(unknown)'}\n\n"
                f"{body_text.strip()}"
            )
            return CurlResult(ok=response.ok, output=output.strip())
        except requests.RequestException as exc:
            return CurlResult(ok=False, output=f"curl request error: {exc}")
        except Exception as exc:  # noqa: BLE001
            return CurlResult(ok=False, output=f"curl request error: {exc}")
