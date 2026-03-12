"""Browser-like web inspection tool with bounded text extraction."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
import time

import requests


@dataclass(slots=True)
class BrowserResult:
    """Structured browser tool result used by the tool router."""

    ok: bool
    output: str


class BrowserTool:
    """Fetches pages and returns concise browser-style inspection details."""

    _SESSION: requests.Session | None = None
    _DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }

    @classmethod
    def _session(cls) -> requests.Session:
        """Return a persistent session to preserve cookies like a real browser."""

        if cls._SESSION is None:
            session = requests.Session()
            session.headers.update(cls._DEFAULT_HEADERS)
            cls._SESSION = session
        return cls._SESSION

    @staticmethod
    def _retry_delay_seconds(response: requests.Response, attempt: int) -> float:
        """Compute bounded retry delay using Retry-After when present."""

        retry_after = response.headers.get("Retry-After", "").strip()
        if retry_after.isdigit():
            return min(max(float(retry_after), 0.5), 4.0)
        return min(0.75 * (attempt + 1), 3.0)

    @staticmethod
    def open(url: str, timeout_seconds: int) -> BrowserResult:
        """Open a web page and return title, links, and visible text summary."""

        try:
            if not url.startswith(("http://", "https://")):
                return BrowserResult(ok=False, output="Only http:// and https:// URLs are supported.")

            session = BrowserTool._session()
            response: requests.Response | None = None
            max_attempts = 3
            for attempt in range(max_attempts):
                response = session.get(url, timeout=timeout_seconds, allow_redirects=True)
                if response.status_code not in {429, 503}:
                    break
                if attempt < max_attempts - 1:
                    time.sleep(BrowserTool._retry_delay_seconds(response=response, attempt=attempt))

            if response is None:
                return BrowserResult(ok=False, output="Browser open error: empty response")

            response.raise_for_status()
            if not response.encoding:
                response.encoding = response.apparent_encoding or "utf-8"
            html = response.text

            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
            title = unescape(title_match.group(1).strip()) if title_match else "(no title)"

            links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
            unique_links: list[str] = []
            for link in links:
                if link not in unique_links:
                    unique_links.append(link)
                if len(unique_links) >= 20:
                    break

            text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = unescape(re.sub(r"\s+", " ", text)).strip()
            if len(text) > 6000:
                text = text[:6000] + " [truncated]"

            output = (
                f"url={url}\n"
                f"status={response.status_code}\n"
                f"title={title}\n"
                f"links={len(unique_links)}\n"
                f"link_preview={unique_links}\n\n"
                f"{text}"
            )
            return BrowserResult(ok=True, output=output.strip())
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            if status_code == 429:
                return BrowserResult(
                    ok=False,
                    output=(
                        "Browser open error: HTTP 429 (rate limited). "
                        "The site is throttling repeated requests; wait briefly and retry."
                    ),
                )
            return BrowserResult(ok=False, output=f"Browser open error: HTTP {status_code}")
        except requests.RequestException as exc:
            return BrowserResult(ok=False, output=f"Browser open error: {exc}")
        except Exception as exc:  # noqa: BLE001
            return BrowserResult(ok=False, output=f"Browser open error: {exc}")
