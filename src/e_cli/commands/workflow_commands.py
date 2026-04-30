"""Workflow management CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from e_cli.config import get_app_dir
from e_cli.ui.messages import printError, printInfo, printSuccess
from e_cli.workflows.manager import Workflow, WorkflowExecutor, WorkflowManager

app = typer.Typer(help="Workflow and macro management")
console = Console()


@app.command("list")
def list_workflows(
    tag: str | None = typer.Option(None, "--tag", "-t", help="Filter by tag"),
) -> None:
    """List all available workflows."""
    try:
        # Check both app workflows and project workflows
        app_workflows_dir = get_app_dir() / "workflows"
        project_workflows_dir = Path("workflows")

        manager = WorkflowManager(app_workflows_dir)
        workflows = manager.list_workflows()

        # Also load from project workflows if exists
        if project_workflows_dir.exists():
            project_manager = WorkflowManager(project_workflows_dir)
            workflows.extend(project_manager.list_workflows())

        # Filter by tag if specified
        if tag:
            workflows = [w for w in workflows if tag in w.tags]

        if not workflows:
            if tag:
                printInfo(f"No workflows found with tag: {tag}")
            else:
                printInfo("No workflows found.")
            printQuickTip("Create a workflow with: e-cli workflow create <name>")
            return

        # Display workflows in a table
        table = Table(title="Available Workflows")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Version", style="magenta")
        table.add_column("Description", style="white")
        table.add_column("Steps", justify="right", style="green")
        table.add_column("Tags", style="yellow")

        for workflow in workflows:
            table.add_row(
                workflow.name,
                workflow.version,
                workflow.description[:50] + "..." if len(workflow.description) > 50 else workflow.description,
                str(len(workflow.steps)),
                ", ".join(workflow.tags) if workflow.tags else "-",
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(workflows)} workflow(s)[/dim]")

    except Exception as e:
        printError(f"Failed to list workflows: {e}")
        raise typer.Exit(code=1)


@app.command("show")
def show_workflow(
    name: str = typer.Argument(..., help="Workflow name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
) -> None:
    """Show detailed information about a workflow."""
    try:
        # Try app workflows first, then project workflows
        app_workflows_dir = get_app_dir() / "workflows"
        project_workflows_dir = Path("workflows")

        manager = WorkflowManager(app_workflows_dir)
        workflow = manager.get_workflow(name)

        if not workflow and project_workflows_dir.exists():
            project_manager = WorkflowManager(project_workflows_dir)
            workflow = project_manager.get_workflow(name)

        if not workflow:
            printError(f"Workflow not found: {name}")
            raise typer.Exit(code=1)

        # Display workflow details
        console.print(f"\n[bold cyan]{workflow.name}[/bold cyan] [dim]v{workflow.version}[/dim]")
        console.print(f"[dim]Author: {workflow.author}[/dim]\n")
        console.print(f"{workflow.description}\n")

        if workflow.tags:
            console.print(f"[yellow]Tags:[/yellow] {', '.join(workflow.tags)}\n")

        # Show parameters
        if workflow.parameters:
            console.print("[bold]Parameters:[/bold]")
            param_table = Table(show_header=True, box=None)
            param_table.add_column("Name", style="cyan")
            param_table.add_column("Type", style="magenta")
            param_table.add_column("Required", style="yellow")
            param_table.add_column("Default", style="green")
            param_table.add_column("Description", style="white")

            for param in workflow.parameters:
                param_table.add_row(
                    param.get("name", ""),
                    param.get("type", ""),
                    "Yes" if param.get("required", False) else "No",
                    str(param.get("default", "-")),
                    param.get("description", ""),
                )

            console.print(param_table)
            console.print()

        # Show steps
        console.print(f"[bold]Steps:[/bold] ({len(workflow.steps)} total)\n")
        for i, step in enumerate(workflow.steps, 1):
            console.print(f"  [cyan]{i}.[/cyan] [bold]{step.name}[/bold]")
            console.print(f"     [dim]Tool:[/dim] {step.tool}")

            if verbose:
                if step.parameters:
                    console.print(f"     [dim]Parameters:[/dim]")
                    for key, value in step.parameters.items():
                        console.print(f"       - {key}: {value}")

                if step.condition:
                    console.print(f"     [dim]Condition:[/dim] {step.condition}")

            console.print()

    except Exception as e:
        printError(f"Failed to show workflow: {e}")
        raise typer.Exit(code=1)


@app.command("run")
def run_workflow(
    name: str = typer.Argument(..., help="Workflow name"),
    params: list[str] = typer.Option([], "--param", "-p", help="Parameters in key=value format"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be executed without running"),
) -> None:
    """Execute a workflow."""
    try:
        # Try app workflows first, then project workflows
        app_workflows_dir = get_app_dir() / "workflows"
        project_workflows_dir = Path("workflows")

        manager = WorkflowManager(app_workflows_dir)
        workflow = manager.get_workflow(name)

        if not workflow and project_workflows_dir.exists():
            project_manager = WorkflowManager(project_workflows_dir)
            workflow = project_manager.get_workflow(name)

        if not workflow:
            printError(f"Workflow not found: {name}")
            raise typer.Exit(code=1)

        # Parse parameters
        parameters: dict[str, Any] = {}
        for param in params:
            if "=" not in param:
                printError(f"Invalid parameter format: {param} (use key=value)")
                raise typer.Exit(code=1)

            key, value = param.split("=", 1)
            parameters[key] = value

        # Validate required parameters
        for param_def in workflow.parameters:
            param_name = param_def.get("name", "")
            if param_def.get("required", False) and param_name not in parameters:
                printError(f"Missing required parameter: {param_name}")
                raise typer.Exit(code=1)

            # Use default if not provided
            if param_name not in parameters and "default" in param_def:
                parameters[param_name] = param_def["default"]

        if dry_run:
            console.print(f"\n[bold]Dry run for workflow:[/bold] {workflow.name}\n")
            console.print("[bold]Parameters:[/bold]")
            for key, value in parameters.items():
                console.print(f"  {key} = {value}")
            console.print(f"\n[bold]Steps to execute:[/bold]")
            for i, step in enumerate(workflow.steps, 1):
                status = "[green]✓[/green]"
                if step.condition:
                    status = "[yellow]?[/yellow]"
                console.print(f"  {status} {i}. {step.name} ({step.tool})")
            console.print()
            return

        # Execute workflow
        printInfo(f"Executing workflow: {workflow.name}")
        executor = WorkflowExecutor()
        results = executor.execute(workflow, parameters)

        # Display results
        console.print()
        for step_result in results["steps"]:
            step_name = step_result.get("name", "")

            if step_result.get("skipped"):
                console.print(f"[yellow]⊘[/yellow] {step_name} - Skipped: {step_result.get('reason', '')}")
            elif step_result.get("error"):
                console.print(f"[red]✗[/red] {step_name} - Error: {step_result.get('error', '')}")
            else:
                console.print(f"[green]✓[/green] {step_name} - {step_result.get('status', 'done')}")

        console.print()
        if results["success"]:
            printSuccess(f"Workflow '{workflow.name}' completed successfully")
        else:
            printError(f"Workflow '{workflow.name}' failed: {results.get('error', 'Unknown error')}")
            raise typer.Exit(code=1)

    except Exception as e:
        printError(f"Failed to run workflow: {e}")
        raise typer.Exit(code=1)


@app.command("create")
def create_workflow(
    name: str = typer.Argument(..., help="Workflow name"),
    description: str = typer.Option("", "--description", "-d", help="Workflow description"),
    global_workflow: bool = typer.Option(False, "--global", "-g", help="Create in global workflows directory"),
) -> None:
    """Create a new workflow template."""
    try:
        if global_workflow:
            workflows_dir = get_app_dir() / "workflows"
        else:
            workflows_dir = Path("workflows")

        workflows_dir.mkdir(parents=True, exist_ok=True)

        # Create basic workflow template
        workflow = Workflow(
            name=name,
            description=description or f"Workflow: {name}",
            version="1.0.0",
            author="user",
            parameters=[
                {
                    "name": "example_param",
                    "type": "string",
                    "required": False,
                    "default": "default_value",
                    "description": "Example parameter",
                }
            ],
            steps=[],
            tags=["custom"],
        )

        manager = WorkflowManager(workflows_dir)
        manager.save_workflow(workflow)

        workflow_file = workflows_dir / f"{name}.yaml"
        printSuccess(f"Created workflow: {workflow_file}")
        printInfo(f"Edit the file to add steps and customize parameters")

    except Exception as e:
        printError(f"Failed to create workflow: {e}")
        raise typer.Exit(code=1)


@app.command("delete")
def delete_workflow(
    name: str = typer.Argument(..., help="Workflow name"),
    global_workflow: bool = typer.Option(False, "--global", "-g", help="Delete from global workflows"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a workflow."""
    try:
        if global_workflow:
            workflows_dir = get_app_dir() / "workflows"
        else:
            workflows_dir = Path("workflows")

        manager = WorkflowManager(workflows_dir)
        workflow = manager.get_workflow(name)

        if not workflow:
            printError(f"Workflow not found: {name}")
            raise typer.Exit(code=1)

        if not force:
            confirm = input(f"Delete workflow '{name}'? [y/N]: ").strip().lower()
            if confirm != "y":
                printInfo("Cancelled")
                return

        if manager.delete_workflow(name):
            printSuccess(f"Deleted workflow: {name}")
        else:
            printError(f"Failed to delete workflow: {name}")
            raise typer.Exit(code=1)

    except Exception as e:
        printError(f"Failed to delete workflow: {e}")
        raise typer.Exit(code=1)


def printQuickTip(message: str) -> None:
    """Print a quick tip message."""
    console.print(f"[dim]💡 Tip: {message}[/dim]")


if __name__ == "__main__":
    app()
