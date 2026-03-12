"""Git-specific read-only helpers for repository inspection workflows."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class GitResult:
    """Structured git tool result used by the tool router."""

    ok: bool
    output: str


class GitTool:
    """Provides read-only git helpers scoped to the workspace root."""

    def __init__(self, workspaceRoot: Path) -> None:
        """Store canonical workspace root for repository command execution."""

        self.workspaceRoot = workspaceRoot.resolve()

    def diff(self, path: str | None, timeout_seconds: int) -> GitResult:
        """Return the current git diff, optionally restricted to one workspace path."""

        try:
            command = ["git", "-C", str(self.workspaceRoot), "--no-pager", "diff"]
            if path and path.strip():
                command.extend(["--", path.strip()])
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            output = (completed.stdout or completed.stderr or "(no diff)").strip()
            if len(output) > 12000:
                output = output[:12000] + "\n[truncated]"
            return GitResult(ok=completed.returncode == 0, output=output)
        except subprocess.TimeoutExpired:
            return GitResult(ok=False, output="git diff timed out.")
        except Exception as exc:  # noqa: BLE001
            return GitResult(ok=False, output=f"Git diff error: {exc}")