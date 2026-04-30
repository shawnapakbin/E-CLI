"""Wiki search functionality."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from e_cli.wiki.page import WikiPage


class WikiSearch:
    """Search functionality for wiki pages."""

    def __init__(self, wiki_dir: Path) -> None:
        """Initialize wiki search.

        Args:
            wiki_dir: Wiki directory path
        """
        self.wiki_dir = wiki_dir

    def search(
        self,
        query: str,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[tuple[WikiPage, float]]:
        """Search wiki pages.

        Args:
            query: Search query
            category: Optional category filter
            tags: Optional tag filters
            limit: Maximum results to return

        Returns:
            List of (WikiPage, relevance_score) tuples
        """
        results: list[tuple[WikiPage, float]] = []

        # Get all pages
        if category:
            pattern = f"{category}/**/*.md"
        else:
            pattern = "**/*.md"

        for md_file in self.wiki_dir.glob(pattern):
            if ".meta" in md_file.parts or "_templates" in md_file.parts:
                continue

            try:
                page = WikiPage.from_file(md_file)

                # Apply tag filter
                if tags and not any(tag in page.tags for tag in tags):
                    continue

                # Calculate relevance score
                score = self._calculate_relevance(page, query)

                if score > 0:
                    results.append((page, score))

            except Exception:
                continue

        # Sort by relevance score
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:limit]

    def _calculate_relevance(self, page: WikiPage, query: str) -> float:
        """Calculate relevance score for a page.

        Args:
            page: Wiki page
            query: Search query

        Returns:
            Relevance score (0.0 to 1.0+)
        """
        query_lower = query.lower()
        score = 0.0

        # Title match (highest weight)
        if query_lower in page.title.lower():
            score += 10.0
            if query_lower == page.title.lower():
                score += 10.0  # Exact match bonus

        # Tag match
        for tag in page.tags:
            if query_lower in tag.lower():
                score += 5.0

        # Content match (lower weight, count occurrences)
        content_lower = page.content.lower()
        occurrences = content_lower.count(query_lower)
        score += occurrences * 0.5

        # Metadata match
        for value in page.metadata.values():
            if isinstance(value, str) and query_lower in value.lower():
                score += 2.0

        return score

    def search_by_tags(self, tags: list[str]) -> list[WikiPage]:
        """Search pages by tags.

        Args:
            tags: Tags to search for

        Returns:
            List of matching pages
        """
        results = []

        for md_file in self.wiki_dir.glob("**/*.md"):
            if ".meta" in md_file.parts or "_templates" in md_file.parts:
                continue

            try:
                page = WikiPage.from_file(md_file)

                if any(tag in page.tags for tag in tags):
                    results.append(page)

            except Exception:
                continue

        return results

    def find_orphaned_pages(self) -> list[WikiPage]:
        """Find pages with no incoming or outgoing links.

        Returns:
            List of orphaned pages
        """
        pages = []
        all_linked_targets = set()

        # First pass: collect all link targets
        for md_file in self.wiki_dir.glob("**/*.md"):
            if ".meta" in md_file.parts or "_templates" in md_file.parts:
                continue

            try:
                page = WikiPage.from_file(md_file)
                for link in page.links:
                    all_linked_targets.add(link.target)
            except Exception:
                continue

        # Second pass: find pages with no links
        for md_file in self.wiki_dir.glob("**/*.md"):
            if ".meta" in md_file.parts or "_templates" in md_file.parts:
                continue

            try:
                page = WikiPage.from_file(md_file)
                page_name = page.path.stem

                # Page is orphaned if it has no outgoing links and
                # is not referenced by any other page
                if len(page.links) == 0 and page_name not in all_linked_targets:
                    pages.append(page)

            except Exception:
                continue

        return pages
