"""Inspect subcommands."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from constrained_agent.cli._common import load_candidate, load_run_data, run_async
from constrained_agent.reporting import RunReport
from constrained_agent.settings import Settings

inspect_app = typer.Typer(help="Inspect persisted run state")
console = Console()


@inspect_app.command("run")
def inspect_run(ctx: typer.Context, run_id: str = typer.Argument(..., help="Run ID")) -> None:
    """Show run details."""
    settings: Settings = ctx.obj["settings"]
    data = run_async(load_run_data(settings, run_id))
    report = RunReport.from_parts(
        data["run"],
        data["events"],
        data["evaluations"],
        data["manifest"],
        completion_manifest_ref=data["manifest_ref"],
    )
    console.print_json(json.dumps(report.model_dump(mode="json"), sort_keys=True))


@inspect_app.command("events")
def inspect_events(ctx: typer.Context, run_id: str = typer.Argument(..., help="Run ID")) -> None:
    """List persisted events for a run."""
    settings: Settings = ctx.obj["settings"]
    data = run_async(load_run_data(settings, run_id))
    table = Table(title=f"Events: {run_id}")
    table.add_column("Iteration")
    table.add_column("Type")
    table.add_column("Source")
    table.add_column("Target")
    table.add_column("Timestamp")
    for event in data["events"]:
        table.add_row(
            str(event.iteration),
            event.event_type,
            event.source_state or "-",
            event.target_state or "-",
            event.timestamp.isoformat(),
        )
    console.print(table)


@inspect_app.command("budget")
def inspect_budget(ctx: typer.Context, run_id: str = typer.Argument(..., help="Run ID")) -> None:
    """Show budget usage for a run."""
    settings: Settings = ctx.obj["settings"]
    data = run_async(load_run_data(settings, run_id))
    report = RunReport.from_parts(
        data["run"],
        data["events"],
        data["evaluations"],
        data["manifest"],
        completion_manifest_ref=data["manifest_ref"],
    )
    console.print_json(json.dumps(report.budget, sort_keys=True))


@inspect_app.command("candidate")
def inspect_candidate(
    ctx: typer.Context,
    candidate_id: str = typer.Argument(..., help="Candidate ID"),
) -> None:
    """Show candidate details."""
    settings: Settings = ctx.obj["settings"]
    candidate = run_async(load_candidate(settings, candidate_id))
    if candidate is None:
        raise typer.BadParameter(f"candidate not found: {candidate_id}")
    payload = {
        "id": candidate.id,
        "run_id": candidate.run_id,
        "repository_state_hash": candidate.repository_state_hash,
        "parent_id": candidate.parent_id,
        "depth": candidate.depth,
        "status": candidate.status,
        "iteration": candidate.iteration,
        "created_at": candidate.created_at.isoformat(),
    }
    console.print_json(json.dumps(payload, sort_keys=True))
