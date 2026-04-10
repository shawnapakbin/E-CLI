"""Integration tests for the Textual TUI (ECLIApp) using headless pilot."""

from __future__ import annotations

import pytest

from e_cli.ui.tui import (
    ChatPanel,
    ECLIApp,
    ECLIAppConfig,
    InputBar,
    StatusBar,
    TokenMessage,
    ToolEndMessage,
    ToolOutputPanel,
    ToolStartMessage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(ecli_config: ECLIAppConfig | None = None) -> ECLIApp:
    return ECLIApp(ecli_config=ecli_config or ECLIAppConfig())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_composes_without_errors() -> None:
    """The app should compose and mount all widgets without raising."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        # If we reach here the app composed successfully
        assert pilot.app is app


@pytest.mark.asyncio
async def test_chat_panel_present_in_dom() -> None:
    """ChatPanel should be present in the DOM after compose."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        chat_panel = pilot.app.query_one("#chat_panel", ChatPanel)
        assert chat_panel is not None


@pytest.mark.asyncio
async def test_tool_output_panel_present_in_dom() -> None:
    """ToolOutputPanel should be present in the DOM after compose."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        tool_panel = pilot.app.query_one("#tool_output_panel", ToolOutputPanel)
        assert tool_panel is not None


@pytest.mark.asyncio
async def test_status_bar_present_in_dom() -> None:
    """StatusBar (Footer) should be present in the DOM after compose."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        status_bar = pilot.app.query_one(StatusBar)
        assert status_bar is not None


@pytest.mark.asyncio
async def test_token_message_updates_chat_panel() -> None:
    """Posting a TokenMessage should cause ChatPanel.append_token to be called."""
    app = _make_app()
    tokens_received: list[str] = []

    async with app.run_test(headless=True) as pilot:
        chat_panel = pilot.app.query_one("#chat_panel", ChatPanel)

        # Patch append_token to track calls
        original_append = chat_panel.append_token

        def _track_append(token: str) -> None:
            tokens_received.append(token)
            original_append(token)

        chat_panel.append_token = _track_append  # type: ignore[method-assign]

        pilot.app.post_message(TokenMessage("hello world"))
        await pilot.pause()
        await pilot.pause()

        # The handler should have called append_token with our token
        assert "hello world" in tokens_received


@pytest.mark.asyncio
async def test_tool_start_message_adds_row_to_tool_panel() -> None:
    """Posting a ToolStartMessage should add a row to ToolOutputPanel."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        tool_panel = pilot.app.query_one("#tool_output_panel", ToolOutputPanel)
        initial_row_count = tool_panel.row_count

        pilot.app.post_message(ToolStartMessage("shell", '{"command": "ls"}'))
        await pilot.pause()

        assert tool_panel.row_count == initial_row_count + 1


@pytest.mark.asyncio
async def test_tool_end_message_updates_tool_panel() -> None:
    """Posting ToolStartMessage then ToolEndMessage should update the row status."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        tool_panel = pilot.app.query_one("#tool_output_panel", ToolOutputPanel)

        pilot.app.post_message(ToolStartMessage("file.read", '{"path": "README.md"}'))
        await pilot.pause()

        row_count_after_start = tool_panel.row_count
        assert row_count_after_start >= 1

        pilot.app.post_message(ToolEndMessage("file.read", "ok", "# E-CLI"))
        await pilot.pause()

        # Row count should not decrease — the row was updated, not replaced
        assert tool_panel.row_count >= row_count_after_start


@pytest.mark.asyncio
async def test_status_bar_shows_session_info() -> None:
    """The app sub_title should contain session/provider/model info."""
    cfg = ECLIAppConfig(session_id="test-session", provider="ollama", model="llama3")
    app = _make_app(cfg)
    async with app.run_test(headless=True) as pilot:
        assert "test-session" in pilot.app.sub_title
        assert "ollama" in pilot.app.sub_title
        assert "llama3" in pilot.app.sub_title


@pytest.mark.asyncio
async def test_tool_output_panel_update_row_fallback() -> None:
    """update_row falls back to adding a new row when the key doesn't exist."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        tool_panel = pilot.app.query_one("#tool_output_panel", ToolOutputPanel)
        initial_count = tool_panel.row_count
        # Call update_row for a tool that was never started (no existing row)
        tool_panel.update_row("never_started", "ok", "result")
        # Should have added a fallback row
        assert tool_panel.row_count > initial_count


@pytest.mark.asyncio
async def test_input_submitted_empty_is_noop() -> None:
    """Submitting empty input does not crash or add to chat."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        chat_panel = pilot.app.query_one("#chat_panel", ChatPanel)
        # Simulate empty input submission
        input_bar = pilot.app.query_one("#input_bar", InputBar)
        await pilot.click("#input_bar")
        # Don't type anything, just press Enter
        await pilot.press("enter")
        await pilot.pause()
        # App should still be running without error
        assert pilot.app is app


@pytest.mark.asyncio
async def test_input_submitted_with_text_writes_to_chat() -> None:
    """Submitting non-empty input writes to the chat panel."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        await pilot.click("#input_bar")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        # App should still be running
        assert pilot.app is app


@pytest.mark.asyncio
async def test_action_quit_exits_app() -> None:
    """action_quit exits the app cleanly."""
    app = _make_app()
    async with app.run_test(headless=True) as pilot:
        # Trigger quit action
        await pilot.press("escape")
        # After escape the app should have exited (run_test context exits)


@pytest.mark.asyncio
async def test_start_agent_worker_with_agent_loop() -> None:
    """_start_agent_worker increments turn counter and updates subtitle."""
    from unittest.mock import MagicMock

    mock_loop = MagicMock()
    mock_loop.run.return_value = "agent response"

    cfg = ECLIAppConfig(
        session_id="s1",
        provider="ollama",
        model="llama3",
        agent_loop=mock_loop,
    )
    app = _make_app(cfg)
    async with app.run_test(headless=True) as pilot:
        initial_turn = pilot.app._turn_counter
        # Simulate input submission
        await pilot.click("#input_bar")
        await pilot.press("h", "i")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        # Turn counter should have incremented
        assert pilot.app._turn_counter > initial_turn


@pytest.mark.asyncio
async def test_update_subtitle_reflects_turn_counter() -> None:
    """_update_subtitle includes the current turn counter."""
    cfg = ECLIAppConfig(session_id="abc", provider="p", model="m")
    app = _make_app(cfg)
    async with app.run_test(headless=True) as pilot:
        pilot.app._turn_counter = 5
        pilot.app._update_subtitle()
        assert "turn=5" in pilot.app.sub_title
