"""File read/write tools bounded to the current working directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class FileResult:
    """Structured file tool result used by the tool router."""

    ok: bool
    output: str


class FileTool:
    """Provides read/write file operations with workspace boundary enforcement."""

    def __init__(self, workspace_root: Path) -> None:
        """Store canonical workspace root for path safety checks."""

        self.workspace_root = workspace_root.resolve()

    def _resolve_safe_path(self, relative_or_absolute_path: str) -> Path:
        """Resolve and validate path to ensure it is inside workspace root."""

        candidate_path = Path(relative_or_absolute_path)
        if not candidate_path.is_absolute():
            candidate_path = self.workspace_root / candidate_path
        resolved = candidate_path.resolve()
        if self.workspace_root not in resolved.parents and resolved != self.workspace_root:
            raise ValueError("Path escapes workspace boundary.")
        return resolved

    def read(self, path: str) -> FileResult:
        """Read UTF-8 file content for model analysis and diagnostics."""

        try:
            target = self._resolve_safe_path(path)
            content = target.read_text(encoding="utf-8")
            if len(content) > 12000:
                content = content[:12000] + "\n[truncated]"
            return FileResult(ok=True, output=content)
        except Exception as exc:  # noqa: BLE001
            return FileResult(ok=False, output=f"File read error: {exc}")

    def write(self, path: str, content: str) -> FileResult:
        """Write UTF-8 content to a file path within workspace root."""

        try:
            target = self._resolve_safe_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return FileResult(ok=True, output=f"Wrote file: {target}")
        except Exception as exc:  # noqa: BLE001
            return FileResult(ok=False, output=f"File write error: {exc}")
