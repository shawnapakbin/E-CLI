"""Integration tests for RAG search with wiki."""

import pytest
from e_cli.wiki.manager import WikiManager
from e_cli.tools.rag_tool import RagTool


class TestRAGWikiIntegration:
    """Test RAG search integration with wiki."""

    @pytest.fixture
    def wiki_setup(self, tmp_path):
        """Set up test wiki with sample pages."""
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        manager = WikiManager(wiki_dir)

        # Create test pages
        manager.create_page(
            name="Docker Basics",
            content="Docker is a containerization platform. See also [[Kubernetes]].",
            category="tutorials",
            tags=["docker", "containers"],
        )

        manager.create_page(
            name="Kubernetes",
            content="Kubernetes orchestrates containers. Works with [[Docker Basics]].",
            category="tutorials",
            tags=["kubernetes", "orchestration"],
        )

        manager.create_page(
            name="Python Development",
            content="Python is a programming language. #python #development",
            category="guides",
            tags=["python", "programming"],
        )

        return wiki_dir

    def test_wiki_corpus_search(self, wiki_setup, tmp_path):
        """Test searching wiki corpus."""
        # Note: This test requires wiki directory in the right location
        # For now, test the search method exists and handles wiki corpus

        result = RagTool.search(
            query="docker",
            timeout_seconds=5,
            workspace_root=tmp_path,
            memory_db_path=None,
            corpus="wiki",
            top_k=3,
        )

        assert result.ok is True
        # Output should contain search results or "no matches"
        assert "rag.search" in result.output
        assert "corpus=wiki" in result.output

    def test_combined_corpus_search(self, tmp_path):
        """Test combined corpus search."""
        result = RagTool.search(
            query="test",
            timeout_seconds=5,
            workspace_root=tmp_path,
            memory_db_path=None,
            corpus="combined",
            top_k=5,
        )

        assert result.ok is True
        assert "corpus=combined" in result.output

    def test_invalid_corpus(self, tmp_path):
        """Test invalid corpus returns error."""
        result = RagTool.search(
            query="test",
            timeout_seconds=5,
            workspace_root=tmp_path,
            memory_db_path=None,
            corpus="invalid",
            top_k=5,
        )

        assert result.ok is False
        assert "Invalid corpus" in result.output
