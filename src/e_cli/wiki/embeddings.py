"""Vector embeddings for semantic wiki search (optional enhancement)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]


@dataclass
class EmbeddingResult:
    """Result from embedding computation."""

    vector: list[float]
    model: str
    dimensions: int


class WikiEmbeddings:
    """
    Optional enhancement for semantic wiki search using vector embeddings.

    This module provides semantic search capabilities for wiki pages using
    sentence transformers or other embedding models.

    Note: This is an optional feature that requires additional dependencies:
    - sentence-transformers
    - numpy
    - faiss-cpu or chromadb

    Install with: pip install sentence-transformers numpy faiss-cpu
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """
        Initialize wiki embeddings.

        Args:
            model_name: Name of the sentence transformer model to use
        """
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._index = None

    def _ensure_model_loaded(self) -> None:
        """Lazy load the embedding model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

    def embed_text(self, text: str) -> EmbeddingResult:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResult with vector and metadata
        """
        self._ensure_model_loaded()
        assert self._model is not None

        # Generate embedding
        embedding = self._model.encode(text, convert_to_numpy=True)

        return EmbeddingResult(
            vector=embedding.tolist(),
            model=self.model_name,
            dimensions=len(embedding),
        )

    def embed_pages(self, pages: list[Any]) -> dict[str, EmbeddingResult]:
        """
        Generate embeddings for multiple wiki pages.

        Args:
            pages: List of WikiPage objects

        Returns:
            Dictionary mapping page titles to embeddings
        """
        self._ensure_model_loaded()

        embeddings = {}
        for page in pages:
            # Combine title and content for better semantic representation
            text = f"{page.title}\n\n{page.content}"
            embeddings[page.title] = self.embed_text(text)

        return embeddings

    def semantic_search(
        self,
        query: str,
        page_embeddings: dict[str, EmbeddingResult],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """
        Perform semantic search over embedded pages.

        Args:
            query: Search query
            page_embeddings: Pre-computed page embeddings
            top_k: Number of results to return

        Returns:
            List of (page_title, similarity_score) tuples
        """
        self._ensure_model_loaded()

        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError:
            raise ImportError(
                "numpy not installed. Install with: pip install numpy"
            )

        # Embed the query
        query_embedding = self.embed_text(query)
        query_vector = np.array(query_embedding.vector)

        # Compute similarities
        similarities = []
        for title, page_emb in page_embeddings.items():
            page_vector = np.array(page_emb.vector)

            # Cosine similarity
            similarity = np.dot(query_vector, page_vector) / (
                np.linalg.norm(query_vector) * np.linalg.norm(page_vector)
            )
            similarities.append((title, float(similarity)))

        # Sort by similarity and return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def save_embeddings(self, embeddings: dict[str, EmbeddingResult], path: Path) -> None:
        """
        Save embeddings to disk.

        Args:
            embeddings: Dictionary of embeddings to save
            path: Path to save embeddings
        """
        import json

        data = {
            title: {
                "vector": emb.vector,
                "model": emb.model,
                "dimensions": emb.dimensions,
            }
            for title, emb in embeddings.items()
        }

        with open(path, "w") as f:
            json.dump(data, f)

    def load_embeddings(self, path: Path) -> dict[str, EmbeddingResult]:
        """
        Load embeddings from disk.

        Args:
            path: Path to load embeddings from

        Returns:
            Dictionary of loaded embeddings
        """
        import json

        with open(path) as f:
            data = json.load(f)

        embeddings = {}
        for title, emb_data in data.items():
            embeddings[title] = EmbeddingResult(
                vector=emb_data["vector"],
                model=emb_data["model"],
                dimensions=emb_data["dimensions"],
            )

        return embeddings


# Example usage in wiki search enhancement
class SemanticWikiSearch:
    """Enhanced wiki search with semantic capabilities."""

    def __init__(self, wiki_manager: Any) -> None:
        """
        Initialize semantic search.

        Args:
            wiki_manager: WikiManager instance
        """
        self.wiki_manager = wiki_manager
        self.embeddings_engine = WikiEmbeddings()
        self._embeddings_cache: dict[str, EmbeddingResult] = {}

    def build_index(self) -> None:
        """Build semantic index for all wiki pages."""
        pages = self.wiki_manager.list_pages()
        self._embeddings_cache = self.embeddings_engine.embed_pages(pages)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """
        Search wiki pages semantically.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of (page_title, relevance_score) tuples
        """
        if not self._embeddings_cache:
            self.build_index()

        return self.embeddings_engine.semantic_search(
            query, self._embeddings_cache, top_k
        )

    def hybrid_search(
        self,
        query: str,
        lexical_results: list[tuple[str, float]],
        semantic_weight: float = 0.5,
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """
        Combine lexical and semantic search for best results.

        Args:
            query: Search query
            lexical_results: Results from keyword search
            semantic_weight: Weight for semantic scores (0-1)
            top_k: Number of results

        Returns:
            Combined and re-ranked results
        """
        semantic_results = self.search(query, top_k=20)

        # Normalize and combine scores
        lexical_dict = {title: score for title, score in lexical_results}
        semantic_dict = {title: score for title, score in semantic_results}

        all_titles = set(lexical_dict.keys()) | set(semantic_dict.keys())

        combined = []
        for title in all_titles:
            lex_score = lexical_dict.get(title, 0.0)
            sem_score = semantic_dict.get(title, 0.0)

            # Weighted combination
            combined_score = (
                (1 - semantic_weight) * lex_score +
                semantic_weight * sem_score
            )
            combined.append((title, combined_score))

        # Sort and return top k
        combined.sort(key=lambda x: x[1], reverse=True)
        return combined[:top_k]
