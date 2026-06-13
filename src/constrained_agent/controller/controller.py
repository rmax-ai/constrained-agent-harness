"""Controller assembly for full constrained-run orchestration."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from constrained_agent.agents.protocol import AgentContext, AgentProposal, FileEdit
from constrained_agent.artifacts import ArtifactStore, CompletionManifest, generate_manifest
from constrained_agent.domain.budgets import BudgetTracker
from constrained_agent.domain.candidates import Candidate, CandidateStatus
from constrained_agent.domain.contracts import ContractValidator, GoalContract
from constrained_agent.domain.evaluations import EvaluationVector
from constrained_agent.domain.events import Event, EventType, TransitionDecision, TransitionEvent
from constrained_agent.domain.evidence import ArtifactRef
from constrained_agent.domain.runs import Run, RunStatus
from constrained_agent.errors import (
    BudgetExceededError,
    GoalValidationError,
    RepositoryStateError,
)
from constrained_agent.evaluators.pipeline import EvaluatorPipeline
from constrained_agent.evaluators.protocol import EvaluationContext
from constrained_agent.persistence.models import EvaluationModel
from constrained_agent.persistence.repositories import (
    ArtifactRepository,
    CandidateRepository,
    EventRepository,
    RunRepository,
)
from constrained_agent.policy import PolicyEngine
from constrained_agent.repository.protocol import RepositoryState, RepositoryStore
from constrained_agent.sandbox.protocol import ExecutionRequest, Sandbox

from .state_machine import ControllerState, StateMachine
from .transition_policy import TransitionPolicy


class CodingAgent(Protocol):
    """Minimal agent protocol for controller execution."""

    async def propose_action(self, context: AgentContext) -> AgentProposal:
        """Return the next structured proposal."""

    def get_model_info(self) -> dict[str, str | int | float | bool | None]:
        """Return static model metadata."""


class ControllerEventStore(Protocol):
    """Persistence facade used by the controller and manifest generation."""

    async def create_run(self, run: Run) -> None:
        """Persist the initial run record."""

    async def update_run(self, run: Run) -> None:
        """Persist a run update."""

    async def append_event(self, event: Event) -> None:
        """Persist an append-only event."""

    async def create_candidate(self, run_id: UUID, candidate: Candidate) -> None:
        """Persist a candidate record."""

    async def update_candidate_status(self, candidate_id: UUID, status: CandidateStatus) -> None:
        """Persist a candidate status update."""

    async def record_evaluation(
        self,
        *,
        run_id: UUID,
        candidate_id: UUID,
        vector: EvaluationVector,
        tier: str,
    ) -> None:
        """Persist an evaluation vector."""

    async def record_artifact(self, run_id: UUID, artifact: ArtifactRef) -> None:
        """Persist artifact metadata."""

    def list_events(self, run_id: str) -> list[Event]:
        """Return cached ordered events for a run."""

    def list_candidates(self, run_id: str) -> list[Candidate]:
        """Return cached candidates for a run."""

    def list_artifacts(self, run_id: str) -> list[ArtifactRef]:
        """Return cached artifacts for a run."""


class SqliteEventStore:
    """SQLite-backed event-store facade with in-memory snapshots."""

    def __init__(
        self,
        *,
        run_repository: RunRepository,
        event_repository: EventRepository,
        candidate_repository: CandidateRepository,
        artifact_repository: ArtifactRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._run_repository = run_repository
        self._event_repository = event_repository
        self._candidate_repository = candidate_repository
        self._artifact_repository = artifact_repository
        self._session_factory = session_factory
        self._events: dict[str, list[Event]] = {}
        self._candidates: dict[str, list[Candidate]] = {}
        self._artifacts: dict[str, list[ArtifactRef]] = {}

    async def create_run(self, run: Run) -> None:
        await self._run_repository.create(
            id=str(run.id),
            status=run.status.value,
            goal_hash=run.goal_hash,
            initial_commit=run.initial_commit,
            experiment_mode=run.experiment_mode,
        )

    async def update_run(self, run: Run) -> None:
        await self._run_repository.update(
            str(run.id),
            status=run.status.value,
            updated_at=run.updated_at,
        )

    async def append_event(self, event: Event) -> None:
        await self._event_repository.create(
            id=str(event.id),
            run_id=str(event.run_id),
            event_type=event.event_type.value,
            iteration=event.iteration,
            source_state=event.source_state,
            target_state=event.target_state,
            payload=event.model_dump(mode="json"),
            event_hash=event.event_hash,
            previous_event_hash=event.previous_event_hash,
            timestamp=event.timestamp,
        )
        self._events.setdefault(str(event.run_id), []).append(event)

    async def create_candidate(self, run_id: UUID, candidate: Candidate) -> None:
        await self._candidate_repository.create(
            id=str(candidate.id),
            run_id=str(run_id),
            repository_state_hash=candidate.repository_state_hash,
            parent_id=str(candidate.parent_id) if candidate.parent_id is not None else None,
            depth=candidate.depth,
            status=candidate.status.value,
            iteration=candidate.iteration,
            created_at=candidate.created_at,
        )
        self._candidates.setdefault(str(run_id), []).append(candidate)

    async def update_candidate_status(self, candidate_id: UUID, status: CandidateStatus) -> None:
        model = await self._candidate_repository.update_status(str(candidate_id), status.value)
        if model is None:
            return
        run_candidates = self._candidates.get(model.run_id, [])
        for index, candidate in enumerate(run_candidates):
            if candidate.id == candidate_id:
                run_candidates[index] = candidate.model_copy(update={"status": status})
                break

    async def record_evaluation(
        self,
        *,
        run_id: UUID,
        candidate_id: UUID,
        vector: EvaluationVector,
        tier: str,
    ) -> None:
        async with self._session_factory() as session:
            session.add(
                EvaluationModel(
                    candidate_id=str(candidate_id),
                    run_id=str(run_id),
                    vector=vector.model_dump(mode="json"),
                    tier=tier,
                )
            )
            await session.commit()

    async def record_artifact(self, run_id: UUID, artifact: ArtifactRef) -> None:
        await self._artifact_repository.create(
            run_id=str(run_id),
            path=artifact.path,
            hash=artifact.hash,
            size_bytes=artifact.size_bytes,
            description=artifact.description,
        )
        self._artifacts.setdefault(str(run_id), []).append(artifact)

    def list_events(self, run_id: str) -> list[Event]:
        return list(self._events.get(run_id, []))

    def list_candidates(self, run_id: str) -> list[Candidate]:
        return list(self._candidates.get(run_id, []))

    def list_artifacts(self, run_id: str) -> list[ArtifactRef]:
        return list(self._artifacts.get(run_id, []))

    async def load_snapshots(self, run_id: str) -> None:
        """Populate cached snapshots from persisted storage."""
        stored_events = await self._event_repository.get_by_run(run_id)
        hydrated_events: list[Event] = []
        for model in stored_events:
            payload = dict(model.payload)
            if model.event_type == EventType.STATE_TRANSITION.value:
                hydrated_events.append(TransitionEvent.model_validate(payload))
            else:
                hydrated_events.append(Event.model_validate(payload))
        self._events[run_id] = hydrated_events

        stored_candidates = await self._candidate_repository.list_by_run(run_id)
        async with self._session_factory() as session:
            evaluations_by_candidate = await self._load_evaluations(session, run_id)
        self._candidates[run_id] = [
            Candidate(
                id=UUID(model.id),
                repository_state_hash=model.repository_state_hash,
                evaluation=evaluations_by_candidate.get(model.id),
                parent_id=UUID(model.parent_id) if model.parent_id is not None else None,
                depth=model.depth,
                status=CandidateStatus(model.status),
                iteration=model.iteration,
                created_at=model.created_at,
            )
            for model in stored_candidates
        ]

        stored_artifacts = await self._artifact_repository.list_by_run(run_id)
        self._artifacts[run_id] = [
            ArtifactRef(
                path=model.path,
                hash=model.hash,
                size_bytes=model.size_bytes,
                description=model.description,
            )
            for model in stored_artifacts
        ]

    async def _load_evaluations(
        self,
        session: AsyncSession,
        run_id: str,
    ) -> dict[str, EvaluationVector]:
        result = await session.scalars(
            select(EvaluationModel).where(EvaluationModel.run_id == run_id)
        )
        evaluations: dict[str, EvaluationVector] = {}
        for model in result:
            evaluations[model.candidate_id] = EvaluationVector.model_validate(model.vector)
        return evaluations


class Controller:
    """Drive the full constrained-agent lifecycle."""

    def __init__(
        self,
        *,
        goal_contract: GoalContract,
        sandbox: Sandbox,
        repository_store: RepositoryStore,
        evaluator_pipeline: EvaluatorPipeline,
        agent: CodingAgent,
        artifact_store: ArtifactStore,
        event_store: ControllerEventStore,
        budget_tracker: BudgetTracker,
        transition_policy: TransitionPolicy | None = None,
    ) -> None:
        self._goal_contract = goal_contract
        self._sandbox = sandbox
        self._repository_store = repository_store
        self._evaluator_pipeline = evaluator_pipeline
        self._agent = agent
        self._artifact_store = artifact_store
        self._event_store = event_store
        self._budget_tracker = budget_tracker
        self._transition_policy = transition_policy or TransitionPolicy()
        self._run_id = uuid4()
        self._state_machine = StateMachine(run_id=self._run_id)
        self._policy_engine = PolicyEngine(goal_contract)

    async def run(self) -> CompletionManifest | None:
        """Execute the full controller lifecycle."""
        workspace = self._workspace()
        initial_repository_state = self._snapshot_repository_state(iteration=0)
        run = Run(
            id=self._run_id,
            status=RunStatus.CREATED,
            goal_hash=self._goal_contract.hash(),
            initial_commit=initial_repository_state.commit_sha,
            experiment_mode=self._goal_contract.experiment.completion_strategy.value,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            metadata={
                "model": self._agent.get_model_info(),
                "evaluator_versions": self._evaluator_versions(),
            },
        )
        await self._event_store.create_run(run)

        baseline_candidate = Candidate(
            id=uuid4(),
            repository_state_hash=initial_repository_state.commit_sha,
            evaluation=None,
            parent_id=None,
            depth=0,
            status=CandidateStatus.ACCEPTED,
            iteration=0,
            created_at=datetime.now(UTC),
        )
        await self._event_store.create_candidate(run.id, baseline_candidate)
        history = [baseline_candidate]
        active_state = initial_repository_state
        best_state = initial_repository_state
        last_manifest: CompletionManifest | None = None

        try:
            await self._transition(
                ControllerState.INITIALIZING,
                TransitionDecision.ACCEPT,
                iteration=0,
                reason="run created",
            )
            self._validate_goal()
            run = await self._set_run_status(run, RunStatus.ACTIVE)

            await self._transition(
                ControllerState.BASELINE_EVALUATION,
                TransitionDecision.ACCEPT,
                iteration=0,
                reason="goal validated",
            )
            baseline_vector = await self._evaluate(active_state)
            history[0] = history[0].model_copy(update={"evaluation": baseline_vector})
            await self._event_store.record_evaluation(
                run_id=run.id,
                candidate_id=history[0].id,
                vector=baseline_vector,
                tier="baseline",
            )

            iteration = 1
            stagnation_count = 0
            while True:
                self._budget_tracker.record_iteration()
                if exceeded := self._budget_tracker.exceeded():
                    raise BudgetExceededError(", ".join(exceeded))

                await self._transition(
                    ControllerState.BUILDING_CONTEXT,
                    TransitionDecision.ACCEPT,
                    iteration=iteration,
                    reason="prepare fresh context",
                )
                context = self._build_context(iteration, history, active_state)
                await self._transition(
                    ControllerState.AWAITING_PROPOSAL,
                    TransitionDecision.ACCEPT,
                    iteration=iteration,
                    reason="context ready",
                )
                proposal = await self._agent.propose_action(context)
                self._budget_tracker.record_model_call(0, 0)
                await self._record_event(
                    EventType.MODEL_CALL,
                    iteration=iteration,
                    payload={"context": context.model_dump(mode="json")},
                    source_state=self._state_machine.current_state.value,
                    target_state=self._state_machine.current_state.value,
                )
                await self._record_event(
                    EventType.PROPOSAL_RECEIVED,
                    iteration=iteration,
                    payload=proposal.model_dump(mode="json"),
                    source_state=self._state_machine.current_state.value,
                    target_state=self._state_machine.current_state.value,
                )

                await self._transition(
                    ControllerState.POLICY_CHECK,
                    TransitionDecision.ACCEPT,
                    iteration=iteration,
                    reason="proposal received",
                )
                proposal = self._normalized_proposal(proposal)
                policy_report = self._policy_engine.check_proposal(proposal, workspace)
                await self._record_event(
                    EventType.POLICY_CHECK,
                    iteration=iteration,
                    payload=policy_report.model_dump(mode="json"),
                    source_state=self._state_machine.current_state.value,
                    target_state=self._state_machine.current_state.value,
                )
                if not policy_report.allowed:
                    decision = self._transition_policy.decide(
                        EvaluationVector(policy_violations=len(policy_report.violations)),
                        self._goal_contract,
                        history,
                        policy_violated=True,
                    )
                    await self._transition(
                        ControllerState.SELECTING_TRANSITION,
                        TransitionDecision.REJECT,
                        iteration=iteration,
                        reason="proposal rejected by policy",
                    )
                    await self._record_event(
                        EventType.TRANSITION_DECIDED,
                        iteration=iteration,
                        payload={"decision": decision.value},
                        source_state=self._state_machine.current_state.value,
                        target_state=self._state_machine.current_state.value,
                    )
                    iteration += 1
                    continue

                await self._transition(
                    ControllerState.EXECUTING,
                    TransitionDecision.ACCEPT,
                    iteration=iteration,
                    reason="policy passed",
                )
                execution_failed = await self._execute_proposal(proposal, workspace, iteration)
                if execution_failed:
                    stagnation_count += 1
                    self._repository_store.restore(active_state)
                    await self._transition(
                        ControllerState.SELECTING_TRANSITION,
                        TransitionDecision.ROLLBACK,
                        iteration=iteration,
                        reason="execution failed; restored checkpoint",
                    )
                    iteration += 1
                    continue

                await self._transition(
                    ControllerState.CHECKPOINTING,
                    TransitionDecision.ACCEPT,
                    iteration=iteration,
                    reason="execution succeeded",
                )
                clean_checkpoint = False
                try:
                    candidate_state = self._repository_store.checkpoint(
                        f"controller iteration {iteration}"
                    )
                except RepositoryStateError as exc:
                    if "clean workspace" not in str(exc):
                        raise
                    clean_checkpoint = True
                    candidate_state = self._snapshot_repository_state(iteration=iteration)
                active_state = candidate_state
                checkpoint_artifact = self._artifact_store.store(
                    "diff",
                    ""
                    if clean_checkpoint
                    else self._repository_store.diff(best_state, candidate_state),
                    description=f"iteration {iteration} diff",
                )
                await self._event_store.record_artifact(run.id, checkpoint_artifact)
                await self._record_event(
                    EventType.CHECKPOINT_CREATED,
                    iteration=iteration,
                    payload={
                        "commit": candidate_state.commit_sha,
                        "tree_hash": candidate_state.tree_hash,
                        "artifact_hash": checkpoint_artifact.hash,
                    },
                    source_state=self._state_machine.current_state.value,
                    target_state=self._state_machine.current_state.value,
                )

                await self._transition(
                    ControllerState.EVALUATING,
                    TransitionDecision.ACCEPT,
                    iteration=iteration,
                    reason="checkpoint created",
                )
                vector = await self._evaluate(candidate_state)
                candidate = Candidate(
                    id=uuid4(),
                    repository_state_hash=candidate_state.commit_sha,
                    evaluation=vector,
                    parent_id=history[-1].id,
                    depth=history[-1].depth + 1,
                    status=CandidateStatus.ACTIVE,
                    iteration=iteration,
                    created_at=datetime.now(UTC),
                )
                await self._event_store.create_candidate(run.id, candidate)
                await self._event_store.record_evaluation(
                    run_id=run.id,
                    candidate_id=candidate.id,
                    vector=vector,
                    tier="pipeline",
                )
                await self._record_event(
                    EventType.EVALUATION_COMPLETED,
                    iteration=iteration,
                    payload=vector.model_dump(mode="json"),
                    source_state=self._state_machine.current_state.value,
                    target_state=self._state_machine.current_state.value,
                )

                await self._transition(
                    ControllerState.SELECTING_TRANSITION,
                    TransitionDecision.ACCEPT,
                    iteration=iteration,
                    reason="evaluation completed",
                )
                decision = self._transition_policy.decide(
                    vector,
                    self._goal_contract,
                    history,
                    completion_claimed=proposal.completion_claimed,
                )
                await self._record_event(
                    EventType.TRANSITION_DECIDED,
                    iteration=iteration,
                    payload={"decision": decision.value},
                    source_state=self._state_machine.current_state.value,
                    target_state=self._state_machine.current_state.value,
                )

                if decision is TransitionDecision.COMPLETE:
                    await self._transition(
                        ControllerState.VERIFYING_COMPLETION,
                        decision,
                        iteration=iteration,
                        reason="completion claimed and accepted",
                        candidate_id=candidate.id,
                    )
                    verification_vector = await self._evaluate(candidate_state)
                    if not verification_vector.is_acceptable(self._goal_contract):
                        await self._event_store.update_candidate_status(
                            candidate.id,
                            CandidateStatus.REJECTED,
                        )
                        self._repository_store.restore(best_state)
                        active_state = best_state
                        history.append(
                            candidate.model_copy(update={"status": CandidateStatus.REJECTED})
                        )
                        stagnation_count += 1
                        iteration += 1
                        continue

                    accepted_candidate = candidate.model_copy(
                        update={"status": CandidateStatus.ACCEPTED}
                    )
                    await self._event_store.update_candidate_status(
                        candidate.id,
                        CandidateStatus.ACCEPTED,
                    )
                    history.append(accepted_candidate)
                    run.metadata["budget_usage"] = self._current_budget_usage().model_dump(
                        mode="json"
                    )
                    run.metadata["container_image"] = self._last_container_image()
                    run.updated_at = datetime.now(UTC)
                    run = await self._set_run_status(run, RunStatus.COMPLETED)
                    await self._transition(
                        ControllerState.COMPLETED,
                        TransitionDecision.COMPLETE,
                        iteration=iteration,
                        reason="completion verified",
                        candidate_id=candidate.id,
                    )
                    await self._record_event(
                        EventType.COMPLETION_DECLARED,
                        iteration=iteration,
                        payload={"candidate_id": str(candidate.id)},
                        source_state=self._state_machine.current_state.value,
                        target_state=self._state_machine.current_state.value,
                    )
                    last_manifest = generate_manifest(
                        run,
                        accepted_candidate,
                        self._artifact_store,
                        self._event_store,
                    )
                    return last_manifest

                if vector.is_acceptable(self._goal_contract):
                    best_state = candidate_state
                    active_state = candidate_state
                    stagnation_count = 0
                    accepted_candidate = candidate.model_copy(
                        update={"status": CandidateStatus.ACCEPTED}
                    )
                    await self._event_store.update_candidate_status(
                        candidate.id,
                        CandidateStatus.ACCEPTED,
                    )
                    history.append(accepted_candidate)
                else:
                    await self._event_store.update_candidate_status(
                        candidate.id,
                        CandidateStatus.REJECTED,
                    )
                    history.append(
                        candidate.model_copy(update={"status": CandidateStatus.REJECTED})
                    )
                    active_state = best_state
                    self._repository_store.restore(best_state)
                    stagnation_count += 1

                if stagnation_count >= 2:
                    self._repository_store.restore(best_state)
                    active_state = best_state
                    stagnation_count = 0

                iteration += 1

        except BudgetExceededError as exc:
            run.metadata["budget_usage"] = self._current_budget_usage().model_dump(mode="json")
            run.updated_at = datetime.now(UTC)
            run = await self._set_run_status(run, RunStatus.CANCELLED)
            await self._transition(
                ControllerState.CANCELLED,
                TransitionDecision.FAIL,
                iteration=self._budget_tracker.reserved().iterations_consumed,
                reason=f"budget exhausted: {exc}",
            )
            return last_manifest
        finally:
            await self._sandbox.close()

    def _validate_goal(self) -> None:
        errors = ContractValidator.validate(self._goal_contract)
        if errors:
            raise GoalValidationError("; ".join(errors))

    def _build_context(
        self,
        iteration: int,
        history: list[Candidate],
        active_state: RepositoryState,
    ) -> AgentContext:
        previous = history[-1].evaluation
        failures = ""
        if previous is not None:
            failures = json.dumps(previous.model_dump(mode="json"), sort_keys=True)
        return AgentContext(
            goal_summary=self._goal_contract.task.description,
            repository_map=self._repository_map(),
            candidate_diff=self._safe_diff(history, active_state),
            evaluation_failures=failures,
            prior_rejected=", ".join(
                str(candidate.id)
                for candidate in history
                if candidate.status is CandidateStatus.REJECTED
            ),
            remaining_budget=json.dumps(
                self._budget_tracker.remaining().model_dump(mode="json"),
                sort_keys=True,
            ),
            permitted_actions=["edit writable files", "run allowed commands"],
            protected_summary=", ".join(self._goal_contract.constraints.protected_paths) or "none",
            iteration=iteration,
        )

    async def _evaluate(self, repository_state: RepositoryState) -> EvaluationVector:
        context = EvaluationContext(
            workspace=self._workspace(),
            repository_state=repository_state,
            sandbox=self._sandbox,
            goal=self._goal_contract,
        )
        return await self._evaluator_pipeline.evaluate(context)

    async def _execute_proposal(
        self,
        proposal: AgentProposal,
        workspace: Path,
        iteration: int,
    ) -> bool:
        await self._record_event(
            EventType.EXECUTION_STARTED,
            iteration=iteration,
            payload={"write_files": proposal.write_files},
            source_state=self._state_machine.current_state.value,
            target_state=self._state_machine.current_state.value,
        )
        try:
            self._apply_edits(proposal.edits, workspace)
            for command in proposal.commands:
                if not isinstance(command.argv, list):
                    raise RepositoryStateError("controller only executes argv array commands")
                result = await self._sandbox.execute(
                    ExecutionRequest(
                        argv=command.argv,
                        purpose=getattr(command, "purpose", "controller execution"),
                        timeout_seconds=command.timeout_seconds,
                        working_dir=str(workspace),
                    )
                )
                self._budget_tracker.record_sandbox_time(result.duration_seconds)
                artifact = self._artifact_store.store(
                    "execution-log",
                    json.dumps(result.model_dump(mode="json"), sort_keys=True),
                    description="sandbox execution result",
                )
                await self._event_store.record_artifact(self._run_id, artifact)
                await self._record_event(
                    EventType.EXECUTION_COMPLETED,
                    iteration=iteration,
                    payload={
                        "argv": command.argv,
                        "exit_code": result.exit_code,
                        "timed_out": result.timed_out,
                        "truncated": result.truncated,
                        "artifact_hash": artifact.hash,
                        "container_image": result.container_image,
                    },
                    source_state=self._state_machine.current_state.value,
                    target_state=self._state_machine.current_state.value,
                )
                if result.exit_code != 0 or result.timed_out:
                    return True
            return False
        except (OSError, RepositoryStateError):
            return True

    def _apply_edits(self, edits: list[FileEdit], workspace: Path) -> None:
        for edit in edits:
            target = (workspace / edit.path).resolve()
            if workspace not in target.parents and target != workspace:
                raise RepositoryStateError(f"edit escaped workspace: {edit.path}")
            if edit.operation == "delete":
                if target.exists():
                    target.unlink()
                continue
            if edit.operation in {"create", "replace"}:
                if edit.content is None:
                    raise RepositoryStateError(f"missing content for {edit.operation}: {edit.path}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(edit.content, encoding="utf-8")
                continue
            if edit.operation == "patch":
                if edit.unified_diff is None:
                    raise RepositoryStateError(f"missing unified diff for patch: {edit.path}")
                self._apply_patch_file(workspace, edit.unified_diff)
                continue
            raise RepositoryStateError(f"unsupported edit operation: {edit.operation}")

    def _apply_patch_file(self, workspace: Path, unified_diff: str) -> None:
        if "diff --git" not in unified_diff and "--- " not in unified_diff:
            raise RepositoryStateError("patch edits require a full unified diff")
        try:
            subprocess.run(
                ["git", "apply", "--whitespace=nowarn", "-"],
                cwd=workspace,
                check=True,
                input=unified_diff,
                text=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else "git apply failed"
            raise RepositoryStateError(stderr) from exc

    def _normalized_proposal(self, proposal: AgentProposal) -> AgentProposal:
        if proposal.write_files:
            return proposal
        return proposal.model_copy(update={"write_files": [edit.path for edit in proposal.edits]})

    def _safe_diff(self, history: list[Candidate], active_state: RepositoryState) -> str:
        if len(history) < 2:
            return ""
        previous_commit = history[-1].repository_state_hash
        if previous_commit == active_state.commit_sha:
            return ""
        before = active_state.model_copy(update={"commit_sha": previous_commit})
        try:
            return self._repository_store.diff(before, active_state)
        except Exception:
            return ""

    def _repository_map(self) -> str:
        workspace = self._workspace()
        paths: list[str] = []
        for path in sorted(workspace.rglob("*")):
            if ".git" in path.parts:
                continue
            relative = path.relative_to(workspace).as_posix()
            if relative == "":
                continue
            paths.append(relative + ("/" if path.is_dir() else ""))
            if len(paths) >= 200:
                break
        return "\n".join(paths)

    def _workspace(self) -> Path:
        workspace = getattr(self._repository_store, "workspace", None)
        if workspace is None:
            raise RepositoryStateError("repository store does not expose a workspace")
        return Path(workspace)

    def _snapshot_repository_state(self, *, iteration: int) -> RepositoryState:
        workspace = self._workspace()
        commit_sha = self._git_output(workspace, ["rev-parse", "HEAD"])
        parent_sha = self._optional_git_output(workspace, ["rev-parse", "HEAD^"])
        branch_name = self._git_output(workspace, ["rev-parse", "--abbrev-ref", "HEAD"])
        tree_hash = self._git_output(workspace, ["rev-parse", "HEAD^{tree}"])
        return RepositoryState(
            commit_sha=commit_sha,
            parent_sha=parent_sha,
            branch_name=branch_name,
            tree_hash=tree_hash,
            diff_statistics=None,
            evaluation_ref=None,
            created_iteration=iteration,
        )

    def _git_output(self, workspace: Path, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else "git command failed"
            raise RepositoryStateError(stderr) from exc
        return result.stdout.strip()

    def _optional_git_output(self, workspace: Path, args: list[str]) -> str | None:
        try:
            return self._git_output(workspace, args)
        except RepositoryStateError:
            return None

    async def _transition(
        self,
        target: ControllerState,
        decision: TransitionDecision,
        *,
        iteration: int,
        reason: str,
        candidate_id: UUID | None = None,
    ) -> None:
        event = self._state_machine.transition(
            target,
            decision,
            iteration=iteration,
            reason=reason,
            candidate_id=candidate_id,
        )
        previous_hash = self._last_event_hash()
        event.previous_event_hash = previous_hash
        event.event_hash = Event.compute_hash(event, previous_hash)
        await self._event_store.append_event(event)

    async def _record_event(
        self,
        event_type: EventType,
        *,
        iteration: int,
        payload: dict[str, Any],
        source_state: str | None,
        target_state: str | None,
    ) -> None:
        previous_hash = self._last_event_hash()
        event = Event(
            id=uuid4(),
            run_id=self._run_id,
            event_type=event_type,
            iteration=iteration,
            source_state=source_state,
            target_state=target_state,
            payload=payload,
            previous_event_hash=previous_hash,
            event_hash="pending",
            timestamp=datetime.now(UTC),
        )
        event.event_hash = Event.compute_hash(event, previous_hash)
        await self._event_store.append_event(event)

    def _last_event_hash(self) -> str | None:
        events = self._event_store.list_events(str(self._run_id))
        if not events:
            return None
        return events[-1].event_hash

    async def _set_run_status(self, run: Run, status: RunStatus) -> Run:
        updated = run.model_copy(update={"status": status, "updated_at": datetime.now(UTC)})
        await self._event_store.update_run(updated)
        return updated

    def _current_budget_usage(self) -> Any:
        remaining = self._budget_tracker.remaining()
        reserved = self._budget_tracker.reserved()
        return reserved.model_copy(
            update={
                "iterations_consumed": reserved.iterations_consumed - remaining.iterations_consumed,
                "model_calls": reserved.model_calls - remaining.model_calls,
                "runtime_seconds": reserved.runtime_seconds - remaining.runtime_seconds,
                "sandbox_seconds": 0.0,
            }
        )

    def _evaluator_versions(self) -> dict[str, str]:
        evaluators = getattr(self._evaluator_pipeline, "_evaluators", [])
        return {
            getattr(evaluator, "id", evaluator.__class__.__name__): evaluator.__class__.__module__
            for evaluator in evaluators
        }

    def _last_container_image(self) -> str | None:
        for event in reversed(self._event_store.list_events(str(self._run_id))):
            container_image = event.payload.get("container_image")
            if isinstance(container_image, str) and container_image != "":
                return container_image
        return None
