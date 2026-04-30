"""Wiki manager for lifecycle operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from e_cli.config import get_app_dir
from e_cli.wiki.page import WikiPage, WikiLink


class WikiManager:
    """Manages wiki lifecycle and operations."""

    def __init__(self, wiki_dir: Path | None = None) -> None:
        """Initialize wiki manager.

        Args:
            wiki_dir: Optional custom wiki directory
        """
        if wiki_dir is None:
            wiki_dir = get_app_dir() / "wiki"

        self.wiki_dir = wiki_dir
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

        # Create default structure
        self._ensure_structure()

    def _ensure_structure(self) -> None:
        """Ensure wiki directory structure exists."""
        subdirs = [
            "concepts",
            "sessions",
            "projects",
            "how-to",
            "reference",
            "troubleshooting",
            "_templates",
            ".meta",
        ]

        for subdir in subdirs:
            (self.wiki_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Create index.md if it doesn't exist
        index_file = self.wiki_dir / "index.md"
        if not index_file.exists():
            index_content = """---
title: Wiki Home
created: 2026-04-30
tags: [index]
---

# E-CLI Knowledge Wiki

Welcome to your personal knowledge base.

## Sections

- [[concepts/index|Concepts]] - Conceptual knowledge
- [[sessions/index|Sessions]] - Session learnings
- [[projects/index|Projects]] - Project documentation
- [[how-to/index|How-To Guides]] - Step-by-step guides
- [[reference/index|Reference]] - Quick references
- [[troubleshooting/index|Troubleshooting]] - Common issues

## Recent Pages

[Auto-generated list of recent pages]
"""
            index_file.write_text(index_content)

    def create_page(
        self,
        name: str,
        content: str = "",
        category: str = "concepts",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WikiPage:
        """Create a new wiki page.

        Args:
            name: Page name (without .md extension)
            content: Page content
            category: Category/subdirectory (e.g., 'concepts', 'how-to')
            tags: Optional tags
            metadata: Optional metadata dict

        Returns:
            Created WikiPage
        """
        # Sanitize name for filename
        safe_name = name.replace(" ", "-").lower()
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "-_")

        page_path = self.wiki_dir / category / f"{safe_name}.md"

        if page_path.exists():
            raise FileExistsError(f"Page already exists: {page_path}")

        page = WikiPage(
            path=page_path,
            title=name,
            content=content,
            metadata=metadata or {},
            tags=tags or [],
        )

        page.save()
        return page

    def get_page(self, name: str, category: str | None = None) -> WikiPage | None:
        """Get a wiki page by name.

        Args:
            name: Page name
            category: Optional category to search in

        Returns:
            WikiPage or None if not found
        """
        # Try direct path first
        if category:
            page_path = self.wiki_dir / category / f"{name}.md"
            if page_path.exists():
                return WikiPage.from_file(page_path)

        # Search all categories
        for md_file in self.wiki_dir.rglob("*.md"):
            if md_file.stem == name or md_file.stem == name.replace(" ", "-").lower():
                return WikiPage.from_file(md_file)

        return None

    def list_pages(self, category: str | None = None) -> list[WikiPage]:
        """List all wiki pages.

        Args:
            category: Optional category filter

        Returns:
            List of WikiPages
        """
        pages = []

        if category:
            search_dir = self.wiki_dir / category
            if not search_dir.exists():
                return []
            pattern = "*.md"
        else:
            search_dir = self.wiki_dir
            pattern = "**/*.md"

        for md_file in search_dir.glob(pattern):
            # Skip template and meta directories
            if ".meta" in md_file.parts or "_templates" in md_file.parts:
                continue

            try:
                page = WikiPage.from_file(md_file)
                pages.append(page)
            except Exception:
                continue

        return pages

    def delete_page(self, name: str, category: str | None = None) -> bool:
        """Delete a wiki page.

        Args:
            name: Page name
            category: Optional category

        Returns:
            True if deleted, False if not found
        """
        page = self.get_page(name, category)
        if page and page.path.exists():
            page.path.unlink()
            return True
        return False

    def update_page(
        self,
        name: str,
        content: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WikiPage | None:
        """Update an existing wiki page.

        Args:
            name: Page name
            content: New content (None to keep existing)
            tags: New tags (None to keep existing)
            metadata: New metadata (None to keep existing)

        Returns:
            Updated WikiPage or None if not found
        """
        page = self.get_page(name)
        if not page:
            return None

        if content is not None:
            page.content = content

        if tags is not None:
            page.tags = tags

        if metadata is not None:
            page.metadata.update(metadata)

        from datetime import datetime
        page.updated_at = datetime.now()
        page.save()

        return page

    def compute_backlinks(self) -> dict[str, list[WikiLink]]:
        """Compute backlinks for all pages.

        Returns:
            Dictionary mapping page names to their backlinks
        """
        backlinks: dict[str, list[WikiLink]] = {}

        pages = self.list_pages()

        for page in pages:
            page_name = page.path.stem

            for link in page.links:
                target = link.target
                if target not in backlinks:
                    backlinks[target] = []

                backlinks[target].append(
                    WikiLink(
                        target=page_name,
                        display=page.title,
                        is_backlink=True,
                    )
                )

        return backlinks

    def get_stats(self) -> dict[str, Any]:
        """Get wiki statistics.

        Returns:
            Statistics dictionary
        """
        pages = self.list_pages()

        total_pages = len(pages)
        total_tags = len(set(tag for page in pages for tag in page.tags))
        total_links = sum(len(page.links) for page in pages)

        categories: dict[str, int] = {}
        for page in pages:
            category = page.path.parent.name
            categories[category] = categories.get(category, 0) + 1

        return {
            "total_pages": total_pages,
            "total_tags": total_tags,
            "total_links": total_links,
            "categories": categories,
        }
