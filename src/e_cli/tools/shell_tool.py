"""Shell command execution tool with guardrails and structured output."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(slots=True)
class ShellResult:
    """Structured shell execution result used by the tool router."""

    ok: bool
    output: str
    exitCode: int


class ShellTool:
    """Executes shell commands with timeout and output truncation protections."""

    @staticmethod
    def run(command: str, timeout_seconds: int) -> ShellResult:
        """Execute one shell command and return combined stdout/stderr content."""

        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            output = (stdout + "\n" + stderr).strip()
            if len(output) > 8000:
                output = output[:8000] + "\n[truncated]"
            return ShellResult(ok=completed.returncode == 0, output=output, exitCode=completed.returncode)
        except subprocess.TimeoutExpired:
            return ShellResult(ok=False, output="Command timed out.", exitCode=124)
        except Exception as exc:  # noqa: BLE001
            return ShellResult(ok=False, output=f"Shell execution error: {exc}", exitCode=1)
