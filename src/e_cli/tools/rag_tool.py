"""Lightweight RAG retrieval over session memory, workspace files, and doc index."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3
import time

# Location of the doc index manifest (same as DocIndexer uses)
_DOC_INDEX_DIR = Path("~/.e-cli/doc_index").expanduser()
_DOC_MANIFEST_PATH = _DOC_INDEX_DIR / "manifest.json"
# In-memory store for doc chunks: corpus -> list[str]
_doc_chunks: dict[str, list[str]] = {}


@dataclass(slots=True)
class RagResult:
    """Structured result for RAG tool execution."""

    ok: bool
    output: str


@dataclass(slots=True)
class _Candidate:
    """One ranked retrieval candidate."""

    source: str
    label: str
    snippet: str
    score: float


class RagTool:
    """Provides simple keyword/BM25-style retrieval without external dependencies."""

    _MAX_OUTPUT_CHARS = 8000
    _TEXT_SUFFIXES = {".py", ".md", ".txt"}
    _SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build"}

    @staticmethod
    def add_chunks(corpus: str, chunks: list[str]) -> None:
        """Store text chunks under *corpus* for later retrieval via search."""
        if corpus not in _doc_chunks:
            _doc_chunks[corpus] = []
        _doc_chunks[corpus].extend(chunks)

    @staticmethod
    def search(
        query: str,
        timeout_seconds: int,
        workspace_root: Path,
        memory_db_path: Path | None,
        corpus: str = "combined",
        top_k: int = 5,
    ) -> RagResult:
        """Retrieve relevant snippets from memory, workspace, or both."""

        try:
            query_text = query.strip()
            if not query_text:
                return RagResult(ok=False, output="RAG search requires a non-empty query.")

            normalized_corpus = corpus.strip().lower()
            if normalized_corpus not in {"session", "workspace", "combined"}:
                return RagResult(ok=False, output="Invalid corpus. Use session, workspace, or combined.")

            normalized_top_k = max(1, min(int(top_k), 10))
            deadline = time.monotonic() + max(1, timeout_seconds)
            candidates: list[_Candidate] = []

            if normalized_corpus in {"session", "combined"} and memory_db_path is not None:
                candidates.extend(RagTool._search_memory(query_text, memory_db_path, deadline))

            if normalized_corpus in {"workspace", "combined"}:
                candidates.extend(RagTool._search_workspace(query_text, workspace_root, deadline))

            # Always include doc index corpora (all indexed documentation)
            candidates.extend(RagTool._search_doc_index(query_text, deadline))

            if not candidates:
                return RagResult(
                    ok=True,
                    output=(
                        "rag.search\n"
                        f"query={query_text}\n"
                        f"corpus={normalized_corpus}\n"
                        "matches=0\n\n"
                        "No relevant context found."
                    ),
                )

            ranked = sorted(candidates, key=lambda item: item.score, reverse=True)[:normalized_top_k]
            lines = [
                "rag.search",
                f"query={query_text}",
                f"corpus={normalized_corpus}",
                f"matches={len(ranked)}",
                "",
            ]
            for index, item in enumerate(ranked, start=1):
                lines.append(f"[{index}] {item.source}: {item.label} (score={item.score:.2f})")
                lines.append(item.snippet)
                lines.append("")

            output = "\n".join(lines).strip()
            if len(output) > RagTool._MAX_OUTPUT_CHARS:
                output = output[: RagTool._MAX_OUTPUT_CHARS] + "\n[truncated]"
            return RagResult(ok=True, output=output)
        except Exception as exc:  # noqa: BLE001
            return RagResult(ok=False, output=f"RAG search error: {exc}")

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text into normalized word units."""

        return re.findall(r"[a-z0-9_]+", text.lower())

    @staticmethod
    def _score(query: str, text: str) -> float:
        """Compute a deterministic lexical relevance score."""

        query_tokens = RagTool._tokenize(query)
        if not query_tokens:
            return 0.0
        text_tokens = RagTool._tokenize(text)
        if not text_tokens:
            return 0.0
        text_index: dict[str, int] = {}
        for token in text_tokens:
            text_index[token] = text_index.get(token, 0) + 1
        overlap = sum(min(3, text_index.get(token, 0)) for token in query_tokens)
        phrase_bonus = 2.0 if query.lower() in text.lower() else 0.0
        return float(overlap) + phrase_bonus

    @staticmethod
    def _snippet(query: str, text: str, max_chars: int = 220) -> str:
        """Extract a compact snippet around the first relevant match."""

        compact = re.sub(r"\s+", " ", text).strip()
        if not compact:
            return ""
        lower = compact.lower()
        best_index = -1
        for token in RagTool._tokenize(query):
            index = lower.find(token)
            if index >= 0 and (best_index < 0 or index < best_index):
                best_index = index
        if best_index < 0:
            return compact[:max_chars]
        start = max(0, best_index - (max_chars // 3))
        end = min(len(compact), start + max_chars)
        snippet = compact[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(compact):
            snippet = snippet + "..."
        return snippet

    @staticmethod
    def _search_memory(query: str, memory_db_path: Path, deadline: float) -> list[_Candidate]:
        """Search persisted session memory tables for lexical matches."""

        if not memory_db_path.exists():
            return []

        candidates: list[_Candidate] = []
        try:
            with sqlite3.connect(str(memory_db_path)) as connection:
                rows = connection.execute(
                    """
                    SELECT session_id, role, content
                    FROM memory_entries
                    ORDER BY id DESC
                    LIMIT 160
                    """
                ).fetchall()
                summary_rows = connection.execute(
                    """
                    SELECT session_id, content
                    FROM conversation_summaries
                    ORDER BY updated_at DESC
                    LIMIT 40
                    """
                ).fetchall()
        except Exception:
            return []

        for row in rows:
            if time.monotonic() > deadline:
                break
            session_id, role, content = str(row[0]), str(row[1]), str(row[2])
            score = RagTool._score(query=query, text=content)
            if score <= 0:
                continue
            snippet = RagTool._snippet(query=query, text=content)
            if snippet:
                candidates.append(_Candidate(source="memory", label=f"session={session_id} role={role}", snippet=snippet, score=score))

        for row in summary_rows:
            if time.monotonic() > deadline:
                break
            session_id, content = str(row[0]), str(row[1])
            score = RagTool._score(query=query, text=content)
            if score <= 0:
                continue
            snippet = RagTool._snippet(query=query, text=content)
            if snippet:
                candidates.append(_Candidate(source="summary", label=f"session={session_id}", snippet=snippet, score=score))
        return candidates

    @staticmethod
    def _search_workspace(query: str, workspace_root: Path, deadline: float) -> list[_Candidate]:
        """Search selected text files under workspace root."""

        candidates: list[_Candidate] = []
        try:
            for path in workspace_root.rglob("*"):
                if time.monotonic() > deadline:
                    break
                if path.is_dir():
                    if path.name in RagTool._SKIP_DIRS:
                        continue
                    continue
                if path.suffix.lower() not in RagTool._TEXT_SUFFIXES:
                    continue
                if any(part in RagTool._SKIP_DIRS for part in path.parts):
                    continue
                try:
                    if path.stat().st_size > 1_000_000:
                        continue
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                score = RagTool._score(query=query, text=text)
                if score <= 0:
                    continue
                snippet = RagTool._snippet(query=query, text=text)
                if not snippet:
                    continue
                try:
                    label = str(path.relative_to(workspace_root))
                except Exception:
                    label = str(path)
                candidates.append(_Candidate(source="file", label=label, snippet=snippet, score=score))
        except Exception:
            return candidates
        return candidates

    @staticmethod
    def _search_doc_index(query: str, deadline: float) -> list[_Candidate]:
        """Search all in-memory doc index corpora for lexical matches."""

        candidates: list[_Candidate] = []
        for corpus, chunks in _doc_chunks.items():
            for chunk in chunks:
                if time.monotonic() > deadline:
                    return candidates
                score = RagTool._score(query=query, text=chunk)
                if score <= 0:
                    continue
                snippet = RagTool._snippet(query=query, text=chunk)
                if snippet:
                    candidates.append(
                        _Candidate(source="doc", label=f"corpus={corpus}", snippet=snippet, score=score)
                    )
        return candidates
