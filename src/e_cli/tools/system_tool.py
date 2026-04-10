"""Cross-platform system information and management tool."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from typing import Any

import psutil

from e_cli.agent.protocol import ToolResult

_log = logging.getLogger(__name__)

_SUBPROCESS_TIMEOUT = 10
_PKG_TIMEOUT = 30


def _os_name() -> str:
    """Return normalised OS name: 'Windows', 'Linux', or 'Darwin'."""
    return platform.system()


class SystemTool:
    """Provides cross-platform system information and management actions."""

    def execute(self, action: str, **kwargs: Any) -> ToolResult:
        """Dispatch *action* to the matching handler method."""
        handler = getattr(self, f"_action_{action}", None)
        if handler is None:
            return ToolResult(ok=False, output=f"Unknown system action: {action!r}")
        try:
            return handler(**kwargs)
        except Exception as exc:
            _log.exception("SystemTool action %r raised an unexpected error", action)
            return ToolResult(ok=False, output=f"System error during {action!r}: {exc}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _action_get_system_info(self, **_: Any) -> ToolResult:
        """Return OS name, version, architecture, CPU count, RAM, and disk info."""
        os_name = _os_name()
        os_version = platform.version()
        architecture = platform.machine()
        cpu_count = psutil.cpu_count(logical=True)
        vm = psutil.virtual_memory()
        total_ram_mb = vm.total // (1024 * 1024)
        disk = shutil.disk_usage("/")
        available_disk_mb = disk.free // (1024 * 1024)

        output = (
            f"os={os_name}\n"
            f"version={os_version}\n"
            f"architecture={architecture}\n"
            f"cpu_count={cpu_count}\n"
            f"total_ram_mb={total_ram_mb}\n"
            f"available_disk_mb={available_disk_mb}"
        )
        return ToolResult(ok=True, output=output)

    def _action_list_processes(self, **_: Any) -> ToolResult:
        """Return a list of running processes with PID, name, CPU%, and memory RSS."""
        lines: list[str] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = proc.info  # type: ignore[attr-defined]
                pid = info.get("pid", "")
                name = info.get("name", "")
                cpu = info.get("cpu_percent", 0.0) or 0.0
                mem_info = info.get("memory_info")
                rss_mb = (mem_info.rss // (1024 * 1024)) if mem_info else 0
                lines.append(f"pid={pid} name={name!r} cpu_percent={cpu} memory_rss_mb={rss_mb}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return ToolResult(ok=True, output="\n".join(lines))

    def _action_kill_process(self, pid: int | None = None, **_: Any) -> ToolResult:
        """Kill a process by PID."""
        if pid is None:
            return ToolResult(ok=False, output="Missing required kwarg: pid")
        try:
            psutil.Process(pid).kill()
            return ToolResult(ok=True, output=f"Process {pid} killed.")
        except psutil.NoSuchProcess:
            return ToolResult(ok=False, output=f"No such process: {pid}")
        except psutil.AccessDenied:
            return ToolResult(ok=False, output=f"Access denied when killing process {pid}")

    def _action_get_logs(self, lines: int = 100, **_: Any) -> ToolResult:
        """Retrieve system logs. Configurable line limit (default 100)."""
        os_name = _os_name()
        if os_name == "Linux":
            result = subprocess.run(
                ["journalctl", "-n", str(lines)],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0:
                return ToolResult(ok=False, output=result.stderr or "journalctl failed")
            return ToolResult(ok=True, output=result.stdout)
        elif os_name == "Darwin":
            log_proc = subprocess.run(
                ["log", "show", "--last", "1h", "--style", "compact"],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            output_lines = log_proc.stdout.splitlines()[:lines]
            return ToolResult(ok=True, output="\n".join(output_lines))
        elif os_name == "Windows":
            result = subprocess.run(
                ["wevtutil", "qe", "Application", f"/c:{lines}", "/f:text"],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0:
                return ToolResult(ok=False, output=result.stderr or "wevtutil failed")
            return ToolResult(ok=True, output=result.stdout)
        else:
            return ToolResult(ok=False, output=f"get_logs is not supported on {os_name}")

    def _action_list_packages(self, **_: Any) -> ToolResult:
        """List installed packages using the OS package manager."""
        os_name = _os_name()
        cmd = _detect_package_manager_list_cmd(os_name)
        if cmd is None:
            return ToolResult(
                ok=False,
                output="No supported package manager found. Expected: apt-get (Debian/Ubuntu), dnf (Fedora/RHEL), brew (macOS), winget (Windows)",
            )
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=_PKG_TIMEOUT)
        if result.returncode != 0:
            return ToolResult(ok=False, output=result.stderr or f"{cmd[0]} list failed")
        return ToolResult(ok=True, output=result.stdout)

    def _action_install_package(self, package: str | None = None, **_: Any) -> ToolResult:
        """Install a package using the OS package manager."""
        if not package:
            return ToolResult(ok=False, output="Missing required kwarg: package")
        os_name = _os_name()
        cmd = _detect_package_manager_install_cmd(os_name, package)
        if cmd is None:
            return ToolResult(
                ok=False,
                output="No supported package manager found. Expected: apt-get (Debian/Ubuntu), dnf (Fedora/RHEL), brew (macOS), winget (Windows)",
            )
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=_PKG_TIMEOUT)
        if result.returncode != 0:
            return ToolResult(ok=False, output=result.stderr or f"Install of {package!r} failed")
        return ToolResult(ok=True, output=result.stdout or f"Package {package!r} installed.")

    def _action_uninstall_package(self, package: str | None = None, **_: Any) -> ToolResult:
        """Uninstall a package using the OS package manager."""
        if not package:
            return ToolResult(ok=False, output="Missing required kwarg: package")
        os_name = _os_name()
        cmd = _detect_package_manager_uninstall_cmd(os_name, package)
        if cmd is None:
            return ToolResult(
                ok=False,
                output="No supported package manager found. Expected: apt-get (Debian/Ubuntu), dnf (Fedora/RHEL), brew (macOS), winget (Windows)",
            )
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=_PKG_TIMEOUT)
        if result.returncode != 0:
            return ToolResult(ok=False, output=result.stderr or f"Uninstall of {package!r} failed")
        return ToolResult(ok=True, output=result.stdout or f"Package {package!r} uninstalled.")

    def _action_list_drivers(self, **_: Any) -> ToolResult:
        """List system drivers. Linux: lsmod, Windows: driverquery, macOS: unsupported."""
        os_name = _os_name()
        if os_name == "Linux":
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0:
                return ToolResult(ok=False, output=result.stderr or "lsmod failed")
            return ToolResult(ok=True, output=result.stdout)
        elif os_name == "Windows":
            result = subprocess.run(
                ["driverquery"],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0:
                return ToolResult(ok=False, output=result.stderr or "driverquery failed")
            return ToolResult(ok=True, output=result.stdout)
        else:
            return ToolResult(ok=False, output="list_drivers is not supported on macOS")


# ------------------------------------------------------------------
# Package manager helpers
# ------------------------------------------------------------------

def _detect_package_manager_list_cmd(os_name: str) -> list[str] | None:
    if os_name == "Linux":
        if shutil.which("apt-get"):
            return ["apt-get", "list", "--installed"]
        if shutil.which("dnf"):
            return ["dnf", "list", "installed"]
        return None
    elif os_name == "Darwin":
        if shutil.which("brew"):
            return ["brew", "list"]
        return None
    elif os_name == "Windows":
        if shutil.which("winget"):
            return ["winget", "list"]
        return None
    return None


def _detect_package_manager_install_cmd(os_name: str, package: str) -> list[str] | None:
    if os_name == "Linux":
        if shutil.which("apt-get"):
            return ["apt-get", "install", "-y", package]
        if shutil.which("dnf"):
            return ["dnf", "install", "-y", package]
        return None
    elif os_name == "Darwin":
        if shutil.which("brew"):
            return ["brew", "install", package]
        return None
    elif os_name == "Windows":
        if shutil.which("winget"):
            return ["winget", "install", package]
        return None
    return None


def _detect_package_manager_uninstall_cmd(os_name: str, package: str) -> list[str] | None:
    if os_name == "Linux":
        if shutil.which("apt-get"):
            return ["apt-get", "remove", "-y", package]
        if shutil.which("dnf"):
            return ["dnf", "remove", "-y", package]
        return None
    elif os_name == "Darwin":
        if shutil.which("brew"):
            return ["brew", "uninstall", package]
        return None
    elif os_name == "Windows":
        if shutil.which("winget"):
            return ["winget", "uninstall", package]
        return None
    return None
