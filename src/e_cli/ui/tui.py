"""Textual TUI for E-CLI — chat panel, tool-output panel, status bar, and input bar."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, Input, RichLog
from textual.worker import Worker, WorkerState

from e_cli.sub_agent.tui_bridge import SubAgentStatusMessage


# ---------------------------------------------------------------------------
# Message types posted from AgentWorker to the app
# ---------------------------------------------------------------------------


class TokenMessage(Message):
    """Posted when the agent emits a streaming response token."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self.token = token


class ToolStartMessage(Message):
    """Posted when a tool call begins execution."""

    def __init__(self, tool_name: str, args_preview: str) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.args_preview = args_preview


class ToolEndMessage(Message):
    """Posted when a tool call completes."""

    def __init__(self, tool_name: str, status: str, result_preview: str) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.status = status
        self.result_preview = result_preview


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


class ChatPanel(RichLog):
    """Scrollable chat panel that appends streaming tokens."""

    DEFAULT_CSS = """
    ChatPanel {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def append_token(self, token: str) -> None:
        """Append a streaming token to the chat log."""
        self.write(token)


class ToolOutputPanel(DataTable):
    """DataTable showing tool calls with status and result preview."""

    DEFAULT_CSS = """
    ToolOutputPanel {
        height: 10;
        border: solid $secondary;
    }
    """

    def on_mount(self) -> None:
        self.add_columns("tool", "args preview", "status", "result preview")

    def add_row(self, tool_name: str, args_preview: str) -> None:  # type: ignore[override]
        """Add a new row for a tool call that has just started."""
        super().add_row(tool_name, args_preview[:60], "running", "", key=tool_name)

    def update_row(self, tool_name: str, status: str, result_preview: str) -> None:
        """Update the status and result preview for a completed tool call."""
        try:
            row_key = self.get_row(tool_name)  # type: ignore[arg-type]
            # DataTable rows are indexed; find the row by key and update columns 2 and 3
            col_keys = [col.key for col in self.columns.values()]
            status_col = col_keys[2] if len(col_keys) > 2 else None
            result_col = col_keys[3] if len(col_keys) > 3 else None
            if status_col:
                self.update_cell(tool_name, status_col, status)  # type: ignore[arg-type]
            if result_col:
                self.update_cell(tool_name, result_col, result_preview[:60])  # type: ignore[arg-type]
        except Exception:
            # If the row doesn't exist yet, add it as completed
            super().add_row(tool_name, "", status, result_preview[:60], key=f"{tool_name}_done")

    def handle_sub_agent_status(self, message: SubAgentStatusMessage) -> None:
        """Add or update a row for a sub-agent task status update.

        Columns: task_id, status, tool_calls_made, confidence.
        When a message arrives for an existing task_id, the row is updated in place.
        For a new task_id, a new row is appended.
        """
        confidence_str = f"{message.confidence:.2f}" if message.confidence is not None else "—"
        row_key = f"sub_agent:{message.task_id}"
        try:
            # Try to update existing row
            self.get_row(row_key)  # type: ignore[arg-type]
            col_keys = [col.key for col in self.columns.values()]
            if len(col_keys) >= 3:
                self.update_cell(row_key, col_keys[1], message.status)  # type: ignore[arg-type]
                self.update_cell(row_key, col_keys[2], str(message.tool_calls_made))  # type: ignore[arg-type]
            if len(col_keys) >= 4:
                self.update_cell(row_key, col_keys[3], confidence_str)  # type: ignore[arg-type]
        except Exception:
            # Row doesn't exist yet — add it
            super().add_row(
                message.task_id,
                message.status,
                str(message.tool_calls_made),
                confidence_str,
                key=row_key,
            )


class StatusBar(Footer):
    """Footer-based status bar showing session info."""

    pass


class InputBar(Input):
    """Text input widget for user messages."""

    DEFAULT_CSS = """
    InputBar {
        dock: bottom;
    }
    """


# ---------------------------------------------------------------------------
# Main Textual app
# ---------------------------------------------------------------------------


@dataclass
class ECLIAppConfig:
    """Configuration passed into ECLIApp at construction time."""

    session_id: str = ""
    provider: str = ""
    model: str = ""
    agent_loop: Any = None  # AgentLoop instance, optional


class ECLIApp(App[None]):
    """Main Textual application for E-CLI."""

    TITLE = "E-CLI"
    CSS = """
    Screen {
        layout: vertical;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ]

    def __init__(self, ecli_config: ECLIAppConfig | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ecli_config = ecli_config or ECLIAppConfig()
        self._turn_counter: int = 0
        self._worker: Worker[None] | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield ChatPanel(id="chat_panel", highlight=True, markup=True)
        yield ToolOutputPanel(id="tool_output_panel")
        yield InputBar(id="input_bar", placeholder="Type a message and press Enter…")
        yield StatusBar()

    def on_mount(self) -> None:
        cfg = self._ecli_config
        self.sub_title = (
            f"session={cfg.session_id or 'new'} | "
            f"provider={cfg.provider or 'none'} | "
            f"model={cfg.model or 'none'} | "
            f"turn={self._turn_counter}"
        )

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission and start the agent worker."""
        user_text = event.value.strip()
        if not user_text:
            return
        input_bar = self.query_one("#input_bar", InputBar)
        input_bar.clear()

        chat_panel = self.query_one("#chat_panel", ChatPanel)
        chat_panel.write(f"\n[bold cyan]You:[/bold cyan] {user_text}\n")

        if self._ecli_config.agent_loop is not None:
            self._start_agent_worker(user_text)

    # ------------------------------------------------------------------
    # AgentWorker
    # ------------------------------------------------------------------

    def _start_agent_worker(self, user_prompt: str) -> None:
        """Launch the agent loop in a background worker thread."""
        self._turn_counter += 1
        self._update_subtitle()

        agent_loop = self._ecli_config.agent_loop
        session_id = self._ecli_config.session_id

        def _run_agent() -> None:
            """Worker function that runs the agent loop and posts messages."""
            try:
                # Post a synthetic token for the start of the response
                self.post_message(TokenMessage("\n[bold green]Agent:[/bold green] "))

                result = agent_loop.run(
                    userPrompt=user_prompt,
                    sessionId=session_id,
                )
                # Post the final answer as tokens
                for chunk in (result or ""):
                    self.post_message(TokenMessage(chunk))
                self.post_message(TokenMessage("\n"))
            except Exception as exc:
                self.post_message(TokenMessage(f"\n[red]Error: {exc}[/red]\n"))

        self._worker = self.run_worker(_run_agent, thread=True)

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_token_message(self, message: TokenMessage) -> None:
        """Append a streaming token to the chat panel."""
        chat_panel = self.query_one("#chat_panel", ChatPanel)
        chat_panel.append_token(message.token)

    def on_tool_start_message(self, message: ToolStartMessage) -> None:
        """Add a row to the tool output panel when a tool starts."""
        tool_panel = self.query_one("#tool_output_panel", ToolOutputPanel)
        tool_panel.add_row(message.tool_name, message.args_preview)

    def on_tool_end_message(self, message: ToolEndMessage) -> None:
        """Update the tool output panel row when a tool completes."""
        tool_panel = self.query_one("#tool_output_panel", ToolOutputPanel)
        tool_panel.update_row(message.tool_name, message.status, message.result_preview)

    def on_sub_agent_status_message(self, message: SubAgentStatusMessage) -> None:
        """Forward sub-agent status updates to the tool output panel."""
        tool_panel = self.query_one("#tool_output_panel", ToolOutputPanel)
        tool_panel.handle_sub_agent_status(message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_subtitle(self) -> None:
        cfg = self._ecli_config
        self.sub_title = (
            f"session={cfg.session_id or 'new'} | "
            f"provider={cfg.provider or 'none'} | "
            f"model={cfg.model or 'none'} | "
            f"turn={self._turn_counter}"
        )

    def action_quit(self) -> None:
        """Clean shutdown: cancel any running worker and exit."""
        if self._worker is not None and self._worker.state == WorkerState.RUNNING:
            self._worker.cancel()
        self.exit()
