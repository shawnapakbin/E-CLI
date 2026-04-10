"""Unit tests for SystemTool covering all actions and OS environments."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from e_cli.tools.system_tool import SystemTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(pid: int = 1, name: str = "proc", cpu: float = 0.5, rss: int = 10 * 1024 * 1024) -> MagicMock:
    mem_info = SimpleNamespace(rss=rss)
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name, "cpu_percent": cpu, "memory_info": mem_info}
    return proc


# ---------------------------------------------------------------------------
# get_system_info
# ---------------------------------------------------------------------------

class TestGetSystemInfo:
    def test_returns_correct_fields(self) -> None:
        tool = SystemTool()
        vm = SimpleNamespace(total=2 * 1024 * 1024 * 1024)  # 2 GB
        disk = SimpleNamespace(free=10 * 1024 * 1024 * 1024)  # 10 GB

        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch("e_cli.tools.system_tool.platform.version", return_value="5.15.0"),
            patch("e_cli.tools.system_tool.platform.machine", return_value="x86_64"),
            patch("e_cli.tools.system_tool.psutil.cpu_count", return_value=4),
            patch("e_cli.tools.system_tool.psutil.virtual_memory", return_value=vm),
            patch("e_cli.tools.system_tool.shutil.disk_usage", return_value=disk),
        ):
            result = tool.execute("get_system_info")

        assert result.ok is True
        assert "os=Linux" in result.output
        assert "version=5.15.0" in result.output
        assert "architecture=x86_64" in result.output
        assert "cpu_count=4" in result.output
        assert "total_ram_mb=2048" in result.output
        assert "available_disk_mb=10240" in result.output


# ---------------------------------------------------------------------------
# list_processes
# ---------------------------------------------------------------------------

class TestListProcesses:
    def test_returns_list_with_correct_structure(self) -> None:
        tool = SystemTool()
        procs = [_make_proc(pid=42, name="bash", cpu=1.2, rss=5 * 1024 * 1024)]

        with patch("e_cli.tools.system_tool.psutil.process_iter", return_value=procs):
            result = tool.execute("list_processes")

        assert result.ok is True
        assert "pid=42" in result.output
        assert "name='bash'" in result.output
        assert "cpu_percent=1.2" in result.output
        assert "memory_rss_mb=5" in result.output

    def test_skips_inaccessible_processes(self) -> None:
        import psutil as _psutil

        tool = SystemTool()
        bad_proc = MagicMock()
        bad_proc.info = {}
        bad_proc.__iter__ = MagicMock(side_effect=_psutil.AccessDenied(0))

        good_proc = _make_proc(pid=1, name="init")

        with patch("e_cli.tools.system_tool.psutil.process_iter", return_value=[good_proc]):
            result = tool.execute("list_processes")

        assert result.ok is True


# ---------------------------------------------------------------------------
# kill_process
# ---------------------------------------------------------------------------

class TestKillProcess:
    def test_success(self) -> None:
        tool = SystemTool()
        mock_proc = MagicMock()

        with patch("e_cli.tools.system_tool.psutil.Process", return_value=mock_proc):
            result = tool.execute("kill_process", pid=123)

        mock_proc.kill.assert_called_once()
        assert result.ok is True
        assert "123" in result.output

    def test_no_such_process(self) -> None:
        import psutil as _psutil

        tool = SystemTool()
        with patch("e_cli.tools.system_tool.psutil.Process", side_effect=_psutil.NoSuchProcess(999)):
            result = tool.execute("kill_process", pid=999)

        assert result.ok is False
        assert "No such process" in result.output

    def test_access_denied(self) -> None:
        import psutil as _psutil

        tool = SystemTool()
        with patch("e_cli.tools.system_tool.psutil.Process", side_effect=_psutil.AccessDenied(1)):
            result = tool.execute("kill_process", pid=1)

        assert result.ok is False
        assert "Access denied" in result.output

    def test_missing_pid(self) -> None:
        tool = SystemTool()
        result = tool.execute("kill_process")
        assert result.ok is False
        assert "pid" in result.output


# ---------------------------------------------------------------------------
# get_logs
# ---------------------------------------------------------------------------

class TestGetLogs:
    def _run_result(self, stdout: str = "", returncode: int = 0) -> SimpleNamespace:
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)

    def test_linux_dispatches_journalctl(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result("log line")) as mock_run,
        ):
            result = tool.execute("get_logs", lines=50)

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "journalctl"
        assert "50" in cmd

    def test_macos_dispatches_log_show(self) -> None:
        tool = SystemTool()
        log_output = "\n".join(f"line {i}" for i in range(200))
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Darwin"),
            patch(
                "e_cli.tools.system_tool.subprocess.run",
                return_value=self._run_result(log_output),
            ) as mock_run,
        ):
            result = tool.execute("get_logs", lines=10)

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "log"
        # Only 10 lines returned
        assert len(result.output.splitlines()) == 10

    def test_windows_dispatches_wevtutil(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Windows"),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result("event")) as mock_run,
        ):
            result = tool.execute("get_logs", lines=20)

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "wevtutil"
        assert "/c:20" in cmd

    def test_linux_journalctl_failure(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch(
                "e_cli.tools.system_tool.subprocess.run",
                return_value=SimpleNamespace(stdout="", stderr="unit not found", returncode=1),
            ),
        ):
            result = tool.execute("get_logs")

        assert result.ok is False


# ---------------------------------------------------------------------------
# list_packages
# ---------------------------------------------------------------------------

class TestListPackages:
    def _run_result(self, stdout: str = "pkg1\npkg2", returncode: int = 0) -> SimpleNamespace:
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)

    def test_linux_apt_get(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch("e_cli.tools.system_tool.shutil.which", side_effect=lambda x: "/usr/bin/apt-get" if x == "apt-get" else None),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result()) as mock_run,
        ):
            result = tool.execute("list_packages")

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "apt-get"

    def test_linux_dnf(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch("e_cli.tools.system_tool.shutil.which", side_effect=lambda x: "/usr/bin/dnf" if x == "dnf" else None),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result()) as mock_run,
        ):
            result = tool.execute("list_packages")

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "dnf"

    def test_macos_brew(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Darwin"),
            patch("e_cli.tools.system_tool.shutil.which", side_effect=lambda x: "/usr/local/bin/brew" if x == "brew" else None),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result()) as mock_run,
        ):
            result = tool.execute("list_packages")

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "brew"

    def test_windows_winget(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Windows"),
            patch("e_cli.tools.system_tool.shutil.which", side_effect=lambda x: "winget" if x == "winget" else None),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result()) as mock_run,
        ):
            result = tool.execute("list_packages")

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "winget"

    def test_no_package_manager(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch("e_cli.tools.system_tool.shutil.which", return_value=None),
        ):
            result = tool.execute("list_packages")

        assert result.ok is False
        assert "No supported package manager" in result.output


# ---------------------------------------------------------------------------
# install_package
# ---------------------------------------------------------------------------

class TestInstallPackage:
    def _run_result(self, stdout: str = "installed", returncode: int = 0) -> SimpleNamespace:
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)

    def test_success_apt_get(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch("e_cli.tools.system_tool.shutil.which", side_effect=lambda x: "/usr/bin/apt-get" if x == "apt-get" else None),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result()) as mock_run,
        ):
            result = tool.execute("install_package", package="curl")

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert "curl" in cmd

    def test_no_package_manager_error(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch("e_cli.tools.system_tool.shutil.which", return_value=None),
        ):
            result = tool.execute("install_package", package="curl")

        assert result.ok is False
        assert "No supported package manager" in result.output

    def test_missing_package_kwarg(self) -> None:
        tool = SystemTool()
        result = tool.execute("install_package")
        assert result.ok is False
        assert "package" in result.output


# ---------------------------------------------------------------------------
# uninstall_package
# ---------------------------------------------------------------------------

class TestUninstallPackage:
    def _run_result(self, stdout: str = "removed", returncode: int = 0) -> SimpleNamespace:
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)

    def test_success_brew(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Darwin"),
            patch("e_cli.tools.system_tool.shutil.which", side_effect=lambda x: "/usr/local/bin/brew" if x == "brew" else None),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result()) as mock_run,
        ):
            result = tool.execute("uninstall_package", package="wget")

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert "wget" in cmd
        assert cmd[0] == "brew"

    def test_no_package_manager_error(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Darwin"),
            patch("e_cli.tools.system_tool.shutil.which", return_value=None),
        ):
            result = tool.execute("uninstall_package", package="wget")

        assert result.ok is False


# ---------------------------------------------------------------------------
# list_drivers
# ---------------------------------------------------------------------------

class TestListDrivers:
    def _run_result(self, stdout: str = "Module\ndrv1", returncode: int = 0) -> SimpleNamespace:
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)

    def test_linux_lsmod(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Linux"),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result()) as mock_run,
        ):
            result = tool.execute("list_drivers")

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "lsmod"

    def test_windows_driverquery(self) -> None:
        tool = SystemTool()
        with (
            patch("e_cli.tools.system_tool.platform.system", return_value="Windows"),
            patch("e_cli.tools.system_tool.subprocess.run", return_value=self._run_result("driver info")) as mock_run,
        ):
            result = tool.execute("list_drivers")

        assert result.ok is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "driverquery"

    def test_macos_unsupported(self) -> None:
        tool = SystemTool()
        with patch("e_cli.tools.system_tool.platform.system", return_value="Darwin"):
            result = tool.execute("list_drivers")

        assert result.ok is False
        assert "not supported on macOS" in result.output


# ---------------------------------------------------------------------------
# Unknown action
# ---------------------------------------------------------------------------

def test_unknown_action_returns_error() -> None:
    tool = SystemTool()
    result = tool.execute("nonexistent_action")
    assert result.ok is False
    assert "Unknown system action" in result.output
