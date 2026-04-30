"""Unit tests for wiki page module."""

import pytest
from pathlib import Path
from e_cli.wiki.page import WikiPage, WikiLink


class TestWikiLink:
    """Test WikiLink dataclass."""

    def test_simple_wikilink(self):
        """Test creating a simple wikilink."""
        link = WikiLink(target="Docker Basics", display=None)
        assert link.target == "Docker Basics"
        assert link.display is None

    def test_wikilink_with_display(self):
        """Test wikilink with custom display text."""
        link = WikiLink(target="Docker Basics", display="Docker")
        assert link.target == "Docker Basics"
        assert link.display == "Docker"


class TestWikiPage:
    """Test WikiPage class."""

    def test_parse_wikilinks_simple(self):
        """Test parsing simple wikilinks."""
        content = "See [[Docker Basics]] and [[Kubernetes]]"
        links = WikiPage._parse_wikilinks(content)

        assert len(links) == 2
        assert links[0].target == "Docker Basics"
        assert links[0].display is None
        assert links[1].target == "Kubernetes"

    def test_parse_wikilinks_with_display(self):
        """Test parsing wikilinks with display text."""
        content = "Check [[Docker Basics|Docker]] documentation"
        links = WikiPage._parse_wikilinks(content)

        assert len(links) == 1
        assert links[0].target == "Docker Basics"
        assert links[0].display == "Docker"

    def test_parse_inline_tags(self):
        """Test parsing inline tags."""
        content = "This is about #docker and #containers"
        tags = WikiPage._parse_inline_tags(content)

        assert len(tags) == 2
        assert "docker" in tags
        assert "containers" in tags

    def test_page_from_file(self, tmp_path):
        """Test creating page from file."""
        # Create test file
        test_file = tmp_path / "test.md"
        content = """---
title: Test Page
tags: [test, example]
category: testing
---

# Test Page

This is a test page with [[Another Page]].

It has #inline #tags too.
"""
        test_file.write_text(content)

        # Parse page
        page = WikiPage.from_file(test_file)

        assert page.title == "Test Page"
        assert "test" in page.tags
        assert "example" in page.tags
        assert "inline" in page.tags
        assert "tags" in page.tags
        assert page.metadata["category"] == "testing"
        assert len(page.links) == 1
        assert page.links[0].target == "Another Page"

    def test_page_without_frontmatter(self, tmp_path):
        """Test creating page without YAML frontmatter."""
        test_file = tmp_path / "simple.md"
        content = """# Simple Page

Just content with [[Link]].
"""
        test_file.write_text(content)

        page = WikiPage.from_file(test_file)

        # Should use filename as title
        assert page.title == "simple"
        assert len(page.links) == 1
        assert page.links[0].target == "Link"

    def test_page_to_dict(self, tmp_path):
        """Test converting page to dictionary."""
        test_file = tmp_path / "test.md"
        content = """---
title: Dict Test
---

Content
"""
        test_file.write_text(content)

        page = WikiPage.from_file(test_file)
        page_dict = page.to_dict()

        assert page_dict["title"] == "Dict Test"
        assert "content" in page_dict
        assert "metadata" in page_dict
        assert "tags" in page_dict
        assert "links" in page_dict

    def test_multiple_wikilinks_same_line(self):
        """Test parsing multiple wikilinks on same line."""
        content = "Topics: [[Python]], [[JavaScript]], and [[Go]]"
        links = WikiPage._parse_wikilinks(content)

        assert len(links) == 3
        targets = [link.target for link in links]
        assert "Python" in targets
        assert "JavaScript" in targets
        assert "Go" in targets

    def test_nested_tags_in_frontmatter_and_inline(self, tmp_path):
        """Test combining frontmatter and inline tags."""
        test_file = tmp_path / "tags.md"
        content = """---
title: Tag Test
tags: [yaml, frontmatter]
---

Content with #inline #markdown tags.
"""
        test_file.write_text(content)

        page = WikiPage.from_file(test_file)

        # Should have both frontmatter and inline tags
        assert "yaml" in page.tags
        assert "frontmatter" in page.tags
        assert "inline" in page.tags
        assert "markdown" in page.tags
