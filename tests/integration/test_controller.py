from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from constrained_agent.agents import AgentProposal, FileEdit, ScriptedAgent
from constrained_agent.artifacts import ArtifactStore, verify_manifest
from constrained_agent.controller import Controller, SqliteEventStore
from constrained_agent.domain import BudgetTracker, EvaluationResult, EvaluationTier, GoalContract
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


def _run_git(repository: Path, args: list[str]) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _create_source_repo(tmp_path: Path) -> Path:
    repository = tmp_path / "source"
    repository.mkdir()
    _run_git(repository, ["init", "-b", "main"])
    _run_git(repository, ["config", "user.name", "CAH Test"])
    _run_git(repository, ["config", "user.email", "cah@example.com"])
    (repository / "src").mkdir()
    (repository / "src" / "app.py").write_text("VALUE = 'old'\n", encoding="utf-8")
    _run_git(repository, ["add", "src/app.py"])
    _run_git(repository, ["commit", "-m", "initial"])
    return repository


def _make_contract(*, max_iterations: int = 3) -> GoalContract:
    return GoalContract.model_validate(
        {
            "schema_version": "1",
            "task": {
                "id": "task-1",
                "title": "Update app value",
                "description": "Change src/app.py so the evaluator sees VALUE = 'new'.",
            },
            "model": {
                "provider": "test",
                "name": "scripted",
                "temperature": 0.0,
            },
            "acceptance": {
                "required_checks": [
                    {
                        "id": "visible-source-check",
                        "evaluator": "source-value",
                        "command": ["python", "-c", "print('placeholder')"],
                        "expected_exit_code": 0,
                        "blocking": True,
                    }
                ],
                "hidden_checks": None,
            },
            "constraints": {
                "max_iterations": max_iterations,
                "max_runtime_seconds": 60,
                "max_model_calls": 5,
                "writable_paths": ["src/**"],
                "protected_paths": [],
                "allowed_commands": [["python"]],
                "forbidden_patterns": [],
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


class SourceValueEvaluator:
    id = "source-value"
    tier = EvaluationTier.TIER_2_TARGETED_TESTS

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        content = (context.workspace / "src" / "app.py").read_text(encoding="utf-8")
        passed = "VALUE = 'new'" in content
        return EvaluationResult(
            evaluator_id=self.id,
            tier=self.tier,
            passed=passed,
            stdout="new value present" if passed else "new value missing",
            stderr="",
            exit_code=0 if passed else 1,
            duration_seconds=0.01,
        )

    def merge_into(self, vector: EvaluationVector, result: EvaluationResult) -> None:
        vector.runtime_seconds += result.duration_seconds
        if result.passed:
            vector.visible_tests_passed += 1
        else:
            vector.visible_tests_failed += 1


@pytest.fixture
async def sqlite_event_store(tmp_path: Path) -> tuple[DatabaseEngine, SqliteEventStore]:
    database_path = tmp_path / "controller.db"
    engine = DatabaseEngine(Settings(database_url=f"sqlite:///{database_path}"))
    await engine.init_db()
    store = SqliteEventStore(
        run_repository=RunRepository(engine.get_session()),
        event_repository=EventRepository(engine.get_session()),
        candidate_repository=CandidateRepository(engine.get_session()),
        artifact_repository=ArtifactRepository(engine.get_session()),
        session_factory=engine.get_session(),
    )
    try:
        yield engine, store
    finally:
        await engine.dispose()


def _make_pipeline() -> EvaluatorPipeline:
    pipeline = EvaluatorPipeline()
    pipeline.register(SourceValueEvaluator())
    return pipeline


def _make_success_agent() -> ScriptedAgent:
    return ScriptedAgent(
        [
            AgentProposal(
                summary="Update the constant.",
                hypothesis="Changing the value satisfies the evaluator.",
                evidence_considered=["visible evaluator"],
                files_to_inspect=["src/app.py"],
                edits=[
                    FileEdit(
                        path="src/app.py",
                        operation="replace",
                        content="VALUE = 'new'\n",
                    )
                ],
                commands=[],
                expected_effect="visible checks pass",
                risk_notes=[],
                completion_claimed=True,
                write_files=["src/app.py"],
            )
        ]
    )


def _make_unsuccessful_agent() -> ScriptedAgent:
    return ScriptedAgent(
        [
            AgentProposal(
                summary="Do not fix the file yet.",
                hypothesis="Another iteration may be needed.",
                evidence_considered=["baseline evaluator failure"],
                files_to_inspect=["src/app.py"],
                edits=[],
                commands=[],
                expected_effect="no change",
                risk_notes=[],
                completion_claimed=False,
                write_files=[],
            ),
            AgentProposal(
                summary="Still do not fix the file.",
                hypothesis="Budget should terminate cleanly.",
                evidence_considered=["previous failure"],
                files_to_inspect=["src/app.py"],
                edits=[],
                commands=[],
                expected_effect="no change",
                risk_notes=[],
                completion_claimed=False,
                write_files=[],
            ),
        ]
    )


@pytest.mark.asyncio
async def test_controller_orchestrates_full_run_lifecycle(
    tmp_path: Path,
    sqlite_event_store: tuple[DatabaseEngine, SqliteEventStore],
) -> None:
    _, event_store = sqlite_event_store
    source = _create_source_repo(tmp_path)
    repository_store = GitRepositoryStore(runtime_dir=tmp_path / ".cah", run_id="run-success")
    repository_store.initialize(source)
    artifact_store = ArtifactStore(runtime_dir=tmp_path / ".cah", run_id="run-success")
    controller = Controller(
        goal_contract=_make_contract(),
        sandbox=FakeSandbox(),
        repository_store=repository_store,
        evaluator_pipeline=_make_pipeline(),
        agent=_make_success_agent(),
        artifact_store=artifact_store,
        event_store=event_store,
        budget_tracker=BudgetTracker(_make_contract()),
    )

    manifest = await controller.run()

    assert manifest is not None
    assert (
        repository_store.workspace.joinpath("src/app.py").read_text(encoding="utf-8")
        == "VALUE = 'new'\n"
    )
    assert manifest.final_evaluation_vector["visible_tests_passed"] == 1
    assert verify_manifest(manifest, artifact_store) is True


@pytest.mark.asyncio
async def test_transition_decisions_are_persisted(
    tmp_path: Path,
    sqlite_event_store: tuple[DatabaseEngine, SqliteEventStore],
) -> None:
    _, event_store = sqlite_event_store
    source = _create_source_repo(tmp_path)
    repository_store = GitRepositoryStore(runtime_dir=tmp_path / ".cah", run_id="run-events")
    repository_store.initialize(source)
    controller = Controller(
        goal_contract=_make_contract(),
        sandbox=FakeSandbox(),
        repository_store=repository_store,
        evaluator_pipeline=_make_pipeline(),
        agent=_make_success_agent(),
        artifact_store=ArtifactStore(runtime_dir=tmp_path / ".cah", run_id="run-events"),
        event_store=event_store,
        budget_tracker=BudgetTracker(_make_contract()),
    )

    await controller.run()
    run_id = next(iter(event_store._events))
    await event_store.load_snapshots(run_id)
    persisted_types = [event.event_type for event in event_store.list_events(run_id)]

    assert EventType.TRANSITION_DECIDED in persisted_types
    assert EventType.COMPLETION_DECLARED in persisted_types


@pytest.mark.asyncio
async def test_budget_exhaustion_terminates_cleanly(
    tmp_path: Path,
    sqlite_event_store: tuple[DatabaseEngine, SqliteEventStore],
) -> None:
    _, event_store = sqlite_event_store
    source = _create_source_repo(tmp_path)
    repository_store = GitRepositoryStore(runtime_dir=tmp_path / ".cah", run_id="run-budget")
    repository_store.initialize(source)
    contract = _make_contract(max_iterations=1)
    controller = Controller(
        goal_contract=contract,
        sandbox=FakeSandbox(),
        repository_store=repository_store,
        evaluator_pipeline=_make_pipeline(),
        agent=_make_unsuccessful_agent(),
        artifact_store=ArtifactStore(runtime_dir=tmp_path / ".cah", run_id="run-budget"),
        event_store=event_store,
        budget_tracker=BudgetTracker(contract),
    )

    manifest = await controller.run()

    assert manifest is None
    run_id = next(iter(event_store._events))
    final_event = event_store.list_events(run_id)[-1]
    assert final_event.target_state == "CANCELLED"


@pytest.mark.asyncio
async def test_completion_manifest_is_produced_and_verifiable(
    tmp_path: Path,
    sqlite_event_store: tuple[DatabaseEngine, SqliteEventStore],
) -> None:
    _, event_store = sqlite_event_store
    source = _create_source_repo(tmp_path)
    repository_store = GitRepositoryStore(runtime_dir=tmp_path / ".cah", run_id="run-manifest")
    repository_store.initialize(source)
    artifact_store = ArtifactStore(runtime_dir=tmp_path / ".cah", run_id="run-manifest")
    controller = Controller(
        goal_contract=_make_contract(),
        sandbox=FakeSandbox(),
        repository_store=repository_store,
        evaluator_pipeline=_make_pipeline(),
        agent=_make_success_agent(),
        artifact_store=artifact_store,
        event_store=event_store,
        budget_tracker=BudgetTracker(_make_contract()),
    )

    manifest = await controller.run()

    assert manifest is not None
    assert manifest.event_chain_head_hash != ""
    assert len(manifest.artifact_hashes) >= 1
    assert verify_manifest(manifest, artifact_store) is True
