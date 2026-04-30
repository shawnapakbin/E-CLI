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


def stream(message: str) -> None:
    """Print a streaming fragment without forcing a newline."""

    try:
        console.print(message, style="green", end="", markup=False, highlight=False, soft_wrap=True)
    except Exception as exc:
        raise RuntimeError(f"Failed to print stream message: {exc}") from exc


def streamBreak() -> None:
    """Terminate a streaming line with a newline."""

    try:
        console.print()
    except Exception as exc:
        raise RuntimeError(f"Failed to print stream line break: {exc}") from exc


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


def printSuccess(messageText: str) -> None:
    """Compatibility wrapper for success message output."""

    try:
        console.print(f"[green]{messageText}[/green]")
    except Exception as exc:
        raise RuntimeError(f"Failed in printSuccess: {exc}") from exc


def printStream(messageText: str) -> None:
    """Compatibility wrapper for streaming output fragments."""

    try:
        stream(messageText)
    except Exception as exc:
        raise RuntimeError(f"Failed in printStream: {exc}") from exc


def printStreamBreak() -> None:
    """Compatibility wrapper for ending a streaming output line."""

    try:
        streamBreak()
    except Exception as exc:
        raise RuntimeError(f"Failed in printStreamBreak: {exc}") from exc
