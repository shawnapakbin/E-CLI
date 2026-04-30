"""Interactive menu system for E-CLI commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any
import sys


@dataclass
class MenuItem:
    """Represents a single menu option."""

    key: str
    label: str
    description: str | None = None
    action: Callable[[], Any] | None = None
    submenu: Menu | None = None
    shortcut: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        """Validate that item has either action or submenu, not both."""
        if self.action is not None and self.submenu is not None:
            raise ValueError("MenuItem cannot have both action and submenu")
        if self.action is None and self.submenu is None:
            raise ValueError("MenuItem must have either action or submenu")


@dataclass
class Menu:
    """Interactive menu with numbered options."""

    title: str
    items: list[MenuItem] = field(default_factory=list)
    description: str | None = None
    show_back: bool = True
    show_exit: bool = False
    _parent: Menu | None = None

    def add_item(self, item: MenuItem) -> None:
        """Add a menu item to this menu."""
        self.items.append(item)

    def add_action(
        self,
        key: str,
        label: str,
        action: Callable[[], Any],
        description: str | None = None,
        shortcut: str | None = None,
    ) -> None:
        """Add an action item to the menu."""
        self.add_item(
            MenuItem(
                key=key,
                label=label,
                description=description,
                action=action,
                shortcut=shortcut,
            )
        )

    def add_submenu(
        self,
        key: str,
        label: str,
        submenu: Menu,
        description: str | None = None,
        shortcut: str | None = None,
    ) -> None:
        """Add a submenu item to the menu."""
        submenu._parent = self
        self.add_item(
            MenuItem(
                key=key,
                label=label,
                description=description,
                submenu=submenu,
                shortcut=shortcut,
            )
        )

    def get_enabled_items(self) -> list[MenuItem]:
        """Get only enabled items."""
        return [item for item in self.items if item.enabled]


@dataclass
class MenuSession:
    """Manages menu navigation state and execution."""

    root_menu: Menu
    _menu_stack: list[Menu] = field(default_factory=list)
    _running: bool = False

    def __post_init__(self) -> None:
        """Initialize menu stack with root menu."""
        self._menu_stack = [self.root_menu]

    def get_current_menu(self) -> Menu:
        """Get the currently active menu."""
        if not self._menu_stack:
            return self.root_menu
        return self._menu_stack[-1]

    def push_menu(self, menu: Menu) -> None:
        """Navigate to a submenu."""
        self._menu_stack.append(menu)

    def pop_menu(self) -> Menu | None:
        """Go back to previous menu."""
        if len(self._menu_stack) > 1:
            return self._menu_stack.pop()
        return None

    def is_at_root(self) -> bool:
        """Check if currently at root menu."""
        return len(self._menu_stack) <= 1

    def run(self) -> Any:
        """Run the menu session with interactive navigation."""
        from e_cli.ui.menu_renderer import MenuRenderer

        self._running = True
        renderer = MenuRenderer()
        result = None

        while self._running:
            current_menu = self.get_current_menu()

            # Render the menu and get user selection
            try:
                selected_item = renderer.display_and_select(current_menu, self.is_at_root())
            except KeyboardInterrupt:
                # User pressed Ctrl+C
                if self.is_at_root():
                    self._running = False
                    break
                else:
                    # Go back to previous menu
                    self.pop_menu()
                    continue
            except EOFError:
                # User pressed Ctrl+D
                self._running = False
                break

            if selected_item is None:
                # User chose to go back or exit
                if self.is_at_root():
                    self._running = False
                else:
                    self.pop_menu()
                continue

            # Execute the selected item
            if selected_item.action is not None:
                # Execute action
                try:
                    result = selected_item.action()
                    # If action returns a value, we might want to exit
                    # For now, continue showing menu unless explicitly stopped
                except Exception as exc:
                    from e_cli.ui.messages import printError
                    printError(f"Error executing {selected_item.label}: {exc}")
                    input("\nPress Enter to continue...")

            elif selected_item.submenu is not None:
                # Navigate to submenu
                self.push_menu(selected_item.submenu)

        return result


def is_interactive_terminal() -> bool:
    """Check if running in an interactive terminal (TTY)."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def should_use_menu_mode() -> bool:
    """Determine if menu mode should be used based on environment."""
    # For now, simple check - can be enhanced with config later
    return is_interactive_terminal()
