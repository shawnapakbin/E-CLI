"""Centralized logger setup for E-CLI."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for concise terminal diagnostics."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger(name)


def buildLogRecord(eventName: str, payload: dict[str, object]) -> str:
    """Return deterministic JSON log payloads for structured events."""

    try:
        record = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "event": eventName,
            "payload": payload,
        }
        return json.dumps(record, ensure_ascii=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to build structured log record: {exc}") from exc
