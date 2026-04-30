"""Reusable UI components for E-CLI menus and interfaces."""

from __future__ import annotations

from typing import Any, Callable
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


def show_header(title: str, subtitle: str | None = None) -> None:
    """Display a formatted header box.

    Args:
        title: Main title text
        subtitle: Optional subtitle text
    """
    content = f"[bold cyan]{title}[/bold cyan]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"

    panel = Panel(content, border_style="cyan", padding=(0, 2))
    console.print(panel)
    console.print()


def show_success(message: str) -> None:
    """Display a success message with checkmark."""
    console.print(f"[green]✓[/green] {message}")


def show_error(message: str) -> None:
    """Display an error message with X mark."""
    console.print(f"[red]✗[/red] {message}")


def show_warning(message: str) -> None:
    """Display a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def show_info(message: str) -> None:
    """Display an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def confirm(question: str, default: bool = False) -> bool:
    """Ask user for yes/no confirmation.

    Args:
        question: Question to ask
        default: Default answer if user just presses Enter

    Returns:
        True if user confirmed, False otherwise
    """
    return Confirm.ask(question, default=default)


def prompt_text(question: str, default: str = "") -> str:
    """Prompt user for text input.

    Args:
        question: Question/prompt to display
        default: Default value if user just presses Enter

    Returns:
        User's input text
    """
    return Prompt.ask(question, default=default)


def prompt_choice(question: str, choices: list[str], default: str | None = None) -> str:
    """Prompt user to select from a list of choices.

    Args:
        question: Question to display
        choices: List of valid choices
        default: Default choice if user just presses Enter

    Returns:
        User's selected choice
    """
    return Prompt.ask(question, choices=choices, default=default if default is not None else "")


def show_progress_spinner(description: str, task: Callable[[], Any]) -> Any:
    """Execute a task while showing a progress spinner.

    Args:
        description: Description of the task being performed
        task: Function to execute

    Returns:
        Result from the task function
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description=description, total=None)
        result = task()
    return result


def show_progress_bar(description: str, total: int, task: Callable[[Callable[[int], None]], Any]) -> Any:
    """Execute a task while showing a progress bar.

    Args:
        description: Description of the task being performed
        total: Total number of steps
        task: Function that accepts an update callback

    Returns:
        Result from the task function
    """
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task_id = progress.add_task(description, total=total)

        def update_progress(steps: int = 1) -> None:
            progress.update(task_id, advance=steps)

        result = task(update_progress)
    return result


def show_table(
    headers: list[str],
    rows: list[list[str]],
    title: str | None = None,
    show_lines: bool = False,
) -> None:
    """Display a formatted table.

    Args:
        headers: Column headers
        rows: List of row data
        title: Optional table title
        show_lines: Whether to show lines between rows
    """
    table = Table(title=title, show_lines=show_lines)

    for header in headers:
        table.add_column(header, style="cyan")

    for row in rows:
        table.add_row(*row)

    console.print(table)


def show_key_value_pairs(pairs: dict[str, str], title: str | None = None) -> None:
    """Display key-value pairs in a formatted table.

    Args:
        pairs: Dictionary of key-value pairs
        title: Optional table title
    """
    table = Table(title=title, show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", width=20)
    table.add_column("Value", style="green")

    for key, value in pairs.items():
        table.add_row(key, value)

    console.print(table)


def pause(message: str = "Press Enter to continue...") -> None:
    """Pause and wait for user to press Enter.

    Args:
        message: Message to display
    """
    console.input(f"\n[dim]{message}[/dim]")


def clear_screen() -> None:
    """Clear the terminal screen."""
    console.clear()


def print_section_header(title: str) -> None:
    """Print a section header with visual separation.

    Args:
        title: Section title
    """
    console.print()
    console.print(f"[bold cyan]{'─' * 50}[/bold cyan]")
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print(f"[bold cyan]{'─' * 50}[/bold cyan]")
    console.print()


def show_status_indicator(status: str, message: str) -> None:
    """Show a status indicator with colored icon.

    Args:
        status: One of 'success', 'error', 'warning', 'info', 'running'
        message: Status message
    """
    icons = {
        "success": "[green]✓[/green]",
        "error": "[red]✗[/red]",
        "warning": "[yellow]⚠[/yellow]",
        "info": "[blue]ℹ[/blue]",
        "running": "[cyan]⟳[/cyan]",
    }

    icon = icons.get(status, "•")
    console.print(f"{icon} {message}")
