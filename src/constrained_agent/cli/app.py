"""CLI entry point using Typer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from constrained_agent import __version__
from constrained_agent.settings import Settings
from constrained_agent.logging import configure_logging, get_logger

app = typer.Typer(
    name="cah",
    help="constrained-agent-harness — bounded, verifiable coding agent execution",
    no_args_is_help=True,
)
console = Console()
logger = get_logger(__name__)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"constrained-agent-harness v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    log_level: Optional[str] = typer.Option(None, "--log-level", help="Log level override"),
) -> None:
    """CAH: constrained-agent-harness CLI."""
    settings = Settings()
    level = log_level or settings.log_level
    configure_logging(level if not verbose else "DEBUG")
    ctx.obj = {"settings": settings, "verbose": verbose}


@app.command()
def doctor(
    ctx: typer.Context,
    skip_model: bool = typer.Option(False, "--skip-model", help="Skip model accessibility check"),
) -> None:
    """Verify system prerequisites."""
    console.print("[bold green]CAH Doctor[/bold green]")
    console.print(f"Version: {__version__}")
    console.print()

    checks: list[tuple[str, bool, str]] = []

    # Python version
    import sys
    py_ok = sys.version_info >= (3, 13)
    checks.append(("Python >= 3.13", py_ok, sys.version.split()[0]))

    # Git
    import shutil
    git_path = shutil.which("git")
    git_ok = git_path is not None
    checks.append(("Git available", git_ok, git_path or "not found"))

    # Docker
    docker_path = shutil.which("docker")
    docker_ok = docker_path is not None
    checks.append(("Docker available", docker_ok, docker_path or "not found (optional for scripted mode)"))

    # Google credentials
    settings: Settings = ctx.obj["settings"]
    creds_ok = bool(settings.google_api_key) or settings.use_vertex_ai
    checks.append(("Google credentials configured", creds_ok, "yes" if creds_ok else "no (needed for google-adk agent)"))

    # Runtime dir
    runtime_dir = settings.runtime_dir
    runtime_ok = True
    checks.append(("Runtime directory", runtime_ok, str(runtime_dir.resolve())))

    # Evaluator tools
    for tool_name in ["pytest", "ruff", "mypy"]:
        tool_path = shutil.which(tool_name)
        checks.append((f"Evaluator: {tool_name}", tool_path is not None, tool_path or "not found"))

    table = Table(show_header=False)
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Detail")

    for name, ok, detail in checks:
        status = "✓" if ok else "✗"
        style = "green" if ok else "red"
        table.add_row(name, f"[{style}]{status}[/{style}]", detail)

    console.print(table)


@app.command()
def init(
    ctx: typer.Context,
    path: Path = typer.Option(".", "--path", "-p", help="Project path"),
) -> None:
    """Initialize a CAH runtime directory."""
    settings: Settings = ctx.obj["settings"]
    runtime_dir = Path(path) / settings.runtime_dir
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "artifacts").mkdir(exist_ok=True)
    console.print(f"[green]Initialized CAH runtime at {runtime_dir.resolve()}[/green]")


@app.command()
def validate_goal(
    ctx: typer.Context,
    goal_path: Path = typer.Argument(..., help="Path to goal.yaml"),
) -> None:
    """Validate a goal contract file."""
    console.print(f"[yellow]validate-goal: {goal_path} (not yet implemented)[/yellow]")


@app.command()
def run(
    ctx: typer.Context,
    goal: Path = typer.Argument(..., help="Path to goal.yaml"),
    repo: Path = typer.Option(Path("."), "--repo", "-r", help="Path to target repository"),
    agent: str = typer.Option("scripted", "--agent", "-a", help="Agent type: scripted, google-adk, replay"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model override"),
    mode: str = typer.Option("constrained-verification", "--mode", help="Experiment mode"),
) -> None:
    """Execute a run against a target repository."""
    console.print(f"[yellow]run: {goal} repo={repo} agent={agent} mode={mode} (not yet implemented)[/yellow]")


@app.command()
def resume(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID to resume"),
) -> None:
    """Resume an interrupted run."""
    console.print(f"[yellow]resume: {run_id} (not yet implemented)[/yellow]")


@app.command()
def cancel(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID to cancel"),
) -> None:
    """Cancel a running or paused run."""
    console.print(f"[yellow]cancel: {run_id} (not yet implemented)[/yellow]")


if __name__ == "__main__":
    app()
