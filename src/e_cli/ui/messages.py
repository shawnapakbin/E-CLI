"""UI helper messages for consistent terminal output."""

from __future__ import annotations

from rich.console import Console

console = Console()


def quick_tip(message: str) -> None:
    """Print a standardized Quick Tip helper line."""

    try:
        console.print(f"[cyan]Quick Tip:[/cyan] {message}")
    except Exception as exc:
        raise RuntimeError(f"Failed to print quick tip: {exc}") from exc


def info(message: str) -> None:
    """Print an informational line."""

    try:
        console.print(f"[green]{message}[/green]")
    except Exception as exc:
        raise RuntimeError(f"Failed to print info message: {exc}") from exc


def warn(message: str) -> None:
    """Print a warning line."""

    try:
        console.print(f"[yellow]{message}[/yellow]")
    except Exception as exc:
        raise RuntimeError(f"Failed to print warning message: {exc}") from exc


def error(message: str) -> None:
    """Print an error line."""

    try:
        console.print(f"[red]{message}[/red]")
    except Exception as exc:
        raise RuntimeError(f"Failed to print error message: {exc}") from exc


def printQuickTip(messageText: str) -> None:
    """Compatibility wrapper for Quick Tip message output."""

    try:
        quick_tip(messageText)
    except Exception as exc:
        raise RuntimeError(f"Failed in printQuickTip: {exc}") from exc


def printInfo(messageText: str) -> None:
    """Compatibility wrapper for informational message output."""

    try:
        info(messageText)
    except Exception as exc:
        raise RuntimeError(f"Failed in printInfo: {exc}") from exc


def printError(messageText: str) -> None:
    """Compatibility wrapper for error message output."""

    try:
        error(messageText)
    except Exception as exc:
        raise RuntimeError(f"Failed in printError: {exc}") from exc
