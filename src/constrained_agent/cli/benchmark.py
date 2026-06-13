"""Benchmark validation commands."""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console

benchmark_app = typer.Typer(help="Benchmark utilities")
console = Console()


def validate_benchmark_path(path: Path) -> list[str]:
    """Return benchmark validation failures."""
    errors: list[str] = []
    benchmark_root = path.resolve()
    required_paths = [
        benchmark_root / "benchmark_manifest.yaml",
        benchmark_root / "goal.yaml",
        benchmark_root / "source_repo",
        benchmark_root / "source_repo" / "src" / "app.py",
        benchmark_root / "source_repo" / "tests" / "test_webhook.py",
        benchmark_root / "protected_tests",
        benchmark_root / "reference_solution" / "src" / "app.py",
    ]
    for required in required_paths:
        if not required.exists():
            errors.append(f"missing required path: {required}")

    if errors:
        return errors

    try:
        manifest = yaml.safe_load((benchmark_root / "benchmark_manifest.yaml").read_text())
        goal = yaml.safe_load((benchmark_root / "goal.yaml").read_text())
    except (OSError, yaml.YAMLError) as exc:
        return [f"failed to parse manifest or goal: {exc}"]

    if not isinstance(manifest, dict):
        errors.append("benchmark_manifest.yaml must contain a mapping")
    if not isinstance(goal, dict):
        errors.append("goal.yaml must contain a mapping")

    source_repo = benchmark_root / "source_repo"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_webhook.py"],
        cwd=source_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        errors.append("visible tests should fail before the benchmark is solved")

    protected_tests = benchmark_root / "protected_tests"
    for candidate in [protected_tests, *protected_tests.rglob("*")]:
        mode = candidate.stat().st_mode
        if mode & stat.S_IWUSR:
            errors.append(f"owner-writable protected path: {candidate}")
        if mode & stat.S_IWGRP:
            errors.append(f"group-writable protected path: {candidate}")
        if mode & stat.S_IWOTH:
            errors.append(f"world-writable protected path: {candidate}")

    if not (benchmark_root / "reference_solution").is_dir():
        errors.append("reference_solution directory is missing")

    return errors


@benchmark_app.command("validate")
def validate_benchmark(
    name: str = typer.Argument(..., help="Benchmark name or path"),
) -> None:
    """Validate benchmark integrity."""
    candidate = Path(name)
    benchmark_root = candidate if candidate.exists() else Path("benchmarks") / name
    errors = validate_benchmark_path(benchmark_root)
    if errors:
        for error in errors:
            console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]benchmark valid: {benchmark_root}[/green]")
