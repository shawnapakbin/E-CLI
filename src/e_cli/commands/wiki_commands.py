"""Wiki management CLI commands."""

import typer

from e_cli.wiki.manager import WikiManager
from e_cli.wiki.search import WikiSearch
from e_cli.wiki.indexer import WikiIndexer
from e_cli.ui.messages import printInfo, printError
from e_cli.ui.components import show_table, show_success, show_key_value_pairs

app = typer.Typer(help="Knowledge wiki management commands")


@app.command("init")
def init_wiki() -> None:
    """Initialize the wiki system."""
    try:
        wiki = WikiManager()
        show_success("Wiki initialized successfully.")
        printInfo(f"Wiki directory: {wiki.wiki_dir}")

    except Exception as e:
        printError(f"Failed to initialize wiki: {e}")


@app.command("create")
def create_page(
    name: str = typer.Argument(..., help="Page name"),
    category: str = typer.Option("concepts", "--category", "-c", help="Page category"),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
) -> None:
    """Create a new wiki page."""
    try:
        wiki = WikiManager()

        tag_list = tags.split(",") if tags else []
        tag_list = [t.strip() for t in tag_list]

        page = wiki.create_page(
            name=name,
            content=f"# {name}\n\nWrite your content here...",
            category=category,
            tags=tag_list,
        )

        show_success(f"Page created: {page.path}")
        printInfo(f"Edit the page at: {page.path}")

    except FileExistsError:
        printError(f"Page '{name}' already exists.")
    except Exception as e:
        printError(f"Failed to create page: {e}")


@app.command("list")
def list_pages(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
) -> None:
    """List all wiki pages."""
    try:
        wiki = WikiManager()
        pages = wiki.list_pages(category=category)

        if not pages:
            printInfo("No pages found.")
            return

        headers = ["Title", "Category", "Tags", "Updated"]
        rows = []

        for page in pages:
            category_name = page.path.parent.name
            tags_str = ", ".join(page.tags[:3])
            if len(page.tags) > 3:
                tags_str += "..."

            updated = page.updated_at.strftime("%Y-%m-%d") if page.updated_at else "Unknown"

            rows.append([
                page.title,
                category_name,
                tags_str or "-",
                updated,
            ])

        show_table(headers, rows, title="Wiki Pages")
        printInfo(f"\nTotal: {len(pages)} page(s)")

    except Exception as e:
        printError(f"Failed to list pages: {e}")


@app.command("search")
def search_pages(
    query: str = typer.Argument(..., help="Search query"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    tags: str = typer.Option(None, "--tags", "-t", help="Filter by tags (comma-separated)"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results"),
) -> None:
    """Search wiki pages."""
    try:
        wiki = WikiManager()
        search = WikiSearch(wiki.wiki_dir)

        tag_list = tags.split(",") if tags else None
        results = search.search(query=query, category=category, tags=tag_list, limit=limit)

        if not results:
            printInfo("No matching pages found.")
            return

        headers = ["Title", "Score", "Summary"]
        rows = []

        for page, score in results:
            summary = page.get_summary(max_length=60)
            rows.append([
                page.title,
                f"{score:.1f}",
                summary,
            ])

        show_table(headers, rows, title=f"Search Results for '{query}'")
        printInfo(f"\nFound {len(results)} matching page(s).")

    except Exception as e:
        printError(f"Failed to search pages: {e}")


@app.command("show")
def show_page(
    name: str = typer.Argument(..., help="Page name"),
) -> None:
    """Show page information."""
    try:
        wiki = WikiManager()
        page = wiki.get_page(name)

        if not page:
            printError(f"Page '{name}' not found.")
            return

        info = {
            "Title": page.title,
            "Path": str(page.path),
            "Category": page.path.parent.name,
            "Tags": ", ".join(page.tags) if page.tags else "None",
            "Links": str(len(page.links)),
            "Created": page.created_at.strftime("%Y-%m-%d %H:%M") if page.created_at else "Unknown",
            "Updated": page.updated_at.strftime("%Y-%m-%d %H:%M") if page.updated_at else "Unknown",
        }

        show_key_value_pairs(info, title=f"Page: {name}")

        # Show related pages
        if page.links:
            printInfo("\nLinks to:")
            for link in page.links[:10]:
                printInfo(f"  → {link.target}")

    except Exception as e:
        printError(f"Failed to show page: {e}")


@app.command("delete")
def delete_page(
    name: str = typer.Argument(..., help="Page name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a wiki page."""
    try:
        wiki = WikiManager()

        if not yes:
            page = wiki.get_page(name)
            if not page:
                printError(f"Page '{name}' not found.")
                return

            confirm = input(f"Delete page '{page.title}' at {page.path}? (y/N): ")
            if confirm.lower() != 'y':
                printInfo("Cancelled.")
                return

        if wiki.delete_page(name):
            show_success(f"Page '{name}' deleted.")
        else:
            printError(f"Page '{name}' not found.")

    except Exception as e:
        printError(f"Failed to delete page: {e}")


@app.command("index")
def rebuild_index() -> None:
    """Rebuild the wiki index."""
    try:
        wiki = WikiManager()
        indexer = WikiIndexer(wiki.wiki_dir)

        printInfo("Building wiki index...")
        index = indexer.build_index()

        show_success(f"Index rebuilt: {len(index['pages'])} pages indexed.")

    except Exception as e:
        printError(f"Failed to rebuild index: {e}")


@app.command("stats")
def show_stats() -> None:
    """Show wiki statistics."""
    try:
        wiki = WikiManager()
        stats = wiki.get_stats()

        info = {
            "Total Pages": str(stats["total_pages"]),
            "Total Tags": str(stats["total_tags"]),
            "Total Links": str(stats["total_links"]),
        }

        show_key_value_pairs(info, title="Wiki Statistics")

        # Show breakdown by category
        if stats["categories"]:
            printInfo("\nPages by Category:")
            for category, count in stats["categories"].items():
                printInfo(f"  {category}: {count}")

    except Exception as e:
        printError(f"Failed to get stats: {e}")


@app.command("backlinks")
def show_backlinks(
    name: str = typer.Argument(..., help="Page name"),
) -> None:
    """Show pages that link to this page."""
    try:
        wiki = WikiManager()
        backlinks_map = wiki.compute_backlinks()

        page = wiki.get_page(name)
        if not page:
            printError(f"Page '{name}' not found.")
            return

        page_name = page.path.stem
        backlinks = backlinks_map.get(page_name, [])

        if not backlinks:
            printInfo(f"No backlinks found for '{name}'.")
            return

        printInfo(f"Pages linking to '{page.title}':")
        for link in backlinks:
            printInfo(f"  ← {link.display or link.target}")

    except Exception as e:
        printError(f"Failed to show backlinks: {e}")
