"""Doctor command."""

from __future__ import annotations

import shutil
import sys

import typer
from rich.console import Console
from rich.table import Table

from constrained_agent import __version__
from constrained_agent.settings import Settings

console = Console()


def doctor_command(
    ctx: typer.Context,
    skip_model: bool = typer.Option(False, "--skip-model", help="Skip model accessibility check"),
) -> None:
    """Verify system prerequisites."""
    del skip_model
    console.print("[bold green]CAH Doctor[/bold green]")
    console.print(f"Version: {__version__}")
    console.print()

    checks: list[tuple[str, bool, str]] = []
    py_ok = sys.version_info >= (3, 13)
    checks.append(("Python >= 3.13", py_ok, sys.version.split()[0]))
    git_path = shutil.which("git")
    checks.append(("Git available", git_path is not None, git_path or "not found"))
    docker_path = shutil.which("docker")
    checks.append(
        ("Docker available", docker_path is not None, docker_path or "not found (optional)")
    )

    settings: Settings = ctx.obj["settings"]
    creds_ok = bool(settings.google_api_key) or settings.use_vertex_ai
    checks.append(("Google credentials configured", creds_ok, "yes" if creds_ok else "no"))
    checks.append(("Runtime directory", True, str(settings.runtime_dir.resolve())))

    for tool_name in ["pytest", "ruff", "mypy", "alembic"]:
        tool_path = shutil.which(tool_name)
        checks.append((f"Tool: {tool_name}", tool_path is not None, tool_path or "not found"))

    table = Table(show_header=False)
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Detail")

    for name, ok, detail in checks:
        status = "✓" if ok else "✗"
        style = "green" if ok else "red"
        table.add_row(name, f"[{style}]{status}[/{style}]", detail)

    console.print(table)
