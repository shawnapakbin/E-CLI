#!/usr/bin/env python3
"""Cross-platform installer for E-CLI.

This script installs E-CLI with pip and persists the Python user script directory
on PATH for Linux, macOS, and Windows.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig


MARKER_BEGIN = "# >>> e-cli installer >>>"
MARKER_END = "# <<< e-cli installer <<<"


def _run(command: list[str]) -> None:
    """Run one command and raise on non-zero exit status."""

    subprocess.run(command, check=True)


def _python_user_scripts_dir() -> Path:
    """Return the current user's scripts/bin directory for this Python runtime."""

    if os.name == "nt":
        scripts_path = sysconfig.get_path("scripts", scheme="nt_user")
    else:
        scripts_path = sysconfig.get_path("scripts", scheme="posix_user")

    if not scripts_path:
        user_base = Path(sysconfig.get_config_var("userbase") or Path.home() / ".local")
        return user_base / ("Scripts" if os.name == "nt" else "bin")
    return Path(scripts_path)


def _detect_unix_profile() -> Path:
    """Select a shell profile file that is most likely to be sourced."""

    home = Path.home()
    shell = Path(os.environ.get("SHELL", "")).name
    if shell == "zsh":
        return home / ".zshrc"
    if shell == "bash":
        system_name = platform.system().lower()
        if system_name == "darwin":
            return home / ".bash_profile"
        return home / ".bashrc"
    return home / ".profile"


def _persist_path_unix(scripts_dir: Path) -> str:
    """Persist PATH update in a shell rc/profile file on Unix-like systems."""

    profile = _detect_unix_profile()
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.touch(exist_ok=True)

    existing = profile.read_text(encoding="utf-8")
    if MARKER_BEGIN in existing and MARKER_END in existing:
        return f"PATH entry already present in {profile}"

    block = (
        f"\n{MARKER_BEGIN}\n"
        f"export PATH=\"{scripts_dir}:$PATH\"\n"
        f"{MARKER_END}\n"
    )
    profile.write_text(existing + block, encoding="utf-8")
    return f"Added PATH entry to {profile}"


def _persist_path_windows(scripts_dir: Path) -> str:
    """Persist PATH update in current user environment on Windows."""

    try:
        import winreg  # type: ignore
    except Exception as exc:  # pragma: no cover - non-windows environments
        return f"Could not import winreg to persist PATH: {exc}"

    key_path = r"Environment"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            current_path, value_type = winreg.QueryValueEx(key, "Path")
            if not isinstance(current_path, str):
                current_path = ""
        except FileNotFoundError:
            current_path = ""
            value_type = winreg.REG_EXPAND_SZ

        path_parts = [part.strip() for part in current_path.split(";") if part.strip()]
        normalized = {part.lower().rstrip("\\") for part in path_parts}
        scripts_text = str(scripts_dir)
        if scripts_text.lower().rstrip("\\") in normalized:
            return "PATH entry already present in user environment"

        updated_path = scripts_text if not current_path else f"{current_path};{scripts_text}"
        winreg.SetValueEx(key, "Path", 0, value_type, updated_path)

    return "Added PATH entry to current user environment"


def _persist_path(scripts_dir: Path) -> str:
    """Persist path update for the active platform and update current process PATH."""

    os.environ["PATH"] = f"{scripts_dir}{os.pathsep}{os.environ.get('PATH', '')}"

    if os.name == "nt":
        return _persist_path_windows(scripts_dir)
    return _persist_path_unix(scripts_dir)


def _install_package(repo_root: Path, dev: bool) -> None:
    """Install E-CLI with pip for the current user."""

    target = f"{repo_root}[dev]" if dev else str(repo_root)
    _run([sys.executable, "-m", "pip", "install", "--user", target])


def _print_quick_start() -> None:
    """Show a short next-step checklist after installation."""

    print("\nQuick Start")
    print("1. Ensure a model server is running (e.g., Ollama on http://localhost:11434).")
    print("2. Run: e-cli models list")
    print("3. Pick a model: e-cli models list --choose")
    print("4. Start chat: e-cli")


def main() -> int:
    """Parse options, install E-CLI, persist PATH, and show next steps."""

    parser = argparse.ArgumentParser(description="Install E-CLI and add it to PATH")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Install with development extras from the local repository",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = _python_user_scripts_dir()

    print(f"Installing E-CLI from: {repo_root}")
    _install_package(repo_root=repo_root, dev=args.dev)

    print(f"Detected user scripts directory: {scripts_dir}")
    scripts_dir.mkdir(parents=True, exist_ok=True)
    path_result = _persist_path(scripts_dir)
    print(path_result)

    ecli_executable = scripts_dir / ("e-cli.exe" if os.name == "nt" else "e-cli")
    if ecli_executable.exists():
        print(f"Installed executable: {ecli_executable}")

    print("\nInstallation complete.")
    print("Open a new terminal session if `e-cli` is not immediately available.")
    _print_quick_start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
