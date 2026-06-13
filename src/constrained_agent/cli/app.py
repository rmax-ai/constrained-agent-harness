"""CLI entry point using Typer."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from constrained_agent import __version__
from constrained_agent.cli._common import upgrade_database
from constrained_agent.cli.benchmark import benchmark_app
from constrained_agent.cli.doctor import doctor_command
from constrained_agent.cli.experiment import experiment_app
from constrained_agent.cli.inspect import inspect_app
from constrained_agent.cli.report import artifacts_app, report_app
from constrained_agent.logging import configure_logging
from constrained_agent.settings import Settings

app = typer.Typer(
    name="cah",
    help="constrained-agent-harness — bounded, verifiable coding agent execution",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"constrained-agent-harness v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    log_level: str | None = typer.Option(None, "--log-level", help="Log level override"),
) -> None:
    """CAH: constrained-agent-harness CLI."""
    del version
    settings = Settings()
    level = log_level or settings.log_level
    configure_logging(level if not verbose else "DEBUG")
    ctx.obj = {"settings": settings, "verbose": verbose}


app.command("doctor")(doctor_command)
app.add_typer(inspect_app, name="inspect")
app.add_typer(report_app, name="report")
app.add_typer(artifacts_app, name="artifacts")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(experiment_app, name="experiment")


@app.command()
def init(
    ctx: typer.Context,
    path: Path = typer.Option(".", "--path", "-p", help="Project path"),  # noqa: B008
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
    goal_path: Path = typer.Argument(..., help="Path to goal.yaml"),  # noqa: B008
) -> None:
    """Validate a goal contract file."""
    del ctx
    console.print(f"[yellow]validate-goal: {goal_path} (not yet implemented)[/yellow]")


@app.command()
def run(
    ctx: typer.Context,
    goal: Path = typer.Argument(..., help="Path to goal.yaml"),  # noqa: B008
    repo: Path = typer.Option(  # noqa: B008
        Path("."),
        "--repo",
        "-r",
        help="Path to target repository",
    ),
    agent: str = typer.Option(
        "scripted", "--agent", "-a", help="Agent type: scripted, google-adk, replay"
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="Model override"),
    mode: str = typer.Option("constrained-verification", "--mode", help="Experiment mode"),
) -> None:
    """Execute a run against a target repository."""
    del ctx, model
    console.print(
        f"[yellow]run: {goal} repo={repo} agent={agent} mode={mode} (not yet implemented)[/yellow]"
    )


@app.command()
def resume(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID to resume"),
) -> None:
    """Resume an interrupted run."""
    del ctx
    console.print(f"[yellow]resume: {run_id} (not yet implemented)[/yellow]")


@app.command()
def cancel(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID to cancel"),
) -> None:
    """Cancel a running or paused run."""
    del ctx
    console.print(f"[yellow]cancel: {run_id} (not yet implemented)[/yellow]")


db_app = typer.Typer(help="Database utilities")


@db_app.command("upgrade")
def db_upgrade(ctx: typer.Context) -> None:
    """Run database schema upgrades."""
    settings: Settings = ctx.obj["settings"]
    del ctx
    upgrade_database(settings)
    console.print(f"[green]database upgraded at {settings.database_url}[/green]")


app.add_typer(db_app, name="db")


if __name__ == "__main__":
    app()
