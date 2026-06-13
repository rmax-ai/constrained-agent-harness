from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from shutil import copytree

from constrained_agent.artifacts import ArtifactStore
from constrained_agent.cli.experiment import PytestEvaluator, payment_contract, payment_fix_agent
from constrained_agent.controller import Controller, SqliteEventStore
from constrained_agent.domain import BudgetTracker
from constrained_agent.evaluators import EvaluatorPipeline
from constrained_agent.persistence import DatabaseEngine
from constrained_agent.persistence.repositories import (
    ArtifactRepository,
    CandidateRepository,
    EventRepository,
    RunRepository,
)
from constrained_agent.repository import GitRepositoryStore
from constrained_agent.sandbox import FakeSandbox
from constrained_agent.settings import Settings


async def _run() -> int:
    project_root = Path(__file__).resolve().parents[1]
    benchmark_root = project_root / "benchmarks" / "payment_webhook"
    with tempfile.TemporaryDirectory(prefix="cah-smoke-") as temp_dir:
        temp_root = Path(temp_dir)
        source_repo = temp_root / "source_repo"
        copytree(benchmark_root / "source_repo", source_repo)
        runtime_dir = temp_root / ".cah"
        settings = Settings(
            runtime_dir=runtime_dir,
            database_url=f"sqlite:///{runtime_dir / 'smoke.db'}",
        )
        engine = DatabaseEngine(settings)
        await engine.init_db()
        event_store = SqliteEventStore(
            run_repository=RunRepository(engine.get_session()),
            event_repository=EventRepository(engine.get_session()),
            candidate_repository=CandidateRepository(engine.get_session()),
            artifact_repository=ArtifactRepository(engine.get_session()),
            session_factory=engine.get_session(),
        )
        repository_store = GitRepositoryStore(runtime_dir=runtime_dir, run_id="smoke")
        repository_store.initialize(source_repo)
        pipeline = EvaluatorPipeline()
        pipeline.register(PytestEvaluator())
        contract = payment_contract()
        controller = Controller(
            goal_contract=contract,
            sandbox=FakeSandbox(),
            repository_store=repository_store,
            evaluator_pipeline=pipeline,
            agent=payment_fix_agent(benchmark_root / "reference_solution"),
            artifact_store=ArtifactStore(runtime_dir=runtime_dir, run_id="smoke"),
            event_store=event_store,
            budget_tracker=BudgetTracker(contract),
        )
        manifest = await controller.run()
        if manifest is None:
            print("smoke test failed: no completion manifest produced")
            await engine.dispose()
            return 1
        if manifest.budget_usage.iterations_consumed <= 0:
            print("smoke test failed: budget iterations were not recorded")
            await engine.dispose()
            return 1
        print(f"smoke test passed: run_id={manifest.run_id}")
        await engine.dispose()
        return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
