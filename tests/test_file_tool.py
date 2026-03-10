"""Tests for safe workspace-bounded file tool operations."""

from pathlib import Path

from e_cli.tools.file_tool import FileTool


def test_file_tool_write_and_read(tmp_path: Path) -> None:
    """Verifies file write then read works inside workspace root."""

    fileTool = FileTool(workspace_root=tmp_path)
    writeResult = fileTool.write("notes/out.txt", "hello")
    readResult = fileTool.read("notes/out.txt")

    assert writeResult.ok is True
    assert readResult.ok is True
    assert readResult.output == "hello"


def test_file_tool_blocks_path_escape(tmp_path: Path) -> None:
    """Verifies path traversal outside workspace is rejected."""

    fileTool = FileTool(workspace_root=tmp_path)
    escapeResult = fileTool.read("../outside.txt")
    assert escapeResult.ok is False
