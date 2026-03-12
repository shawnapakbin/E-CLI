"""Tests for SQLite-backed memory storage and retrieval."""

from pathlib import Path

from e_cli.memory.service import MemoryService
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


def test_memory_store_persists_summary_and_audit(tmp_path: Path) -> None:
    """Ensures summary and audit tables are usable through the store API."""

    dbPath = tmp_path / "memory.db"
    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=dbPath, schemaPath=schemaPath)

    store.append(sessionId="s1", role="user", content="hello")
    store.upsertConversationSummary(sessionId="s1", content="Prior conversation summary", coveredUntilId=1)
    store.appendAuditEvent(
        sessionId="s1",
        action="tool.execute",
        tool="shell",
        approved=True,
        status="ok",
        reason="test",
        details="exitCode=0",
    )

    summary = store.getConversationSummary(sessionId="s1")
    auditEvents = store.listAuditEvents(sessionId="s1")

    assert summary is not None
    assert summary.coveredUntilId == 1
    assert len(auditEvents) == 1
    assert auditEvents[0].tool == "shell"


def test_memory_store_delete_entries_through(tmp_path: Path) -> None:
    """Ensures compaction pruning deletes older raw entries through a cutoff id."""

    dbPath = tmp_path / "memory.db"
    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=dbPath, schemaPath=schemaPath)

    store.append(sessionId="s1", role="user", content="one")
    store.append(sessionId="s1", role="assistant", content="two")
    store.append(sessionId="s1", role="user", content="three")

    deletedCount = store.deleteEntriesThrough(sessionId="s1", throughId=2)
    entries = store.listAllBySession(sessionId="s1")

    assert deletedCount == 2
    assert len(entries) == 1
    assert entries[0].content == "three"


def test_memory_service_compact_session_prunes_and_loads_summary(tmp_path: Path) -> None:
    """Ensures explicit compaction prunes old rows and later loads include the stored summary."""

    dbPath = tmp_path / "memory.db"
    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=dbPath, schemaPath=schemaPath)
    service = MemoryService(memoryStore=store)

    for index in range(10):
        role = "user" if index % 2 == 0 else "assistant"
        service.appendMessage(sessionId="session-a", role=role, content=f"message {index} " + ("x" * 120))

    result = service.compactSession(sessionId="session-a", keepRecent=3, targetTokens=180, dryRun=False)
    remainingEntries = store.listAllBySession(sessionId="session-a")
    summary = store.getConversationSummary(sessionId="session-a")
    loadedMessages = service.loadConversation(sessionId="session-a", maxTokens=3200, summaryTokens=800)

    assert result.compactedEntryCount > 0
    assert result.deletedEntryCount == result.compactedEntryCount
    assert len(remainingEntries) == result.retainedEntryCount
    assert summary is not None
    assert summary.coveredUntilId == result.coveredUntilId
    assert loadedMessages[0].role == "system"
    assert "Prior conversation summary" in loadedMessages[0].content
    assert len(loadedMessages) == len(remainingEntries) + 1


def test_memory_service_compact_session_dry_run_leaves_entries_unchanged(tmp_path: Path) -> None:
    """Ensures dry-run compaction reports results without mutating stored entries."""

    dbPath = tmp_path / "memory.db"
    schemaPath = Path(__file__).resolve().parents[1] / "src" / "e_cli" / "memory" / "schema.sql"
    store = MemoryStore(dbPath=dbPath, schemaPath=schemaPath)
    service = MemoryService(memoryStore=store)

    for index in range(6):
        service.appendMessage(sessionId="session-dry", role="user", content=f"message {index} " + ("y" * 100))

    beforeEntries = store.listAllBySession(sessionId="session-dry")
    result = service.compactSession(sessionId="session-dry", keepRecent=2, targetTokens=120, dryRun=True)
    afterEntries = store.listAllBySession(sessionId="session-dry")
    summary = store.getConversationSummary(sessionId="session-dry")

    assert result.dryRun is True
    assert result.compactedEntryCount > 0
    assert result.deletedEntryCount == 0
    assert len(beforeEntries) == len(afterEntries)
    assert summary is None
