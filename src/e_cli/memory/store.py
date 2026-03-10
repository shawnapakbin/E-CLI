"""SQLite memory store for conversation history persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class MemoryEntry:
    """Represents one persisted message entry in memory history."""

    sessionId: str
    role: str
    content: str
    createdAt: str


@dataclass(frozen=True)
class SessionSummary:
    """Represents one session overview row for session management commands."""

    sessionId: str
    messageCount: int
    lastCreatedAt: str


class MemoryStore:
    """Provides low-level SQLite operations for memory persistence and recall."""

    def __init__(self, dbPath: Path, schemaPath: Path) -> None:
        """Initializes store paths and ensures schema is applied once."""

        self.dbPath = dbPath
        self.schemaPath = schemaPath
        self.dbPath.parent.mkdir(parents=True, exist_ok=True)
        self._ensureSchema()

    def _connect(self) -> sqlite3.Connection:
        """Creates one sqlite connection for a scoped operation."""

        try:
            connection = sqlite3.connect(str(self.dbPath))
            connection.row_factory = sqlite3.Row
            return connection
        except Exception as exc:
            raise RuntimeError(f"Failed to connect memory database: {exc}") from exc

    @contextmanager
    def _connectionScope(self) -> sqlite3.Connection:
        """Yield one sqlite connection and always close it after use."""

        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _ensureSchema(self) -> None:
        """Applies table/index schema for memory storage."""

        try:
            schemaSql = self.schemaPath.read_text(encoding="utf-8")
            with self._connectionScope() as connection:
                connection.executescript(schemaSql)
                connection.commit()
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize memory schema: {exc}") from exc

    def append(self, sessionId: str, role: str, content: str) -> None:
        """Appends one message entry to persistent memory."""

        try:
            createdAt = datetime.now(tz=timezone.utc).isoformat()
            with self._connectionScope() as connection:
                connection.execute(
                    """
                    INSERT INTO memory_entries(created_at, session_id, role, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (createdAt, sessionId, role, content),
                )
                connection.commit()
        except Exception as exc:
            raise RuntimeError(f"Failed to append memory entry: {exc}") from exc

    def listBySession(self, sessionId: str, limit: int = 40) -> list[MemoryEntry]:
        """Returns most-recent message entries for a specific session."""

        try:
            with self._connectionScope() as connection:
                rows = connection.execute(
                    """
                    SELECT created_at, session_id, role, content
                    FROM memory_entries
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (sessionId, limit),
                ).fetchall()
            orderedRows = list(reversed(rows))
            return [
                MemoryEntry(
                    sessionId=str(row["session_id"]),
                    role=str(row["role"]),
                    content=str(row["content"]),
                    createdAt=str(row["created_at"]),
                )
                for row in orderedRows
            ]
        except Exception as exc:
            raise RuntimeError(f"Failed to read memory entries: {exc}") from exc

    def listSessions(self, limit: int = 20) -> list[SessionSummary]:
        """Returns recent sessions ordered by most recent activity."""

        try:
            with self._connectionScope() as connection:
                rows = connection.execute(
                    """
                    SELECT session_id, COUNT(*) AS message_count, MAX(created_at) AS last_created_at
                    FROM memory_entries
                    GROUP BY session_id
                    ORDER BY last_created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [
                SessionSummary(
                    sessionId=str(row["session_id"]),
                    messageCount=int(row["message_count"]),
                    lastCreatedAt=str(row["last_created_at"]),
                )
                for row in rows
            ]
        except Exception as exc:
            raise RuntimeError(f"Failed to list sessions: {exc}") from exc
