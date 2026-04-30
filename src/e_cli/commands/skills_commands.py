"""Skills management CLI commands."""

import typer
from pathlib import Path

from e_cli.skills.manager import get_skill_manager
from e_cli.ui.messages import printInfo, printError
from e_cli.ui.components import show_table, show_success, show_key_value_pairs

app = typer.Typer(help="Skill management commands")


@app.command("list")
def list_skills(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    enabled_only: bool = typer.Option(False, "--enabled", help="Show only enabled skills"),
) -> None:
    """List all available skills."""
    try:
        manager = get_skill_manager()
        skills = manager.list_skills(category=category, enabled_only=enabled_only)

        if not skills:
            printInfo("No skills found.")
            return

        # Prepare table data
        headers = ["Name", "Version", "Category", "Status", "Description"]
        rows = []

        for skill in skills:
            status = "✓ Enabled" if skill.enabled else "✗ Disabled"
            if skill.load_error:
                status = f"⚠ Error: {skill.load_error[:30]}..."

            rows.append([
                skill.metadata.name,
                skill.metadata.version,
                skill.metadata.category,
                status,
                skill.metadata.description[:40] + ("..." if len(skill.metadata.description) > 40 else ""),
            ])

        show_table(headers, rows, title="Available Skills")

        # Show summary
        stats = manager.get_stats()
        printInfo(f"\nTotal: {stats['total_skills']} skills ({stats['enabled_skills']} enabled, {stats['disabled_skills']} disabled)")

    except Exception as e:
        printError(f"Failed to list skills: {e}")


@app.command("info")
def skill_info(
    name: str = typer.Argument(..., help="Skill name"),
) -> None:
    """Show detailed information about a skill."""
    try:
        manager = get_skill_manager()
        skill = manager.get_skill_info(name)

        if not skill:
            printError(f"Skill '{name}' not found.")
            return

        # Display skill information
        info = {
            "Name": skill.metadata.name,
            "Version": skill.metadata.version,
            "Author": skill.metadata.author,
            "Category": skill.metadata.category,
            "Description": skill.metadata.description,
            "Status": "Enabled" if skill.enabled else "Disabled",
            "Path": str(skill.skill_path),
        }

        if skill.load_error:
            info["Error"] = skill.load_error

        show_key_value_pairs(info, title=f"Skill: {name}")

        # Show tags
        if skill.metadata.tags:
            printInfo(f"\nTags: {', '.join(skill.metadata.tags)}")

        # Show permissions
        if skill.metadata.permissions:
            printInfo(f"Permissions: {', '.join(skill.metadata.permissions)}")

        # Show dependencies
        if skill.metadata.dependencies:
            printInfo(f"Dependencies: {', '.join(skill.metadata.dependencies)}")

    except Exception as e:
        printError(f"Failed to get skill info: {e}")


@app.command("enable")
def enable_skill(
    name: str = typer.Argument(..., help="Skill name"),
) -> None:
    """Enable a skill."""
    try:
        manager = get_skill_manager()

        if manager.enable_skill(name):
            show_success(f"Skill '{name}' enabled.")
        else:
            printError(f"Skill '{name}' not found.")

    except Exception as e:
        printError(f"Failed to enable skill: {e}")


@app.command("disable")
def disable_skill(
    name: str = typer.Argument(..., help="Skill name"),
) -> None:
    """Disable a skill."""
    try:
        manager = get_skill_manager()

        if manager.disable_skill(name):
            show_success(f"Skill '{name}' disabled.")
        else:
            printError(f"Skill '{name}' not found.")

    except Exception as e:
        printError(f"Failed to disable skill: {e}")


@app.command("reload")
def reload_skill(
    name: str = typer.Argument(..., help="Skill name"),
) -> None:
    """Reload a skill from disk."""
    try:
        manager = get_skill_manager()

        if manager.reload_skill(name):
            show_success(f"Skill '{name}' reloaded.")
        else:
            printError(f"Failed to reload skill '{name}'.")

    except Exception as e:
        printError(f"Failed to reload skill: {e}")


@app.command("install")
def install_skill(
    path: str = typer.Argument(..., help="Path to skill directory"),
    category: str = typer.Option("custom", "--category", "-c", help="Category to install into"),
) -> None:
    """Install a skill from a directory."""
    try:
        manager = get_skill_manager()
        source_path = Path(path)

        if not source_path.exists():
            printError(f"Path does not exist: {path}")
            return

        if manager.install_skill(source_path, category):
            show_success(f"Skill installed successfully in category '{category}'.")
        else:
            printError("Failed to install skill. Check that skill.yaml exists.")

    except Exception as e:
        printError(f"Failed to install skill: {e}")


@app.command("search")
def search_skills(
    query: str = typer.Argument(..., help="Search query"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    tags: str = typer.Option(None, "--tags", "-t", help="Filter by tags (comma-separated)"),
) -> None:
    """Search for skills."""
    try:
        manager = get_skill_manager()

        tag_list = tags.split(",") if tags else None
        results = manager.search_skills(query=query, category=category, tags=tag_list)

        if not results:
            printInfo("No matching skills found.")
            return

        headers = ["Name", "Category", "Description"]
        rows = []

        for skill in results:
            rows.append([
                skill.metadata.name,
                skill.metadata.category,
                skill.metadata.description[:50] + ("..." if len(skill.metadata.description) > 50 else ""),
            ])

        show_table(headers, rows, title=f"Search Results for '{query}'")
        printInfo(f"\nFound {len(results)} matching skill(s).")

    except Exception as e:
        printError(f"Failed to search skills: {e}")


@app.command("stats")
def show_stats() -> None:
    """Show skill system statistics."""
    try:
        manager = get_skill_manager()
        stats = manager.get_stats()

        info = {
            "Total Skills": str(stats["total_skills"]),
            "Enabled": str(stats["enabled_skills"]),
            "Disabled": str(stats["disabled_skills"]),
            "Categories": str(stats["categories"]),
        }

        show_key_value_pairs(info, title="Skill System Statistics")

        # Show breakdown by category
        if stats["category_breakdown"]:
            printInfo("\nSkills by Category:")
            for category, count in stats["category_breakdown"].items():
                printInfo(f"  {category}: {count}")

    except Exception as e:
        printError(f"Failed to get stats: {e}")
