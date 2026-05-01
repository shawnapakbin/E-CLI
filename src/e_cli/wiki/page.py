"""Wiki page representation and parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class WikiLink:
    """Represents a wikilink in a page."""

    target: str  # Target page name
    display: str | None = None  # Optional display text
    is_backlink: bool = False  # True if this is a backlink reference


@dataclass
class WikiPage:
    """Represents a wiki page with metadata and content."""

    path: Path
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    links: list[WikiLink] = field(default_factory=list)
    backlinks: list[WikiLink] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @staticmethod
    def _parse_wikilinks(content: str) -> list[WikiLink]:
        """Parse wikilinks from content.

        Args:
            content: Page content

        Returns:
            List of WikiLink objects
        """
        links = []
        link_pattern = r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]"
        for match in re.finditer(link_pattern, content):
            target = match.group(1).strip()
            display = match.group(2).strip() if match.group(2) else None
            links.append(WikiLink(target=target, display=display))
        return links

    @staticmethod
    def _parse_inline_tags(content: str) -> list[str]:
        """Parse inline tags from content.

        Args:
            content: Page content

        Returns:
            List of tag strings
        """
        return re.findall(r"#([\w-]+)", content)

    @staticmethod
    def from_file(file_path: Path) -> WikiPage:
        """Load a wiki page from a markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            WikiPage instance
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Wiki page not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Parse frontmatter if present
        metadata: dict[str, Any] = {}
        tags: list[str] = []
        body_content = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                # Parse YAML frontmatter
                frontmatter = parts[1].strip()
                body_content = parts[2].strip()

                try:
                    import yaml
                    metadata = yaml.safe_load(frontmatter) or {}
                    tags = metadata.get("tags", [])
                    if isinstance(tags, str):
                        tags = [t.strip() for t in tags.split(",")]
                except Exception:
                    pass

        # Extract title from metadata or filename or first h1
        title = metadata.get("title", "")
        if not title:
            # When no frontmatter title, prefer filename over H1
            # This ensures consistent naming based on file structure
            if metadata:
                # Has frontmatter but no title field - try H1
                match = re.search(r"^#\s+(.+)$", body_content, re.MULTILINE)
                if match:
                    title = match.group(1).strip()
                else:
                    title = file_path.stem
            else:
                # No frontmatter at all - use filename
                title = file_path.stem

        # Parse wikilinks using helper method
        links = WikiPage._parse_wikilinks(body_content)

        # Extract inline tags using helper method
        inline_tags = WikiPage._parse_inline_tags(body_content)
        all_tags = list(set(tags + inline_tags))

        # Get file timestamps
        stat = file_path.stat()
        created_at = datetime.fromtimestamp(stat.st_ctime)
        updated_at = datetime.fromtimestamp(stat.st_mtime)

        return WikiPage(
            path=file_path,
            title=title,
            content=body_content,
            metadata=metadata,
            tags=all_tags,
            links=links,
            created_at=created_at,
            updated_at=updated_at,
        )

    def save(self) -> None:
        """Save the wiki page to disk."""
        # Build frontmatter
        frontmatter_data = dict(self.metadata)
        frontmatter_data["title"] = self.title
        if self.tags:
            frontmatter_data["tags"] = self.tags
        if self.created_at:
            frontmatter_data["created"] = self.created_at.isoformat()
        if self.updated_at:
            frontmatter_data["updated"] = self.updated_at.isoformat()

        # Write file
        import yaml
        frontmatter = yaml.dump(frontmatter_data, default_flow_style=False)

        full_content = f"---\n{frontmatter}---\n\n{self.content}"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(full_content, encoding="utf-8")

    def get_summary(self, max_length: int = 200) -> str:
        """Get a short summary of the page.

        Args:
            max_length: Maximum summary length

        Returns:
            Summary text
        """
        # Remove frontmatter, headings, and extra whitespace
        clean_content = re.sub(r"^#+ .+$", "", self.content, flags=re.MULTILINE)
        clean_content = re.sub(r"\[\[.+?\]\]", "", clean_content)
        clean_content = " ".join(clean_content.split())

        if len(clean_content) <= max_length:
            return clean_content

        return clean_content[:max_length].rsplit(" ", 1)[0] + "..."

    def get_related_pages(self) -> list[str]:
        """Get list of related page names from links.

        Returns:
            List of page names
        """
        return [link.target for link in self.links]

    def to_dict(self) -> dict[str, Any]:
        """Convert page to dictionary representation.

        Returns:
            Dictionary containing page data
        """
        return {
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "tags": self.tags,
            "links": [{"target": link.target, "display": link.display} for link in self.links],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
