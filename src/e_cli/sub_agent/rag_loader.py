"""RAG loader for the sub-agent orchestration prompt.

Indexes orchestration_prompt.txt from the skill directory into the RAG store
under corpus "sub_agent_docs" using DocIndexer.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CORPUS = "sub_agent_docs"
_PROMPT_FILENAME = "orchestration_prompt.txt"


def index_orchestration_prompt(skill_dir: str | Path, memory_db_path: str | Path) -> None:
    """Read orchestration_prompt.txt from *skill_dir* and index it into the RAG store.

    Indexes the content under corpus ``"sub_agent_docs"`` using :class:`DocIndexer`.
    Logs a WARNING and continues (does not raise) if the file is missing or indexing fails.

    Args:
        skill_dir:      Path to the skill directory containing ``orchestration_prompt.txt``.
        memory_db_path: Path to the memory database (passed through for future use;
                        currently the DocIndexer uses the global in-memory RAG store).
    """
    skill_dir = Path(skill_dir)
    prompt_path = skill_dir / _PROMPT_FILENAME

    if not prompt_path.exists():
        logger.warning(
            "orchestration_prompt.txt not found at %s — skipping RAG indexing", prompt_path
        )
        return

    try:
        content = prompt_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to read %s: %s — skipping RAG indexing", prompt_path, exc)
        return

    if not content.strip():
        logger.warning("orchestration_prompt.txt is empty at %s — skipping RAG indexing", prompt_path)
        return

    try:
        from e_cli.docs.indexer import DocIndexer

        indexer = DocIndexer()
        chunks = indexer._chunk_text(content)
        if chunks:
            from e_cli.tools.rag_tool import RagTool

            RagTool.add_chunks(_CORPUS, chunks)
            logger.info(
                "Indexed %d chunk(s) from %s into RAG corpus '%s'",
                len(chunks),
                prompt_path,
                _CORPUS,
            )
        else:
            logger.warning(
                "No chunks produced from %s — skipping RAG indexing", prompt_path
            )
    except Exception as exc:
        logger.warning("Failed to index orchestration_prompt.txt into RAG store: %s", exc)
