"""Unit tests for PlaywrightTool — all playwright.async_api calls are mocked."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from e_cli.tools.playwright_tool import PlaywrightTool, _SELECTOR_TIMEOUT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool() -> PlaywrightTool:
    return PlaywrightTool()


def _make_timeout_error() -> Exception:
    """Return a fake TimeoutError whose class name contains 'timeout'."""
    class TimeoutError(Exception):  # noqa: N818
        pass
    return TimeoutError("Timed out waiting for selector")


def _mock_page(url: str = "https://example.com", title: str = "Example") -> MagicMock:
    page = MagicMock()
    page.url = url
    page.is_closed.return_value = False
    page.goto = AsyncMock(return_value=MagicMock(status=200))
    page.title = AsyncMock(return_value=title)
    page.screenshot = AsyncMock()
    page.evaluate = AsyncMock(return_value="eval_result")
    page.close = AsyncMock()
    page.on = MagicMock()

    locator = MagicMock()
    locator.click = AsyncMock()
    locator.wait_for = AsyncMock()
    locator.focus = AsyncMock()
    locator.type = AsyncMock()
    locator.inner_text = AsyncMock(return_value="some text")
    locator.inner_html = AsyncMock(return_value="<p>html</p>")
    page.locator = MagicMock(return_value=locator)
    return page


def _mock_context(page: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.new_page = AsyncMock(return_value=page)
    ctx.close = AsyncMock()
    ctx.on = MagicMock()
    return ctx


def _mock_browser(context: MagicMock) -> MagicMock:
    browser = MagicMock()
    browser.is_connected.return_value = True
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()
    return browser


def _mock_playwright(browser: MagicMock) -> MagicMock:
    pw = MagicMock()
    pw.chromium = MagicMock()
    pw.chromium.launch = AsyncMock(return_value=browser)
    pw.stop = AsyncMock()
    return pw


async def _setup_tool_with_mocks(
    tool: PlaywrightTool,
    headless: bool = True,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Inject mock playwright stack into *tool* and return (pw, browser, ctx, page)."""
    page = _mock_page()
    ctx = _mock_context(page)
    browser = _mock_browser(ctx)
    pw = _mock_playwright(browser)

    # Directly inject so _ensure_context short-circuits (no module-level patch needed
    # because the import is lazy inside _ensure_context).
    tool._playwright = pw
    tool._browser = browser
    tool._context = ctx
    tool._page = page

    return pw, browser, ctx, page


# ---------------------------------------------------------------------------
# navigate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_navigate_returns_url_status_title() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)

    result = await tool.execute("navigate", url="https://example.com")

    assert result.ok is True
    assert "url=https://example.com" in result.output
    assert "status=200" in result.output
    assert "title=Example" in result.output
    page.goto.assert_awaited_once_with("https://example.com", timeout=_SELECTOR_TIMEOUT)


# ---------------------------------------------------------------------------
# click
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_click_success() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)

    result = await tool.execute("click", selector="#btn")

    assert result.ok is True
    assert "#btn" in result.output
    page.locator.assert_called_with("#btn")


@pytest.mark.asyncio
async def test_click_timeout_returns_false() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)
    page.locator.return_value.click = AsyncMock(side_effect=_make_timeout_error())

    result = await tool.execute("click", selector="#missing")

    assert result.ok is False
    assert "#missing" in result.output


# ---------------------------------------------------------------------------
# type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_type_success() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)

    result = await tool.execute("type", selector="input", text="hello")

    assert result.ok is True
    assert "hello" in result.output


@pytest.mark.asyncio
async def test_type_timeout_returns_false() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)
    page.locator.return_value.wait_for = AsyncMock(side_effect=_make_timeout_error())

    result = await tool.execute("type", selector="#ghost", text="x")

    assert result.ok is False
    assert "#ghost" in result.output


# ---------------------------------------------------------------------------
# screenshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screenshot_returns_abs_path(tmp_path: Path) -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)
    dest = str(tmp_path / "shot.png")

    result = await tool.execute("screenshot", path=dest)

    assert result.ok is True
    assert "shot.png" in result.output
    page.screenshot.assert_awaited_once()


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_returns_result() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)
    page.evaluate = AsyncMock(return_value=42)

    result = await tool.execute("evaluate", expression="1+1")

    assert result.ok is True
    assert "42" in result.output


# ---------------------------------------------------------------------------
# get_text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_text_success() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)

    result = await tool.execute("get_text", selector="p")

    assert result.ok is True
    assert "some text" in result.output


@pytest.mark.asyncio
async def test_get_text_timeout_returns_false() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)
    page.locator.return_value.inner_text = AsyncMock(side_effect=_make_timeout_error())

    result = await tool.execute("get_text", selector=".gone")

    assert result.ok is False
    assert ".gone" in result.output


# ---------------------------------------------------------------------------
# get_html
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_html_success() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)

    result = await tool.execute("get_html", selector="body")

    assert result.ok is True
    assert "<p>html</p>" in result.output


@pytest.mark.asyncio
async def test_get_html_timeout_returns_false() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)
    page.locator.return_value.inner_html = AsyncMock(side_effect=_make_timeout_error())

    result = await tool.execute("get_html", selector="#nope")

    assert result.ok is False
    assert "#nope" in result.output


# ---------------------------------------------------------------------------
# wait_for_selector
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wait_for_selector_success() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)

    result = await tool.execute("wait_for_selector", selector=".ready")

    assert result.ok is True
    assert ".ready" in result.output


@pytest.mark.asyncio
async def test_wait_for_selector_timeout_returns_false() -> None:
    tool = _make_tool()
    _, _, _, page = await _setup_tool_with_mocks(tool)
    page.locator.return_value.wait_for = AsyncMock(side_effect=_make_timeout_error())

    result = await tool.execute("wait_for_selector", selector=".never")

    assert result.ok is False
    assert ".never" in result.output


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_releases_resources() -> None:
    tool = _make_tool()
    _, browser, ctx, page = await _setup_tool_with_mocks(tool)

    result = await tool.execute("close")

    assert result.ok is True
    page.close.assert_awaited()
    ctx.close.assert_awaited()
    browser.close.assert_awaited()
    assert tool._playwright is None
    assert tool._browser is None
    assert tool._context is None
    assert tool._page is None


# ---------------------------------------------------------------------------
# session reuse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_reused_across_calls() -> None:
    tool = _make_tool()
    _, browser, ctx, page = await _setup_tool_with_mocks(tool)

    await tool.execute("navigate", url="https://a.com")
    await tool.execute("navigate", url="https://b.com")

    # new_context should NOT have been called again (context already exists)
    browser.new_context.assert_not_awaited()


# ---------------------------------------------------------------------------
# unknown action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_action_returns_false() -> None:
    tool = _make_tool()
    await _setup_tool_with_mocks(tool)

    result = await tool.execute("fly_to_moon")

    assert result.ok is False
    assert "fly_to_moon" in result.output


# ---------------------------------------------------------------------------
# handoff_to_user — browser closed by user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handoff_browser_closed_by_user() -> None:
    tool = _make_tool()
    _, browser, ctx, page = await _setup_tool_with_mocks(tool)

    # Simulate browser being closed: after relaunch, page is closed
    closed_page = MagicMock()
    closed_page.url = ""
    closed_page.is_closed.return_value = True
    closed_page.on = MagicMock()

    closed_ctx = MagicMock()
    closed_ctx.new_page = AsyncMock(return_value=closed_page)
    closed_ctx.close = AsyncMock()
    closed_ctx.on = MagicMock()

    closed_browser = MagicMock()
    closed_browser.is_connected.return_value = False
    closed_browser.new_context = AsyncMock(return_value=closed_ctx)
    closed_browser.close = AsyncMock()

    tool._playwright.chromium.launch = AsyncMock(return_value=closed_browser)

    # Patch input() to return immediately (simulating Enter press)
    with patch("builtins.input", return_value=""):
        result = await tool.execute("handoff_to_user")

    assert result.ok is False
    assert "Browser closed by user during handoff" in result.output
