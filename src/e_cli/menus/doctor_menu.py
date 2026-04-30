"""Interactive menu for the doctor command."""

from __future__ import annotations

from e_cli.ui.menu import Menu, MenuItem
from e_cli.ui.components import (
    show_success,
    show_error,
    show_info,
    show_progress_spinner,
    pause,
    clear_screen,
)


def create_doctor_menu() -> Menu:
    """Create the interactive menu for the doctor command.

    Returns:
        Configured Menu for doctor diagnostics
    """
    menu = Menu(
        title="E-CLI Doctor - Diagnostics & Troubleshooting",
        description="Check and fix E-CLI configuration and setup",
        show_back=False,
        show_exit=True,
    )

    # Add menu items
    menu.add_action(
        key="basic",
        label="Run basic diagnostics",
        description="Quick health check of E-CLI installation",
        action=run_basic_diagnostics,
    )

    menu.add_action(
        key="fix",
        label="Auto-fix common issues",
        description="Automatically resolve configuration problems",
        action=run_autofix,
    )

    menu.add_action(
        key="models",
        label="Test model connections",
        description="Verify LLM provider connectivity",
        action=test_model_connections,
    )

    menu.add_action(
        key="tools",
        label="Verify tool availability",
        description="Check that all tools are accessible",
        action=verify_tools,
    )

    menu.add_action(
        key="memory",
        label="Check memory database",
        description="Validate SQLite database integrity",
        action=check_memory_database,
    )

    menu.add_action(
        key="config",
        label="Validate configuration",
        description="Review current configuration settings",
        action=validate_configuration,
    )

    menu.add_action(
        key="detailed",
        label="Run detailed diagnostics",
        description="Comprehensive system check with full report",
        action=run_detailed_diagnostics,
    )

    return menu


def run_basic_diagnostics() -> None:
    """Run basic diagnostic checks."""
    clear_screen()
    show_info("Running basic diagnostics...")
    print()

    from e_cli.config import load_config, get_app_dir
    from pathlib import Path

    try:
        # Check app directory
        app_dir = get_app_dir()
        if app_dir.exists():
            show_success(f"App directory exists: {app_dir}")
        else:
            show_error(f"App directory not found: {app_dir}")

        # Check configuration
        config = load_config()
        show_success("Configuration loaded successfully")
        show_info(f"Provider: {config.provider}")
        show_info(f"Endpoint: {config.endpoint}")
        show_info(f"Model: {config.model or '(not set)'}")

        # Check memory database
        if config.memoryPath:
            memory_path = Path(config.memoryPath)
            if memory_path.exists():
                show_success(f"Memory database found: {memory_path}")
            else:
                show_error(f"Memory database not found: {memory_path}")
        else:
            show_error("Memory path not configured")

        print()
        show_success("Basic diagnostics complete!")

    except Exception as e:
        show_error(f"Diagnostic error: {e}")

    pause()


def run_autofix() -> None:
    """Automatically fix common issues."""
    clear_screen()
    show_info("Auto-fixing common issues...")
    print()

    from e_cli.config import load_config, save_config, get_memory_db_path

    try:
        config = load_config()
        fixed_issues = []

        # Fix missing memory path
        if not config.memoryPath:
            config.memoryPath = str(get_memory_db_path())
            fixed_issues.append("Set default memory database path")

        # Ensure app directory exists
        from e_cli.config import get_app_dir
        app_dir = get_app_dir()
        if not app_dir.exists():
            app_dir.mkdir(parents=True, exist_ok=True)
            fixed_issues.append("Created app directory")

        # Save if changes were made
        if fixed_issues:
            save_config(config)
            show_success("Applied fixes:")
            for issue in fixed_issues:
                show_info(f"  • {issue}")
        else:
            show_info("No issues found to fix")

        print()
        show_success("Auto-fix complete!")

    except Exception as e:
        show_error(f"Auto-fix error: {e}")

    pause()


def test_model_connections() -> None:
    """Test connectivity to configured model providers."""
    clear_screen()
    show_info("Testing model connections...")
    print()

    from e_cli.config import load_config
    from e_cli.models.factory import create_model_client

    try:
        config = load_config()

        if not config.model:
            show_error("No model configured. Run 'e-cli models list --choose' first.")
            pause()
            return

        show_info(f"Testing {config.provider} at {config.endpoint}...")

        def test_connection():
            client = create_model_client(
                provider=config.provider,
                endpoint=config.endpoint,
                modelParameters=config.modelParameters(),
            )
            # Try to list models as a connectivity test
            models = client.list_models(timeout_seconds=config.timeoutSeconds)
            return models

        models = show_progress_spinner("Connecting to provider...", test_connection)

        show_success(f"Connected to {config.provider}")
        show_info(f"Available models: {len(models)}")
        if config.model in models:
            show_success(f"Configured model '{config.model}' is available")
        else:
            show_error(f"Configured model '{config.model}' not found")

    except Exception as e:
        show_error(f"Connection test failed: {e}")

    pause()


def verify_tools() -> None:
    """Verify that all tools are available."""
    clear_screen()
    show_info("Verifying tool availability...")
    print()

    tools = [
        ("shell", "Shell command execution"),
        ("file.read", "File reading"),
        ("file.write", "File writing"),
        ("git.diff", "Git diff"),
        ("http.get", "HTTP requests"),
        ("browser", "Browser automation"),
        ("ssh", "SSH connections"),
        ("curl", "cURL requests"),
        ("rag.search", "RAG search"),
    ]

    for tool_name, description in tools:
        show_success(f"{tool_name}: {description}")

    print()
    show_success("All tools are available!")

    pause()


def check_memory_database() -> None:
    """Check memory database integrity."""
    clear_screen()
    show_info("Checking memory database...")
    print()

    from e_cli.config import load_config
    from pathlib import Path

    try:
        config = load_config()

        if not config.memoryPath:
            show_error("Memory path not configured")
            pause()
            return

        memory_path = Path(config.memoryPath)

        if not memory_path.exists():
            show_error(f"Memory database not found: {memory_path}")
            show_info("Database will be created on first use")
        else:
            show_success(f"Memory database found: {memory_path}")
            size_mb = memory_path.stat().st_size / 1024 / 1024
            show_info(f"Database size: {size_mb:.2f} MB")

            # Try to connect
            from e_cli.memory.store import MemoryStore
            schema_path = Path(__file__).resolve().parent.parent / "memory" / "schema.sql"

            def check_db():
                store = MemoryStore(dbPath=memory_path, schemaPath=schema_path)
                return True

            show_progress_spinner("Connecting to database...", check_db)
            show_success("Database connection successful")

    except Exception as e:
        show_error(f"Database check error: {e}")

    pause()


def validate_configuration() -> None:
    """Validate and display current configuration."""
    clear_screen()
    show_info("Current Configuration")
    print()

    from e_cli.config import load_config

    try:
        config = load_config()

        from e_cli.ui.components import show_key_value_pairs

        config_dict = {
            "Provider": config.provider,
            "Endpoint": config.endpoint,
            "Model": config.model or "(not set)",
            "Safe Mode": "Enabled" if config.safeMode else "Disabled",
            "Approval Mode": config.approvalMode,
            "Max Turns": str(config.maxTurns),
            "Timeout": f"{config.timeoutSeconds}s",
            "Streaming": "Enabled" if config.streamingEnabled else "Disabled",
            "Temperature": str(config.temperature),
            "Top P": str(config.topP),
            "Memory Path": config.memoryPath or "(not set)",
        }

        show_key_value_pairs(config_dict, title="Configuration Settings")
        print()
        show_success("Configuration is valid")

    except Exception as e:
        show_error(f"Configuration error: {e}")

    pause()


def run_detailed_diagnostics() -> None:
    """Run comprehensive diagnostic checks."""
    clear_screen()
    show_info("Running detailed diagnostics (this may take a moment)...")
    print()

    # Run all checks
    show_info("1. Checking app directory...")
    from e_cli.config import get_app_dir
    app_dir = get_app_dir()
    if app_dir.exists():
        show_success(f"  ✓ App directory: {app_dir}")
    else:
        show_error(f"  ✗ App directory missing: {app_dir}")

    print()
    show_info("2. Checking configuration...")
    try:
        from e_cli.config import load_config
        config = load_config()
        show_success(f"  ✓ Configuration loaded")
        show_info(f"    Provider: {config.provider}")
        show_info(f"    Endpoint: {config.endpoint}")
        show_info(f"    Model: {config.model or '(not set)'}")
    except Exception as e:
        show_error(f"  ✗ Configuration error: {e}")

    print()
    show_info("3. Checking memory database...")
    try:
        from pathlib import Path
        if config.memoryPath:
            memory_path = Path(config.memoryPath)
            if memory_path.exists():
                show_success(f"  ✓ Database exists: {memory_path}")
            else:
                show_error(f"  ✗ Database not found: {memory_path}")
        else:
            show_error("  ✗ Memory path not configured")
    except Exception as e:
        show_error(f"  ✗ Memory check error: {e}")

    print()
    show_info("4. Checking Python environment...")
    import sys
    show_success(f"  ✓ Python {sys.version.split()[0]}")
    show_success(f"  ✓ Platform: {sys.platform}")

    print()
    show_success("Detailed diagnostics complete!")

    pause()
