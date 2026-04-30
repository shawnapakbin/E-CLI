# Vector Embeddings for Wiki Search

This module provides optional semantic search capabilities for E-CLI wiki pages using vector embeddings.

## Overview

While E-CLI's built-in wiki search uses lexical matching (keyword-based), this optional enhancement adds **semantic search** using vector embeddings. This allows finding pages based on meaning, not just exact keyword matches.

## Features

- **Semantic Search**: Find pages by meaning, not just keywords
- **Hybrid Search**: Combine lexical and semantic results for best accuracy
- **Multiple Models**: Support for various sentence transformer models
- **Persistent Cache**: Save/load embeddings to avoid recomputation

## Installation

This feature requires additional dependencies:

```bash
pip install sentence-transformers numpy faiss-cpu
```

Or for GPU support:

```bash
pip install sentence-transformers numpy faiss-gpu
```

## Usage

### Basic Semantic Search

```python
from e_cli.wiki.manager import WikiManager
from e_cli.wiki.embeddings import SemanticWikiSearch

# Initialize
wiki_manager = WikiManager()
semantic_search = SemanticWikiSearch(wiki_manager)

# Build index (one-time or when pages change)
semantic_search.build_index()

# Search semantically
results = semantic_search.search("container orchestration", top_k=5)

for title, score in results:
    print(f"{title}: {score:.3f}")
```

### Hybrid Search (Best Results)

```python
from e_cli.wiki.search import WikiSearch

# Get lexical results
wiki_search = WikiSearch(wiki_manager)
lexical_results = wiki_search.search("docker", category=None, tags=None, limit=10)

# Combine with semantic search
hybrid_results = semantic_search.hybrid_search(
    query="docker",
    lexical_results=[(p.title, score) for p, score in lexical_results],
    semantic_weight=0.5,  # 50% semantic, 50% lexical
    top_k=5
)
```

### Caching Embeddings

```python
from pathlib import Path

# Save embeddings
cache_path = Path("~/.e-cli/wiki/embeddings.json").expanduser()
semantic_search.embeddings_engine.save_embeddings(
    semantic_search._embeddings_cache,
    cache_path
)

# Load embeddings (much faster than recomputing)
cached_embeddings = semantic_search.embeddings_engine.load_embeddings(cache_path)
semantic_search._embeddings_cache = cached_embeddings
```

## How It Works

1. **Text Embedding**: Each wiki page (title + content) is converted to a vector representation using a sentence transformer model
2. **Query Embedding**: Search queries are also converted to vectors
3. **Similarity Search**: Cosine similarity finds pages with vectors closest to the query vector
4. **Hybrid Ranking**: Combines semantic similarity with lexical matching for best results

## Models

Default model: `all-MiniLM-L6-v2` (fast, good quality)

Other options:
- `all-mpnet-base-v2` - Better quality, slower
- `multi-qa-MiniLM-L6-cos-v1` - Optimized for Q&A
- `paraphrase-multilingual-MiniLM-L12-v2` - Multilingual support

Change model:

```python
semantic_search = SemanticWikiSearch(wiki_manager)
semantic_search.embeddings_engine = WikiEmbeddings(model_name="all-mpnet-base-v2")
```

## Performance

- **First-time indexing**: ~1-5 seconds per 100 pages
- **Search**: < 100ms for 1000 pages (with cached embeddings)
- **Storage**: ~2KB per page for embeddings

## Integration with RAG

To integrate with E-CLI's RAG system:

```python
# In rag_tool.py, add semantic wiki search option
def _search_wiki_semantic(query: str, top_k: int) -> list[_Candidate]:
    """Semantic wiki search."""
    from e_cli.wiki.embeddings import SemanticWikiSearch
    from e_cli.wiki.manager import WikiManager

    wiki_manager = WikiManager()
    semantic_search = SemanticWikiSearch(wiki_manager)

    results = semantic_search.search(query, top_k=top_k)

    candidates = []
    for title, score in results:
        page = wiki_manager.get_page(title)
        if page:
            snippet = page.content[:200] + "..."
            candidates.append(_Candidate(
                source="wiki-semantic",
                label=title,
                snippet=snippet,
                score=score * 10.0  # Scale to match lexical scores
            ))

    return candidates
```

## Limitations

- Requires additional dependencies (200MB+ for models)
- First indexing can be slow for large wikis
- Embeddings need updating when pages change
- Not suitable for very large wikis (10,000+ pages) without optimization

## Future Enhancements

- [ ] Vector database integration (FAISS, ChromaDB)
- [ ] Incremental indexing (update only changed pages)
- [ ] Multiple embedding models for different languages
- [ ] Query expansion using LLM
- [ ] Automatic relevance feedback

## See Also

- `wiki/search.py` - Lexical wiki search
- `wiki/manager.py` - Wiki page management
- `tools/rag_tool.py` - RAG search integration
