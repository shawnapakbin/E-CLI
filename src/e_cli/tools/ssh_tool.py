"""SSH execution helper with conservative argument validation."""

from __future__ import annotations

from dataclasses import dataclass
import subprocess


@dataclass(slots=True)
class SshResult:
    """Structured SSH execution result used by the tool router."""

    ok: bool
    output: str
    exitCode: int


class SshTool:
    """Executes SSH commands with timeout and output truncation protections."""

    @staticmethod
    def run(
        host: str,
        remote_command: str,
        timeout_seconds: int,
        user: str | None = None,
        port: int | None = None,
        identity_file: str | None = None,
    ) -> SshResult:
        """Execute one remote command over SSH and return combined output."""

        try:
            host_text = host.strip()
            command_text = remote_command.strip()
            if not host_text:
                return SshResult(ok=False, output="Missing SSH host.", exitCode=2)
            if not command_text:
                return SshResult(ok=False, output="Missing SSH command.", exitCode=2)

            target = f"{user}@{host_text}" if user else host_text
            cmd_parts: list[str] = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
            if port and port > 0:
                cmd_parts.extend(["-p", str(port)])
            if identity_file:
                cmd_parts.extend(["-i", identity_file])
            cmd_parts.append(target)
            cmd_parts.append(command_text)

            completed = subprocess.run(
                cmd_parts,
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
            return SshResult(ok=completed.returncode == 0, output=output, exitCode=completed.returncode)
        except subprocess.TimeoutExpired:
            return SshResult(ok=False, output="SSH command timed out.", exitCode=124)
        except Exception as exc:  # noqa: BLE001
            return SshResult(ok=False, output=f"SSH execution error: {exc}", exitCode=1)
