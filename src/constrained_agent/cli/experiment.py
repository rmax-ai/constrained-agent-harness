"""Experiment runner commands."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from shutil import copytree

import typer
from rich.console import Console

from constrained_agent.agents import AgentProposal, FileEdit, ScriptedAgent
from constrained_agent.artifacts import ArtifactStore
from constrained_agent.controller import Controller, SqliteEventStore
from constrained_agent.domain import (
    BudgetTracker,
    EvaluationResult,
    EvaluationTier,
    GoalContract,
)
from constrained_agent.domain.evaluations import EvaluationVector
from constrained_agent.evaluators import EvaluationContext, EvaluatorPipeline
from constrained_agent.persistence import DatabaseEngine
from constrained_agent.persistence.repositories import (
    ArtifactRepository,
    CandidateRepository,
    EventRepository,
    RunRepository,
)
from constrained_agent.reporting import compute_experiment_metrics, compute_run_metrics
from constrained_agent.repository import GitRepositoryStore
from constrained_agent.sandbox import FakeSandbox
from constrained_agent.settings import Settings

experiment_app = typer.Typer(help="Experiment runner")
console = Console()


class PytestEvaluator:
    """Run visible tests against the benchmark workspace."""

    id = "visible-pytest"
    tier = EvaluationTier.TIER_2_TARGETED_TESTS

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        import asyncio
        import time

        started = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_webhook.py",
            cwd=str(context.workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        passed = process.returncode == 0
        return EvaluationResult(
            evaluator_id=self.id,
            tier=self.tier,
            passed=passed,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
            exit_code=int(process.returncode or 0),
            duration_seconds=time.perf_counter() - started,
        )

    def merge_into(self, vector: EvaluationVector, result: EvaluationResult) -> None:
        vector.runtime_seconds += result.duration_seconds
        if result.passed:
            vector.visible_tests_passed += 1
        else:
            vector.visible_tests_failed += 1


def payment_contract() -> GoalContract:
    """Return a controller-compatible contract for the payment benchmark."""
    return GoalContract.model_validate(
        {
            "schema_version": "1",
            "task": {
                "id": "payment-webhook-idempotency",
                "title": "Prevent duplicate payment creation",
                "description": "Fix duplicate webhook handling in src/.",
            },
            "model": {"provider": "scripted", "name": "scripted", "temperature": 0.0},
            "acceptance": {
                "required_checks": [
                    {
                        "id": "visible",
                        "evaluator": "pytest",
                        "command": [sys.executable, "-m", "pytest", "-q", "tests/test_webhook.py"],
                    }
                ],
                "hidden_checks": None,
            },
            "constraints": {
                "max_iterations": 3,
                "max_runtime_seconds": 600,
                "max_model_calls": 3,
                "writable_paths": ["src/**"],
                "protected_paths": ["tests/**", "pyproject.toml"],
                "allowed_commands": [["uv"], ["python"], ["git"]],
                "forbidden_patterns": ["rm -rf", "curl", "wget"],
                "network_mode": "off",
                "dependency_policy": "frozen",
            },
            "approval_gates": [],
            "termination": {
                "success_conditions": ["visible checks pass"],
                "failure_conditions": ["budget exhausted"],
            },
            "experiment": {
                "context_strategy": "full",
                "completion_strategy": "controller_verified",
                "checkpoint_strategy": "per_iteration",
                "branching_factor": 1,
            },
        }
    )


def payment_fix_agent(reference_repo: Path) -> ScriptedAgent:
    """Return a scripted agent that applies the reference fix."""
    edits: list[FileEdit] = []
    for relative_path in ["src/app.py", "src/database.py"]:
        edits.append(
            FileEdit(
                path=relative_path,
                operation="replace",
                content=(reference_repo / relative_path).read_text(encoding="utf-8"),
            )
        )
    return ScriptedAgent(
        [
            AgentProposal(
                summary="Apply the idempotency fix from the reference solution.",
                hypothesis=(
                    "The database must enforce uniqueness and the app must reuse existing rows."
                ),
                evidence_considered=["visible benchmark tests"],
                files_to_inspect=["src/app.py", "src/database.py"],
                edits=edits,
                commands=[],
                expected_effect="visible tests pass",
                risk_notes=[],
                completion_claimed=True,
                write_files=["src/app.py", "src/database.py"],
            )
        ]
    )


@experiment_app.command("run")
def experiment_run(
    repetitions: int = typer.Option(1, "--repetitions", min=1),
    benchmark: str = typer.Option("payment_webhook", "--benchmark"),
) -> None:
    """Run a scripted benchmark experiment multiple times."""
    import asyncio

    metrics = asyncio.run(_run_experiment(repetitions=repetitions, benchmark=benchmark))
    console.print(metrics.to_terminal_summary())
    console.print(metrics.to_json())


async def _run_experiment(repetitions: int, benchmark: str) -> object:
    benchmark_root = Path("benchmarks") / benchmark
    per_run_metrics: list[dict[str, object]] = []
    for index in range(repetitions):
        with tempfile.TemporaryDirectory(prefix=f"cah-exp-{index}-") as temp_dir:
            temp_root = Path(temp_dir)
            source = temp_root / "source_repo"
            copytree(benchmark_root / "source_repo", source)
            runtime_dir = temp_root / ".cah"
            database_path = runtime_dir / "experiment.db"
            settings = Settings(database_url=f"sqlite:///{database_path}", runtime_dir=runtime_dir)
            engine = DatabaseEngine(settings)
            await engine.init_db()
            store = SqliteEventStore(
                run_repository=RunRepository(engine.get_session()),
                event_repository=EventRepository(engine.get_session()),
                candidate_repository=CandidateRepository(engine.get_session()),
                artifact_repository=ArtifactRepository(engine.get_session()),
                session_factory=engine.get_session(),
            )
            repository_store = GitRepositoryStore(runtime_dir=runtime_dir, run_id=f"exp-{index}")
            repository_store.initialize(source)
            pipeline = EvaluatorPipeline()
            pipeline.register(PytestEvaluator())
            contract = payment_contract()
            controller = Controller(
                goal_contract=contract,
                sandbox=FakeSandbox(),
                repository_store=repository_store,
                evaluator_pipeline=pipeline,
                agent=payment_fix_agent(benchmark_root / "reference_solution"),
                artifact_store=ArtifactStore(runtime_dir=runtime_dir, run_id=f"exp-{index}"),
                event_store=store,
                budget_tracker=BudgetTracker(contract),
            )
            await controller.run()
            run_model = (await RunRepository(engine.get_session()).list())[0]
            await store.load_snapshots(run_model.id)
            metrics = compute_run_metrics(
                run_model,
                store.list_candidates(run_model.id),
                store.list_events(run_model.id),
            )
            per_run_metrics.append(metrics)
            await engine.dispose()
    return compute_experiment_metrics(per_run_metrics, mode="scripted-benchmark")
