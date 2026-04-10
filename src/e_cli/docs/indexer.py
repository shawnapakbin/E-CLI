"""Documentation indexer: fetches, parses, chunks, and stores docs into the RAG store."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 1 token ≈ 4 chars → 512 tokens ≈ 2048 chars
_CHARS_PER_CHUNK = 2048

# Manifest location
_MANIFEST_PATH = Path("~/.e-cli/doc_index/manifest.json").expanduser()

# Tags whose content we skip entirely during text extraction
_SKIP_TAGS = frozenset(
    {"script", "style", "head", "noscript", "nav", "footer", "header", "aside"}
)


class _TextExtractor(HTMLParser):
    """HTMLParser subclass that strips tags and collects visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


class DocIndexer:
    """Fetches, parses, chunks, and stores documentation pages into the RAG store."""

    def __init__(self, rag_add_chunks_fn: Any = None, skills_dir: str = "~/.e-cli/skills") -> None:
        """
        Args:
            rag_add_chunks_fn: Callable(corpus: str, chunks: list[str]) -> None.
                               Defaults to RagTool.add_chunks if not provided.
            skills_dir: Path to the skills directory for index_skill lookups.
        """
        if rag_add_chunks_fn is None:
            from e_cli.tools.rag_tool import RagTool
            rag_add_chunks_fn = RagTool.add_chunks
        self._add_chunks = rag_add_chunks_fn
        self._skills_dir = Path(skills_dir).expanduser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_url(self, url: str, corpus: str) -> int:
        """Fetch *url*, extract text, chunk it, store in *corpus*, update manifest.

        Returns the number of chunks stored, or 0 on HTTP error.
        """
        html = self._fetch(url)
        if html is None:
            self._update_manifest(url, corpus, 0)
            return 0

        text = self._extract_text(html)
        chunks = self._chunk_text(text)
        if chunks:
            self._add_chunks(corpus, chunks)

        self._update_manifest(url, corpus, len(chunks))
        return len(chunks)

    def index_skill(self, skill_name: str) -> int:
        """Index all knowledgeUrls declared in the named skill's manifest.json.

        Returns total chunks stored across all URLs.
        """
        manifest_path = self._skills_dir / skill_name / "manifest.json"
        if not manifest_path.exists():
            logger.warning("Skill manifest not found: %s", manifest_path)
            return 0

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read skill manifest %s: %s", manifest_path, exc)
            return 0

        knowledge_urls: list[str] = manifest_data.get("knowledgeUrls", [])
        if not knowledge_urls:
            logger.info("Skill '%s' has no knowledgeUrls.", skill_name)
            return 0

        corpus = f"skill-{skill_name}"
        total = 0
        for url in knowledge_urls:
            total += self.index_url(url, corpus)
        return total

    def refresh_stale(self, max_age_hours: int = 24) -> None:
        """Re-index all manifest entries whose lastIndexedAt is older than *max_age_hours*."""
        manifest = self._load_manifest()
        now = datetime.now(tz=timezone.utc)

        for url, entry in list(manifest.items()):
            last_indexed_str = entry.get("lastIndexedAt", "")
            if not last_indexed_str:
                # Never indexed properly — re-index
                self.index_url(url, entry.get("corpus", "docs"))
                continue

            try:
                last_indexed = datetime.fromisoformat(last_indexed_str.replace("Z", "+00:00"))
            except ValueError:
                self.index_url(url, entry.get("corpus", "docs"))
                continue

            age_hours = (now - last_indexed).total_seconds() / 3600
            if age_hours >= max_age_hours:
                logger.info("Re-indexing stale URL (%.1fh old): %s", age_hours, url)
                self.index_url(url, entry.get("corpus", "docs"))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_text(self, html: str) -> str:
        """Strip HTML tags and return visible text content."""
        extractor = _TextExtractor()
        try:
            extractor.feed(html)
        except Exception as exc:
            logger.warning("HTML parse error: %s", exc)
        text = extractor.get_text()
        # Collapse excessive whitespace
        return re.sub(r"\s{3,}", "  ", text).strip()

    def _chunk_text(self, text: str, max_tokens: int = 512) -> list[str]:
        """Split *text* into chunks of at most *max_tokens* tokens (1 token ≈ 4 chars)."""
        max_chars = max_tokens * 4
        if not text:
            return []

        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        current_words: list[str] = []
        current_len = 0

        for word in words:
            word_len = len(word) + 1  # +1 for the space
            if current_words and current_len + word_len > max_chars:
                chunks.append(" ".join(current_words))
                current_words = [word]
                current_len = len(word)
            else:
                current_words.append(word)
                current_len += word_len

        if current_words:
            chunks.append(" ".join(current_words))

        return chunks

    def _fetch(self, url: str) -> str | None:
        """Fetch *url* via urllib. Returns HTML string or None on HTTP error."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "e-cli-doc-indexer/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                charset = "utf-8"
                content_type = response.headers.get("Content-Type", "")
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].strip().split(";")[0].strip()
                return response.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            logger.warning("HTTP %s fetching %s — skipping.", exc.code, url)
            return None
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s — skipping.", url, exc)
            return None

    # ------------------------------------------------------------------
    # Manifest persistence
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        """Load the manifest from disk, returning an empty dict if absent."""
        if not _MANIFEST_PATH.exists():
            return {}
        try:
            return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load doc manifest: %s", exc)
            return {}

    def _save_manifest(self, manifest: dict[str, dict[str, Any]]) -> None:
        """Persist the manifest to disk."""
        try:
            _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
            _MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save doc manifest: %s", exc)

    def _update_manifest(self, url: str, corpus: str, chunk_count: int) -> None:
        """Update the manifest entry for *url* with current timestamp and chunk count."""
        manifest = self._load_manifest()
        manifest[url] = {
            "lastIndexedAt": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "corpus": corpus,
            "chunkCount": chunk_count,
        }
        self._save_manifest(manifest)
