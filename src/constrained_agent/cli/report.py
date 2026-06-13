"""Report and artifact verification commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from constrained_agent.artifacts import ArtifactStore, verify_manifest
from constrained_agent.cli._common import load_run_data, run_async
from constrained_agent.persistence import DatabaseEngine
from constrained_agent.persistence.models import RunModel
from constrained_agent.reporting import generate_json_report, generate_markdown_report
from constrained_agent.settings import Settings
from constrained_agent.telemetry.run_summary import RunSummary

report_app = typer.Typer(help="Generate reports")
artifacts_app = typer.Typer(help="Verify artifacts")
console = Console()


@report_app.command("run")
def report_run(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    format: str = typer.Option("markdown", "--format", help="markdown or json"),
) -> None:
    """Generate a run report."""
    settings: Settings = ctx.obj["settings"]
    data = run_async(load_run_data(settings, run_id))
    if format == "json":
        console.print(
            generate_json_report(
                data["run"],
                data["events"],
                data["evaluations"],
                data["manifest"],
            )
        )
        return
    console.print(
        generate_markdown_report(
            data["run"],
            data["events"],
            data["evaluations"],
            data["manifest"],
        )
    )


@artifacts_app.command("verify")
def verify_artifacts(ctx: typer.Context, run_id: str = typer.Argument(..., help="Run ID")) -> None:
    """Verify the artifact hash chain for a run."""
    settings: Settings = ctx.obj["settings"]
    data = run_async(load_run_data(settings, run_id))
    manifest = data["manifest"]
    if manifest is None:
        raise typer.BadParameter(f"completion manifest not found for run: {run_id}")
    artifact_store = ArtifactStore(runtime_dir=Path(settings.runtime_dir), run_id=run_id)
    verified = verify_manifest(manifest, artifact_store)
    console.print(json.dumps({"run_id": run_id, "verified": verified}))


@report_app.command("compare")
def report_compare(
    ctx: typer.Context,
    run_id_a: str = typer.Argument(..., help="First run ID"),
    run_id_b: str = typer.Argument(..., help="Second run ID"),
) -> None:
    """Compare two runs side-by-side."""
    settings: Settings = ctx.obj["settings"]
    try:
        data_a = run_async(load_run_data(settings, run_id_a))
        data_b = run_async(load_run_data(settings, run_id_b))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    summary_a = RunSummary.from_events(
        run_id_a, data_a["events"],
        start_time=data_a["run"].created_at,
        end_time=data_a["run"].updated_at,
    )
    summary_b = RunSummary.from_events(
        run_id_b, data_b["events"],
        start_time=data_b["run"].created_at,
        end_time=data_b["run"].updated_at,
    )

    table = Table(title="Run Comparison")
    table.add_column("Metric", style="bold cyan")
    table.add_column(f"Run A ({run_id_a[:8]})", style="yellow")
    table.add_column(f"Run B ({run_id_b[:8]})", style="green")

    table.add_row("Status", data_a["run"].status, data_b["run"].status)
    table.add_row("Iterations", str(summary_a.total_iterations), str(summary_b.total_iterations))
    table.add_row(
        "Duration (s)",
        f"{summary_a.duration_seconds:.1f}",
        f"{summary_b.duration_seconds:.1f}",
    )
    table.add_row("Model Calls", str(summary_a.model_calls), str(summary_b.model_calls))
    table.add_row(
        "Tokens",
        str(summary_a.total_token_estimate),
        str(summary_b.total_token_estimate),
    )
    table.add_row("Evaluator P/F", f"{summary_a.evaluator_passes}P/{summary_a.evaluator_failures}F",
                  f"{summary_b.evaluator_passes}P/{summary_b.evaluator_failures}F")
    table.add_row("Approval", summary_a.final_approval_status or "running",
                  summary_b.final_approval_status or "running")
    table.add_row("Artifacts", str(summary_a.artifact_count), str(summary_b.artifact_count))
    table.add_row("Decisions", str(dict(summary_a.decisions)), str(dict(summary_b.decisions)))

    console.print(table)


@report_app.command("experiment")
def report_experiment(
    ctx: typer.Context,
    experiment_mode: str = typer.Argument(..., help="Experiment mode to filter runs by"),
) -> None:
    """List all runs matching an experiment mode."""
    settings: Settings = ctx.obj["settings"]

    async def _load() -> list[dict[str, Any]]:
        engine = DatabaseEngine(settings)
        try:
            async with engine.get_session()() as session:
                result = await session.scalars(
                    select(RunModel)
                    .where(RunModel.experiment_mode == experiment_mode)
                    .order_by(RunModel.created_at)
                )
                runs = result.all()
            rows: list[dict[str, Any]] = []
            for run in runs:
                try:
                    data = await load_run_data(settings, run.id)
                except ValueError:
                    continue
                summary = RunSummary.from_events(
                    run.id, data["events"],
                    start_time=run.created_at,
                    end_time=run.updated_at,
                )
                rows.append({
                    "run_id": run.id[:8],
                    "status": run.status,
                    "iterations": summary.total_iterations,
                    "duration": round(summary.duration_seconds, 1),
                    "approval": summary.final_approval_status or "running",
                    "pass": summary.evaluator_passes,
                    "fail": summary.evaluator_failures,
                    "artifacts": summary.artifact_count,
                    "tokens": summary.total_token_estimate,
                })
            return rows
        finally:
            await engine.dispose()

    rows = run_async(_load())
    if not rows:
        console.print(f"[yellow]No runs found for experiment mode: {experiment_mode}[/yellow]")
        return

    table = Table(title=f"Experiment: {experiment_mode}")
    table.add_column("Run ID", style="cyan")
    table.add_column("Status")
    table.add_column("Iterations", justify="right")
    table.add_column("Duration (s)", justify="right")
    table.add_column("Approval")
    table.add_column("Eval P/F")
    table.add_column("Artifacts", justify="right")
    table.add_column("Tokens", justify="right")

    for row in rows:
        table.add_row(
            row["run_id"],
            row["status"],
            str(row["iterations"]),
            str(row["duration"]),
            row["approval"],
            f"{row['pass']}P/{row['fail']}F",
            str(row["artifacts"]),
            str(row["tokens"]),
        )

    console.print(table)
