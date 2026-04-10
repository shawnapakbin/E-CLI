"""TUI bridge for sub-agent status updates.

Posts SubAgentStatusMessage instances to the Textual app's message bus.
All operations are no-ops when the TUI is not running (app is None or not a Textual App).
"""

from __future__ import annotations

import logging

from textual.message import Message

logger = logging.getLogger(__name__)


class SubAgentStatusMessage(Message):
    """Textual Message carrying a sub-agent task status update.

    Fields:
        task_id:         Unique identifier for the sub-agent task.
        status:          One of: queued | running | completed | failed | timeout
        tool_calls_made: Number of tool calls the sub-agent has made so far.
        confidence:      Self-reported confidence score (0.0–1.0), or None if unknown.
    """

    def __init__(
        self,
        task_id: str,
        status: str,
        tool_calls_made: int,
        confidence: float | None,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.status = status  # queued | running | completed | failed | timeout
        self.tool_calls_made = tool_calls_made
        self.confidence = confidence


def post_status_update(app: object, message: SubAgentStatusMessage) -> None:
    """Post a SubAgentStatusMessage to the Textual app's message bus.

    This is a no-op (no crash) when the TUI is not running — i.e. when
    *app* is None or is not a Textual App instance.
    """
    if app is None:
        return

    try:
        from textual.app import App  # local import to keep the check lazy

        if not isinstance(app, App):
            return

        app.post_message(message)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to post SubAgentStatusMessage to TUI: %s", exc)
