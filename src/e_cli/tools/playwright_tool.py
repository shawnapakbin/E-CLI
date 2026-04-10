"""Playwright-based headless browser tool with session-scoped BrowserContext."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from e_cli.agent.protocol import ToolResult

_log = logging.getLogger(__name__)

_SELECTOR_TIMEOUT = 10_000  # ms


class PlaywrightTool:
    """Drives a headless Chromium browser via Playwright.

    A single BrowserContext is reused across all calls within an agent session.
    Call ``close()`` or use as an async context manager to release resources.
    """

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._handoff_event: asyncio.Event | None = None

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def _ensure_context(self, headless: bool = True) -> None:
        """Lazily initialise Playwright, browser, context, and page."""
        if self._playwright is None:
            from playwright.async_api import async_playwright  # type: ignore[import]

            self._playwright = await async_playwright().start()

        if self._browser is None or not self._browser.is_connected():
            self._browser = await self._playwright.chromium.launch(headless=headless)

        if self._context is None:
            self._context = await self._browser.new_context()

        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()

    async def _close_context(self) -> None:
        """Close the current context and page without stopping the browser."""
        if self._page and not self._page.is_closed():
            await self._page.close()
        self._page = None
        if self._context:
            await self._context.close()
        self._context = None

    async def close(self) -> None:
        """Release all Playwright resources."""
        await self._close_context()
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    # ------------------------------------------------------------------
    # Public dispatch entry point
    # ------------------------------------------------------------------

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        """Dispatch *action* to the matching handler method."""
        handler = getattr(self, f"_action_{action}", None)
        if handler is None:
            return ToolResult(ok=False, output=f"Unknown browser action: {action!r}")
        try:
            return await handler(**kwargs)
        except Exception as exc:
            _log.exception("PlaywrightTool action %r raised an unexpected error", action)
            return ToolResult(ok=False, output=f"Browser error during {action!r}: {exc}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def _action_navigate(self, url: str, **_: Any) -> ToolResult:
        await self._ensure_context()
        response = await self._page.goto(url, timeout=_SELECTOR_TIMEOUT)
        status = response.status if response else "unknown"
        title = await self._page.title()
        return ToolResult(ok=True, output=f"url={url}\nstatus={status}\ntitle={title}")

    async def _action_click(self, selector: str, **_: Any) -> ToolResult:
        await self._ensure_context()
        try:
            await self._page.locator(selector).click(timeout=_SELECTOR_TIMEOUT)
            return ToolResult(ok=True, output=f"Clicked: {selector}")
        except Exception as exc:
            if "timeout" in type(exc).__name__.lower() or "TimeoutError" in str(type(exc)):
                return ToolResult(ok=False, output=f"Selector not found within timeout: {selector}")
            raise

    async def _action_type(self, selector: str, text: str, **_: Any) -> ToolResult:
        await self._ensure_context()
        try:
            locator = self._page.locator(selector)
            await locator.wait_for(state="visible", timeout=_SELECTOR_TIMEOUT)
            await locator.focus(timeout=_SELECTOR_TIMEOUT)
            await locator.type(text, timeout=_SELECTOR_TIMEOUT)
            return ToolResult(ok=True, output=f"Typed into {selector!r}: {text!r}")
        except Exception as exc:
            if "timeout" in type(exc).__name__.lower() or "TimeoutError" in str(type(exc)):
                return ToolResult(ok=False, output=f"Selector not found within timeout: {selector}")
            raise

    async def _action_screenshot(self, path: str, **_: Any) -> ToolResult:
        await self._ensure_context()
        abs_path = str(Path(path).expanduser().resolve())
        await self._page.screenshot(path=abs_path)
        return ToolResult(ok=True, output=f"Screenshot saved: {abs_path}")

    async def _action_evaluate(self, expression: str, **_: Any) -> ToolResult:
        await self._ensure_context()
        result = await self._page.evaluate(expression)
        return ToolResult(ok=True, output=str(result))

    async def _action_get_text(self, selector: str, **_: Any) -> ToolResult:
        await self._ensure_context()
        try:
            text = await self._page.locator(selector).inner_text(timeout=_SELECTOR_TIMEOUT)
            return ToolResult(ok=True, output=text)
        except Exception as exc:
            if "timeout" in type(exc).__name__.lower() or "TimeoutError" in str(type(exc)):
                return ToolResult(ok=False, output=f"Selector not found within timeout: {selector}")
            raise

    async def _action_get_html(self, selector: str = "html", **_: Any) -> ToolResult:
        await self._ensure_context()
        try:
            html = await self._page.locator(selector).inner_html(timeout=_SELECTOR_TIMEOUT)
            return ToolResult(ok=True, output=html)
        except Exception as exc:
            if "timeout" in type(exc).__name__.lower() or "TimeoutError" in str(type(exc)):
                return ToolResult(ok=False, output=f"Selector not found within timeout: {selector}")
            raise

    async def _action_wait_for_selector(self, selector: str, **_: Any) -> ToolResult:
        await self._ensure_context()
        try:
            await self._page.locator(selector).wait_for(state="visible", timeout=_SELECTOR_TIMEOUT)
            return ToolResult(ok=True, output=f"Selector visible: {selector}")
        except Exception as exc:
            if "timeout" in type(exc).__name__.lower() or "TimeoutError" in str(type(exc)):
                return ToolResult(ok=False, output=f"Selector not found within timeout: {selector}")
            raise

    async def _action_close(self, **_: Any) -> ToolResult:
        await self.close()
        return ToolResult(ok=True, output="Browser context closed.")

    async def _action_handoff_to_user(self, **_: Any) -> ToolResult:
        """Pause agent control, open a headed browser, and wait for the user to press Enter."""
        # Capture current URL before closing headless context
        current_url = ""
        if self._page and not self._page.is_closed():
            current_url = self._page.url

        await self._close_context()

        # Reopen in headed (visible) mode
        if self._browser:
            await self._browser.close()
            self._browser = None

        await self._ensure_context(headless=False)

        # Navigate to the last known URL if available
        if current_url:
            try:
                await self._page.goto(current_url, timeout=_SELECTOR_TIMEOUT)
            except Exception:
                pass  # Best-effort; user can navigate manually

        print("\n[e-cli] Browser handed off to you. Press Enter in this terminal to resume agent control.")

        self._handoff_event = asyncio.Event()

        # Detect browser close
        def _on_close() -> None:
            if self._handoff_event:
                self._handoff_event.set()

        self._page.on("close", _on_close)
        self._context.on("close", _on_close)

        # Wait for Enter in a thread so we don't block the event loop
        loop = asyncio.get_event_loop()
        enter_task = loop.run_in_executor(None, input)
        close_wait = asyncio.ensure_future(self._handoff_event.wait())

        done, pending = await asyncio.wait(
            [asyncio.ensure_future(enter_task), close_wait],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        # Check if browser was closed by user
        browser_closed = self._browser is None or not self._browser.is_connected()
        if not browser_closed and self._page:
            browser_closed = self._page.is_closed()

        if browser_closed:
            self._page = None
            self._context = None
            self._browser = None
            return ToolResult(ok=False, output="Browser closed by user during handoff")

        # Switch back to headless
        page_url = self._page.url if self._page and not self._page.is_closed() else ""
        page_title = ""
        if self._page and not self._page.is_closed():
            try:
                page_title = await self._page.title()
            except Exception:
                pass

        await self._close_context()
        if self._browser:
            await self._browser.close()
            self._browser = None

        await self._ensure_context(headless=True)
        if page_url:
            try:
                await self._page.goto(page_url, timeout=_SELECTOR_TIMEOUT)
            except Exception:
                pass

        return ToolResult(
            ok=True,
            output=f"Handoff complete. Resumed at url={page_url} title={page_title!r}",
        )
