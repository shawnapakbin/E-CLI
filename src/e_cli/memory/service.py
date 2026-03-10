"""Higher-level memory service that converts storage entries to model messages."""

from __future__ import annotations

from e_cli.memory.store import MemoryEntry, MemoryStore, SessionSummary
from e_cli.models.base import ModelMessage


class MemoryService:
    """Coordinates memory persistence and retrieval for agent conversations."""

    def __init__(self, memoryStore: MemoryStore) -> None:
        """Stores memory backend dependency for read/write operations."""

        self.memoryStore = memoryStore

    def appendMessage(self, sessionId: str, role: str, content: str) -> None:
        """Persists one message to long-term session memory."""

        try:
            self.memoryStore.append(sessionId=sessionId, role=role, content=content)
        except Exception as exc:
            raise RuntimeError(f"Failed to append message to memory service: {exc}") from exc

    def loadConversation(self, sessionId: str, limit: int = 40) -> list[ModelMessage]:
        """Loads session memory and maps it to model message format."""

        try:
            entries = self.memoryStore.listBySession(sessionId=sessionId, limit=limit)
            return [ModelMessage(role=entry.role, content=entry.content) for entry in entries]
        except Exception as exc:
            raise RuntimeError(f"Failed to load conversation memory: {exc}") from exc

    def loadEntries(self, sessionId: str, limit: int = 40) -> list[MemoryEntry]:
        """Loads raw session entries for CLI inspection commands."""

        try:
            return self.memoryStore.listBySession(sessionId=sessionId, limit=limit)
        except Exception as exc:
            raise RuntimeError(f"Failed to load session entries: {exc}") from exc

    def listSessions(self, limit: int = 20) -> list[SessionSummary]:
        """Loads recent session summaries for session listing commands."""

        try:
            return self.memoryStore.listSessions(limit=limit)
        except Exception as exc:
            raise RuntimeError(f"Failed to list session summaries: {exc}") from exc
