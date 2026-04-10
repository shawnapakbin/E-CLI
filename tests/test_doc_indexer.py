"""Unit tests for DocIndexer — mocking HTTP responses."""

from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from e_cli.docs.indexer import DocIndexer, _MANIFEST_PATH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
  <nav>Skip me</nav>
  <h1>Hello World</h1>
  <p>This is a documentation page about Python and testing.</p>
  <script>alert('skip')</script>
  <footer>Footer text</footer>
</body>
</html>
"""

LARGE_HTML = "<html><body><p>" + ("word " * 600) + "</p></body></html>"


def _make_response(html: str, status: int = 200) -> MagicMock:
    """Build a mock urllib response object."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = html.encode("utf-8")
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url="http://example.com", code=code, msg="Error", hdrs=None, fp=None)


# ---------------------------------------------------------------------------
# _extract_text
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_strips_script_and_nav(self) -> None:
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)
        text = indexer._extract_text(SIMPLE_HTML)
        assert "Hello World" in text
        assert "documentation page" in text
        assert "alert" not in text
        assert "Skip me" not in text
        assert "Footer text" not in text

    def test_empty_html(self) -> None:
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)
        assert indexer._extract_text("") == ""

    def test_plain_text_passthrough(self) -> None:
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)
        text = indexer._extract_text("<p>Hello</p>")
        assert "Hello" in text


# ---------------------------------------------------------------------------
# _chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_short_text_single_chunk(self) -> None:
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)
        chunks = indexer._chunk_text("hello world", max_tokens=512)
        assert len(chunks) == 1
        assert chunks[0] == "hello world"

    def test_empty_text_returns_empty(self) -> None:
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)
        assert indexer._chunk_text("") == []

    def test_long_text_splits_at_word_boundary(self) -> None:
        # 600 words × ~5 chars each = ~3000 chars > 2048 → should produce ≥2 chunks
        text = " ".join(["word"] * 600)
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)
        chunks = indexer._chunk_text(text, max_tokens=512)
        assert len(chunks) >= 2
        # Each chunk must not exceed 2048 chars
        for chunk in chunks:
            assert len(chunk) <= 2048 + 10  # small tolerance for last word

    def test_chunks_cover_all_words(self) -> None:
        text = " ".join([f"w{i}" for i in range(1000)])
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)
        chunks = indexer._chunk_text(text, max_tokens=512)
        rejoined = " ".join(chunks)
        # All words should be present
        for i in range(1000):
            assert f"w{i}" in rejoined


# ---------------------------------------------------------------------------
# index_url — chunk storage
# ---------------------------------------------------------------------------

class TestIndexUrl:
    def test_stores_chunks_on_success(self) -> None:
        stored: dict[str, list[str]] = {}

        def fake_add(corpus: str, chunks: list[str]) -> None:
            stored.setdefault(corpus, []).extend(chunks)

        indexer = DocIndexer(rag_add_chunks_fn=fake_add)

        with patch("urllib.request.urlopen", return_value=_make_response(SIMPLE_HTML)):
            with patch.object(indexer, "_update_manifest"):
                count = indexer.index_url("http://example.com/docs", "test-corpus")

        assert count > 0
        assert "test-corpus" in stored
        assert len(stored["test-corpus"]) == count

    def test_returns_zero_on_http_4xx(self) -> None:
        stored: list[str] = []
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: stored.extend(ch))

        with patch("urllib.request.urlopen", side_effect=_make_http_error(404)):
            with patch.object(indexer, "_update_manifest") as mock_manifest:
                count = indexer.index_url("http://example.com/missing", "test-corpus")

        assert count == 0
        assert stored == []
        # Manifest is updated with 0 chunks even on HTTP error (tracks attempt)
        mock_manifest.assert_called_once_with("http://example.com/missing", "test-corpus", 0)

    def test_returns_zero_on_http_5xx(self) -> None:
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)

        with patch("urllib.request.urlopen", side_effect=_make_http_error(503)):
            count = indexer.index_url("http://example.com/error", "test-corpus")

        assert count == 0

    def test_large_page_produces_multiple_chunks(self) -> None:
        stored: list[str] = []
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: stored.extend(ch))

        with patch("urllib.request.urlopen", return_value=_make_response(LARGE_HTML)):
            with patch.object(indexer, "_update_manifest"):
                count = indexer.index_url("http://example.com/large", "docs")

        assert count >= 2
        assert len(stored) == count


# ---------------------------------------------------------------------------
# Manifest persistence — timestamp recording
# ---------------------------------------------------------------------------

class TestManifestPersistence:
    def test_timestamp_recorded_after_index(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "manifest.json"

        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)

        with patch("e_cli.docs.indexer._MANIFEST_PATH", manifest_file):
            with patch("urllib.request.urlopen", return_value=_make_response(SIMPLE_HTML)):
                indexer.index_url("http://example.com/page", "my-corpus")

        assert manifest_file.exists()
        data = json.loads(manifest_file.read_text())
        assert "http://example.com/page" in data
        entry = data["http://example.com/page"]
        assert "lastIndexedAt" in entry
        assert entry["corpus"] == "my-corpus"
        assert isinstance(entry["chunkCount"], int)

    def test_manifest_updated_on_reindex(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "manifest.json"

        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)

        with patch("e_cli.docs.indexer._MANIFEST_PATH", manifest_file):
            with patch("urllib.request.urlopen", return_value=_make_response(SIMPLE_HTML)):
                indexer.index_url("http://example.com/page", "my-corpus")
                first_ts = json.loads(manifest_file.read_text())["http://example.com/page"]["lastIndexedAt"]

            with patch("urllib.request.urlopen", return_value=_make_response(SIMPLE_HTML)):
                indexer.index_url("http://example.com/page", "my-corpus")
                second_ts = json.loads(manifest_file.read_text())["http://example.com/page"]["lastIndexedAt"]

        # Timestamps may be equal if run within the same second, but entry must exist
        assert second_ts >= first_ts


# ---------------------------------------------------------------------------
# refresh_stale — re-index URLs older than 24 hours
# ---------------------------------------------------------------------------

class TestRefreshStale:
    def _old_manifest(self, url: str, corpus: str) -> dict:
        old_ts = (datetime.now(tz=timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {url: {"lastIndexedAt": old_ts, "corpus": corpus, "chunkCount": 1}}

    def _fresh_manifest(self, url: str, corpus: str) -> dict:
        fresh_ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {url: {"lastIndexedAt": fresh_ts, "corpus": corpus, "chunkCount": 1}}

    def test_reindexes_stale_url(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "manifest.json"
        url = "http://example.com/stale"
        manifest_file.write_text(json.dumps(self._old_manifest(url, "docs")))

        indexed_urls: list[str] = []

        def fake_index_url(u: str, c: str) -> int:
            indexed_urls.append(u)
            return 3

        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)

        with patch("e_cli.docs.indexer._MANIFEST_PATH", manifest_file):
            with patch.object(indexer, "index_url", side_effect=fake_index_url):
                indexer.refresh_stale(max_age_hours=24)

        assert url in indexed_urls

    def test_skips_fresh_url(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "manifest.json"
        url = "http://example.com/fresh"
        manifest_file.write_text(json.dumps(self._fresh_manifest(url, "docs")))

        indexed_urls: list[str] = []

        def fake_index_url(u: str, c: str) -> int:
            indexed_urls.append(u)
            return 3

        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)

        with patch("e_cli.docs.indexer._MANIFEST_PATH", manifest_file):
            with patch.object(indexer, "index_url", side_effect=fake_index_url):
                indexer.refresh_stale(max_age_hours=24)

        assert url not in indexed_urls

    def test_reindexes_url_with_missing_timestamp(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "manifest.json"
        url = "http://example.com/no-ts"
        manifest_file.write_text(json.dumps({url: {"corpus": "docs", "chunkCount": 0}}))

        indexed_urls: list[str] = []

        def fake_index_url(u: str, c: str) -> int:
            indexed_urls.append(u)
            return 2

        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)

        with patch("e_cli.docs.indexer._MANIFEST_PATH", manifest_file):
            with patch.object(indexer, "index_url", side_effect=fake_index_url):
                indexer.refresh_stale(max_age_hours=24)

        assert url in indexed_urls

    def test_empty_manifest_no_error(self, tmp_path: Path) -> None:
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text("{}")

        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None)

        with patch("e_cli.docs.indexer._MANIFEST_PATH", manifest_file):
            # Should not raise
            indexer.refresh_stale(max_age_hours=24)


# ---------------------------------------------------------------------------
# index_skill
# ---------------------------------------------------------------------------

class TestIndexSkill:
    def test_indexes_knowledge_urls(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        manifest = {
            "name": "my-skill",
            "version": "1.0",
            "knowledgeUrls": ["http://example.com/doc1", "http://example.com/doc2"],
        }
        (skill_dir / "manifest.json").write_text(json.dumps(manifest))

        indexed: list[tuple[str, str]] = []

        def fake_index_url(url: str, corpus: str) -> int:
            indexed.append((url, corpus))
            return 2

        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None, skills_dir=str(tmp_path))

        with patch.object(indexer, "index_url", side_effect=fake_index_url):
            total = indexer.index_skill("my-skill")

        assert total == 4
        assert ("http://example.com/doc1", "skill-my-skill") in indexed
        assert ("http://example.com/doc2", "skill-my-skill") in indexed

    def test_returns_zero_for_missing_skill(self, tmp_path: Path) -> None:
        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None, skills_dir=str(tmp_path))
        total = indexer.index_skill("nonexistent-skill")
        assert total == 0

    def test_returns_zero_for_skill_without_knowledge_urls(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "bare-skill"
        skill_dir.mkdir()
        (skill_dir / "manifest.json").write_text(json.dumps({"name": "bare-skill"}))

        indexer = DocIndexer(rag_add_chunks_fn=lambda c, ch: None, skills_dir=str(tmp_path))
        total = indexer.index_skill("bare-skill")
        assert total == 0


# ---------------------------------------------------------------------------
# Error skipping — multiple URLs, one fails
# ---------------------------------------------------------------------------

class TestErrorSkipping:
    def test_continues_after_http_error(self) -> None:
        """HTTP errors on one URL should not prevent indexing of subsequent URLs."""
        stored: list[str] = []

        def fake_add(corpus: str, chunks: list[str]) -> None:
            stored.extend(chunks)

        indexer = DocIndexer(rag_add_chunks_fn=fake_add)

        call_count = 0

        def side_effect(req, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_http_error(404)
            return _make_response(SIMPLE_HTML)

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch.object(indexer, "_update_manifest"):
                count1 = indexer.index_url("http://example.com/missing", "docs")
                count2 = indexer.index_url("http://example.com/ok", "docs")

        assert count1 == 0
        assert count2 > 0
        assert len(stored) == count2
