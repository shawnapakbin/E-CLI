"""Wiki indexer for fast lookups."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from e_cli.wiki.page import WikiPage


class WikiIndexer:
    """Indexes wiki pages for fast lookup."""

    def __init__(self, wiki_dir: Path) -> None:
        """Initialize wiki indexer.

        Args:
            wiki_dir: Wiki directory path
        """
        self.wiki_dir = wiki_dir
        self.meta_dir = wiki_dir / ".meta"
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.meta_dir / "index.json"

    def build_index(self) -> dict[str, Any]:
        """Build a complete index of all wiki pages.

        Returns:
            Index dictionary
        """
        index: dict[str, Any] = {
            "pages": {},
            "tags": {},
            "links": {},
            "backlinks": {},
        }

        # Index all pages
        for md_file in self.wiki_dir.glob("**/*.md"):
            if ".meta" in md_file.parts or "_templates" in md_file.parts:
                continue

            try:
                page = WikiPage.from_file(md_file)
                page_name = page.path.stem
                relative_path = page.path.relative_to(self.wiki_dir)

                # Add page to index
                index["pages"][page_name] = {
                    "path": str(relative_path),
                    "title": page.title,
                    "tags": page.tags,
                    "links": [link.target for link in page.links],
                    "created": page.created_at.isoformat() if page.created_at else None,
                    "updated": page.updated_at.isoformat() if page.updated_at else None,
                }

                # Index tags
                for tag in page.tags:
                    if tag not in index["tags"]:
                        index["tags"][tag] = []
                    index["tags"][tag].append(page_name)

                # Index links
                for link in page.links:
                    if link.target not in index["links"]:
                        index["links"][link.target] = []
                    index["links"][link.target].append(page_name)

            except Exception:
                continue

        # Compute backlinks
        for target, sources in index["links"].items():
            index["backlinks"][target] = sources

        # Save index
        self.save_index(index)

        return index

    def load_index(self) -> dict[str, Any]:
        """Load the index from disk.

        Returns:
            Index dictionary
        """
        if not self.index_file.exists():
            return self.build_index()

        try:
            with open(self.index_file) as f:
                return cast(dict[str, Any], json.load(f))
        except Exception:
            return self.build_index()

    def save_index(self, index: dict[str, Any]) -> None:
        """Save the index to disk.

        Args:
            index: Index dictionary to save
        """
        with open(self.index_file, "w") as f:
            json.dump(index, f, indent=2)

    def update_page_in_index(self, page_name: str) -> None:
        """Update a single page in the index.

        Args:
            page_name: Name of page to update
        """
        index = self.load_index()

        # Find and re-index the page
        for md_file in self.wiki_dir.glob(f"**/{page_name}.md"):
            if ".meta" in md_file.parts or "_templates" in md_file.parts:
                continue

            try:
                page = WikiPage.from_file(md_file)
                relative_path = page.path.relative_to(self.wiki_dir)

                # Update page entry
                index["pages"][page_name] = {
                    "path": str(relative_path),
                    "title": page.title,
                    "tags": page.tags,
                    "links": [link.target for link in page.links],
                    "created": page.created_at.isoformat() if page.created_at else None,
                    "updated": page.updated_at.isoformat() if page.updated_at else None,
                }

                # Re-index tags
                # Remove old tag associations
                for tag, pages in index["tags"].items():
                    if page_name in pages and tag not in page.tags:
                        pages.remove(page_name)

                # Add new tags
                for tag in page.tags:
                    if tag not in index["tags"]:
                        index["tags"][tag] = []
                    if page_name not in index["tags"][tag]:
                        index["tags"][tag].append(page_name)

                self.save_index(index)
                break

            except Exception:
                continue

    def remove_page_from_index(self, page_name: str) -> None:
        """Remove a page from the index.

        Args:
            page_name: Name of page to remove
        """
        index = self.load_index()

        if page_name in index["pages"]:
            del index["pages"][page_name]

        # Remove from tags
        for tag, pages in index["tags"].items():
            if page_name in pages:
                pages.remove(page_name)

        # Remove from links
        if page_name in index["links"]:
            del index["links"][page_name]

        # Remove from backlinks
        if page_name in index["backlinks"]:
            del index["backlinks"][page_name]

        self.save_index(index)
