"""HTTP helpers for read-only endpoint inspection."""

from __future__ import annotations

from dataclasses import dataclass
import json

import requests


@dataclass(slots=True)
class HttpResult:
    """Structured HTTP tool result used by the tool router."""

    ok: bool
    output: str


class HttpTool:
    """Executes safe GET requests for agent diagnostics and API inspection."""

    @staticmethod
    def get(url: str, timeout_seconds: int) -> HttpResult:
        """Fetch an HTTP or HTTPS URL and return a compact textual summary."""

        try:
            if not url.startswith(("http://", "https://")):
                return HttpResult(ok=False, output="Only http:// and https:// URLs are supported.")

            response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            contentType = response.headers.get("content-type", "")
            bodyText: str
            if "application/json" in contentType.lower():
                bodyText = json.dumps(response.json(), indent=2)
            else:
                bodyText = response.text
            if len(bodyText) > 12000:
                bodyText = bodyText[:12000] + "\n[truncated]"
            output = (
                f"status={response.status_code}\n"
                f"content-type={contentType or '(unknown)'}\n\n"
                f"{bodyText.strip()}"
            )
            return HttpResult(ok=True, output=output.strip())
        except requests.RequestException as exc:
            return HttpResult(ok=False, output=f"HTTP GET error: {exc}")
        except Exception as exc:  # noqa: BLE001
            return HttpResult(ok=False, output=f"HTTP GET error: {exc}")