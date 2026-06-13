from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import copytree

import pytest

from constrained_agent.agents import AgentProposal, FileEdit, ScriptedAgent
from constrained_agent.artifacts import ArtifactStore
from constrained_agent.cli.experiment import PytestEvaluator, payment_contract, payment_fix_agent
from constrained_agent.controller import Controller, SqliteEventStore
from constrained_agent.domain import BudgetTracker, EvaluationResult, EvaluationTier
from constrained_agent.domain.evaluations import EvaluationVector
from constrained_agent.domain.events import EventType
from constrained_agent.evaluators import EvaluationContext, EvaluatorPipeline
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


class FlakyHiddenEvaluator:
    id = "hidden-flaky"
    tier = EvaluationTier.TIER_4_HIDDEN_AND_SECURITY

    def __init__(self) -> None:
        self._calls = 0

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        del context
        self._calls += 1
        return EvaluationResult(
            evaluator_id=self.id,
            tier=self.tier,
            passed=self._calls < 3,
            stdout="",
            stderr="",
            exit_code=0 if self._calls < 3 else 1,
            duration_seconds=0.01,
        )

    def merge_into(self, vector: EvaluationVector, result: EvaluationResult) -> None:
        vector.runtime_seconds += result.duration_seconds
        vector.hidden_tests_passed = (vector.hidden_tests_passed or 0) + int(result.passed)
        vector.hidden_tests_failed = (vector.hidden_tests_failed or 0) + int(not result.passed)


def _run_git(repository: Path, args: list[str]) -> None:
    subprocess.run(["git", *args], cwd=repository, check=True, capture_output=True, text=True)


@pytest.fixture
async def harness(tmp_path: Path) -> tuple[Path, DatabaseEngine, SqliteEventStore]:
    project_root = Path(__file__).resolve().parents[2]
    benchmark_root = project_root / "benchmarks" / "payment_webhook"
    source_repo = tmp_path / "source_repo"
    copytree(benchmark_root / "source_repo", source_repo)
    _run_git(source_repo, ["init", "-b", "main"])
    _run_git(source_repo, ["config", "user.name", "CAH Test"])
    _run_git(source_repo, ["config", "user.email", "cah@example.com"])
    _run_git(source_repo, ["add", "."])
    _run_git(source_repo, ["commit", "-m", "initial benchmark"])
    runtime_dir = tmp_path / ".cah"
    settings = Settings(database_url=f"sqlite:///{runtime_dir / 'e2e.db'}", runtime_dir=runtime_dir)
    engine = DatabaseEngine(settings)
    await engine.init_db()
    event_store = SqliteEventStore(
        run_repository=RunRepository(engine.get_session()),
        event_repository=EventRepository(engine.get_session()),
        candidate_repository=CandidateRepository(engine.get_session()),
        artifact_repository=ArtifactRepository(engine.get_session()),
        session_factory=engine.get_session(),
    )
    try:
        yield source_repo, engine, event_store
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_scripted_agent_successfully_fixes_benchmark(
    harness: tuple[Path, DatabaseEngine, SqliteEventStore],
) -> None:
    source_repo, _, event_store = harness
    benchmark_root = Path(__file__).resolve().parents[2] / "benchmarks" / "payment_webhook"
    runtime_dir = source_repo.parent / ".cah"
    repository_store = GitRepositoryStore(runtime_dir=runtime_dir, run_id="success")
    repository_store.initialize(source_repo)
    pipeline = EvaluatorPipeline()
    pipeline.register(PytestEvaluator())
    base_contract = payment_contract()
    contract = base_contract.model_copy(
        update={
            "constraints": base_contract.constraints.model_copy(update={"max_iterations": 1}),
        }
    )
    controller = Controller(
        goal_contract=contract,
        sandbox=FakeSandbox(),
        repository_store=repository_store,
        evaluator_pipeline=pipeline,
        agent=payment_fix_agent(benchmark_root / "reference_solution"),
        artifact_store=ArtifactStore(runtime_dir=runtime_dir, run_id="success"),
        event_store=event_store,
        budget_tracker=BudgetTracker(contract),
    )

    manifest = await controller.run()

    assert manifest is not None
    assert manifest.budget_usage.iterations_consumed >= 1
    assert manifest.final_evaluation_vector["visible_tests_passed"] == 1


@pytest.mark.asyncio
async def test_policy_enforcement_attempted_protected_edit_is_rejected(
    harness: tuple[Path, DatabaseEngine, SqliteEventStore],
) -> None:
    source_repo, _, event_store = harness
    runtime_dir = source_repo.parent / ".cah"
    repository_store = GitRepositoryStore(runtime_dir=runtime_dir, run_id="protected")
    repository_store.initialize(source_repo)
    agent = ScriptedAgent(
        [
            AgentProposal(
                summary="Edit a protected test file.",
                hypothesis="This should be rejected.",
                evidence_considered=["policy test"],
                files_to_inspect=["tests/test_webhook.py"],
                edits=[
                    FileEdit(
                        path="tests/test_webhook.py",
                        operation="replace",
                        content="print('forbidden')\n",
                    )
                ],
                commands=[],
                expected_effect="policy reject",
                risk_notes=[],
                completion_claimed=False,
                write_files=["tests/test_webhook.py"],
            )
        ]
    )
    pipeline = EvaluatorPipeline()
    pipeline.register(PytestEvaluator())
    base_contract = payment_contract()
    contract = base_contract.model_copy(
        update={
            "constraints": base_contract.constraints.model_copy(update={"max_iterations": 1}),
        }
    )
    controller = Controller(
        goal_contract=contract,
        sandbox=FakeSandbox(),
        repository_store=repository_store,
        evaluator_pipeline=pipeline,
        agent=agent,
        artifact_store=ArtifactStore(runtime_dir=runtime_dir, run_id="protected"),
        event_store=event_store,
        budget_tracker=BudgetTracker(contract),
    )

    manifest = await controller.run()

    assert manifest is None
    run_id = next(iter(event_store._events))
    policy_events = [
        event
        for event in event_store.list_events(run_id)
        if event.event_type == EventType.POLICY_CHECK
    ]
    assert policy_events
    assert policy_events[-1].payload["allowed"] is False


@pytest.mark.asyncio
async def test_false_completion_hidden_tests_fail_and_completion_is_refused(
    harness: tuple[Path, DatabaseEngine, SqliteEventStore],
) -> None:
    source_repo, _, event_store = harness
    benchmark_root = Path(__file__).resolve().parents[2] / "benchmarks" / "payment_webhook"
    runtime_dir = source_repo.parent / ".cah"
    repository_store = GitRepositoryStore(runtime_dir=runtime_dir, run_id="false-completion")
    repository_store.initialize(source_repo)
    pipeline = EvaluatorPipeline()
    pipeline.register(PytestEvaluator())
    pipeline.register(FlakyHiddenEvaluator())
    base_contract = payment_contract()
    contract = base_contract.model_copy(
        update={
            "constraints": base_contract.constraints.model_copy(update={"max_iterations": 1}),
        }
    )
    controller = Controller(
        goal_contract=contract,
        sandbox=FakeSandbox(),
        repository_store=repository_store,
        evaluator_pipeline=pipeline,
        agent=payment_fix_agent(benchmark_root / "reference_solution"),
        artifact_store=ArtifactStore(runtime_dir=runtime_dir, run_id="false-completion"),
        event_store=event_store,
        budget_tracker=BudgetTracker(contract),
    )

    manifest = await controller.run()

    assert manifest is None
    run_id = next(iter(event_store._events))
    transitions = [
        event
        for event in event_store.list_events(run_id)
        if event.event_type == EventType.STATE_TRANSITION
    ]
    assert any(event.target_state == "VERIFYING_COMPLETION" for event in transitions)
    assert all(event.target_state != "COMPLETED" for event in transitions)


@pytest.mark.asyncio
async def test_budget_exhaustion_terminates_cleanly(
    harness: tuple[Path, DatabaseEngine, SqliteEventStore],
) -> None:
    source_repo, _, event_store = harness
    runtime_dir = source_repo.parent / ".cah"
    repository_store = GitRepositoryStore(runtime_dir=runtime_dir, run_id="budget")
    repository_store.initialize(source_repo)
    base_contract = payment_contract()
    contract = base_contract.model_copy(
        update={
            "constraints": base_contract.constraints.model_copy(update={"max_iterations": 1}),
        }
    )
    agent = ScriptedAgent(
        [
            AgentProposal(
                summary="Make no change.",
                hypothesis="Budget should exhaust.",
                evidence_considered=["baseline failure"],
                files_to_inspect=["src/app.py"],
                edits=[],
                commands=[],
                expected_effect="none",
                risk_notes=[],
                completion_claimed=False,
                write_files=[],
            ),
            AgentProposal(
                summary="Still no change.",
                hypothesis="Second iteration should not be reached cleanly.",
                evidence_considered=["baseline failure"],
                files_to_inspect=["src/app.py"],
                edits=[],
                commands=[],
                expected_effect="none",
                risk_notes=[],
                completion_claimed=False,
                write_files=[],
            ),
        ]
    )
    pipeline = EvaluatorPipeline()
    pipeline.register(PytestEvaluator())
    controller = Controller(
        goal_contract=contract,
        sandbox=FakeSandbox(),
        repository_store=repository_store,
        evaluator_pipeline=pipeline,
        agent=agent,
        artifact_store=ArtifactStore(runtime_dir=runtime_dir, run_id="budget"),
        event_store=event_store,
        budget_tracker=BudgetTracker(contract),
    )

    manifest = await controller.run()

    assert manifest is None
    run_id = next(iter(event_store._events))
    assert event_store.list_events(run_id)[-1].target_state == "CANCELLED"
