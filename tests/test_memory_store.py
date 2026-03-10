"""Tests for SQLite-backed memory storage and retrieval."""

from pathlib import Path

from e_cli.memory.store import MemoryStore


def test_memory_store_append_and_list(tmp_path: Path) -> None:
    """Ensures message entries persist and can be recalled by session."""

    dbPath = tmp_path / "memory.db"
    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=dbPath, schemaPath=schemaPath)

    store.append(sessionId="s1", role="user", content="hello")
    store.append(sessionId="s1", role="assistant", content="hi")
    entries = store.listBySession(sessionId="s1")

    assert len(entries) == 2
    assert entries[0].role == "user"
    assert entries[1].role == "assistant"


def test_memory_store_lists_recent_sessions(tmp_path: Path) -> None:
    """Ensures session summaries are grouped and sorted by last activity."""

    dbPath = tmp_path / "memory.db"
    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=dbPath, schemaPath=schemaPath)

    store.append(sessionId="session-a", role="user", content="hello")
    store.append(sessionId="session-b", role="user", content="hi")
    store.append(sessionId="session-b", role="assistant", content="there")

    sessions = store.listSessions(limit=10)

    assert len(sessions) == 2
    assert sessions[0].sessionId == "session-b"
    assert sessions[0].messageCount == 2
    assert sessions[1].sessionId == "session-a"
    assert sessions[1].messageCount == 1
