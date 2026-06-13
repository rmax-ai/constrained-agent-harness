"""Report and artifact verification commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from constrained_agent.artifacts import ArtifactStore, verify_manifest
from constrained_agent.cli._common import load_run_data, run_async
from constrained_agent.reporting import generate_json_report, generate_markdown_report
from constrained_agent.settings import Settings

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
