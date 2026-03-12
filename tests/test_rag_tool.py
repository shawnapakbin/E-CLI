"""Tests for lightweight RAG retrieval tool behavior."""

from pathlib import Path
import sqlite3

from e_cli.tools.rag_tool import RagTool


def _build_memory_db(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE memory_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE conversation_summaries (
                session_id TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                covered_until_id INTEGER NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO memory_entries(created_at, session_id, role, content)
            VALUES ('2026-03-12T00:00:00Z', 's1', 'user', 'router execute flow and safety policy notes')
            """
        )
        connection.execute(
            """
            INSERT INTO conversation_summaries(session_id, updated_at, covered_until_id, content)
            VALUES ('s1', '2026-03-12T01:00:00Z', 1, 'Prior conversation summary: router dispatch and tool audit')
            """
        )
        connection.commit()


def test_rag_search_requires_non_empty_query(tmp_path: Path) -> None:
    """Ensures empty query is rejected before retrieval."""

    result = RagTool.search(
        query="   ",
        timeout_seconds=3,
        workspace_root=tmp_path,
        memory_db_path=None,
    )
    assert result.ok is False


def test_rag_search_rejects_invalid_corpus(tmp_path: Path) -> None:
    """Ensures unsupported corpus names fail fast."""

    result = RagTool.search(
        query="router",
        timeout_seconds=3,
        workspace_root=tmp_path,
        memory_db_path=None,
        corpus="invalid",
    )
    assert result.ok is False


def test_rag_search_combined_returns_memory_and_workspace_matches(tmp_path: Path) -> None:
    """Ensures combined mode includes relevant snippets from both corpora."""

    memory_db = tmp_path / "memory.db"
    _build_memory_db(memory_db)
    code_file = tmp_path / "src" / "module.py"
    code_file.parent.mkdir(parents=True, exist_ok=True)
    code_file.write_text("def execute_router():\n    return 'router execute'\n", encoding="utf-8")

    result = RagTool.search(
        query="router execute",
        timeout_seconds=5,
        workspace_root=tmp_path,
        memory_db_path=memory_db,
        corpus="combined",
        top_k=5,
    )

    assert result.ok is True
    assert "source" not in result.output  # ensure formatted output, not raw object dumps
    assert "memory:" in result.output or "summary:" in result.output
    assert "file:" in result.output


def test_rag_search_truncates_large_output(tmp_path: Path) -> None:
    """Ensures response output is bounded for prompt safety."""

    big_file = tmp_path / "notes.md"
    big_file.write_text(("router " * 4000), encoding="utf-8")

    result = RagTool.search(
        query="router",
        timeout_seconds=5,
        workspace_root=tmp_path,
        memory_db_path=None,
        corpus="workspace",
        top_k=10,
    )

    assert result.ok is True
    assert len(result.output) <= 8015