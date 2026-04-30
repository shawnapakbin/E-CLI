"""Menu rendering with rich formatting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from e_cli.ui.menu import Menu, MenuItem

console = Console()


class MenuRenderer:
    """Renders menus with rich formatting and handles user input."""

    def __init__(self) -> None:
        """Initialize the menu renderer."""
        self.console = console

    def display_and_select(self, menu: Menu, is_root: bool = False) -> MenuItem | None:
        """Display menu and get user selection.

        Returns:
            Selected MenuItem, or None if user chose back/exit
        """
        # Clear screen for cleaner presentation
        self.console.clear()

        # Display menu header
        self._render_header(menu)

        # Display menu items
        enabled_items = menu.get_enabled_items()
        if not enabled_items:
            self.console.print("[yellow]No available options[/yellow]")
            input("\nPress Enter to continue...")
            return None

        self._render_items(enabled_items)

        # Display footer options
        self._render_footer(menu, is_root)

        # Get user selection
        return self._get_user_selection(enabled_items, menu, is_root)

    def _render_header(self, menu: Menu) -> None:
        """Render the menu header with title and description."""
        # Create title with box
        title_text = Text(menu.title, style="bold cyan", justify="center")

        # Add description if available
        content = title_text
        if menu.description:
            content = Text.assemble(
                (menu.title + "\n", "bold cyan"),
                (menu.description, "dim")
            )

        panel = Panel(
            content,
            border_style="cyan",
            padding=(0, 2),
        )
        self.console.print(panel)
        self.console.print()

    def _render_items(self, items: list[MenuItem]) -> None:
        """Render menu items in a formatted table."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Number", style="cyan", width=4)
        table.add_column("Label", style="green")
        table.add_column("Description", style="dim")

        for idx, item in enumerate(items, 1):
            number = f"{idx}."
            label = item.label
            description = item.description or ""

            # Add indicator for submenu
            if item.submenu is not None:
                label += " →"

            table.add_row(number, label, description)

        self.console.print(table)
        self.console.print()

    def _render_footer(self, menu: Menu, is_root: bool) -> None:
        """Render footer with navigation options."""
        footer_items = []

        if menu.show_back and not is_root:
            footer_items.append("[dim]0. Back[/dim]")

        if menu.show_exit or is_root:
            footer_items.append("[dim]0. Exit[/dim]")

        if footer_items:
            self.console.print(" | ".join(footer_items))
            self.console.print()

    def _get_user_selection(
        self,
        items: list[MenuItem],
        menu: Menu,
        is_root: bool
    ) -> MenuItem | None:
        """Get and validate user selection."""
        max_option = len(items)

        while True:
            try:
                # Prompt for input
                prompt = f"[bold]Select an option (1-{max_option})[/bold]: "
                user_input = self.console.input(prompt).strip()

                if not user_input:
                    continue

                # Check for back/exit
                if user_input == "0":
                    return None

                # Parse selection
                try:
                    selection = int(user_input)
                except ValueError:
                    self.console.print("[red]Invalid input. Please enter a number.[/red]")
                    continue

                # Validate range
                if 1 <= selection <= max_option:
                    return items[selection - 1]
                else:
                    self.console.print(f"[red]Please enter a number between 1 and {max_option}[/red]")

            except KeyboardInterrupt:
                # Re-raise to be handled by MenuSession
                raise
            except EOFError:
                # Re-raise to be handled by MenuSession
                raise


def create_simple_menu(title: str, options: list[tuple[str, str, Callable]]) -> Menu:
    """Helper to create a simple menu from a list of options.

    Args:
        title: Menu title
        options: List of (key, label, action) tuples

    Returns:
        Configured Menu instance
    """
    from e_cli.ui.menu import Menu, MenuItem

    menu = Menu(title=title)
    for key, label, action in options:
        menu.add_item(MenuItem(key=key, label=label, action=action))
    return menu
