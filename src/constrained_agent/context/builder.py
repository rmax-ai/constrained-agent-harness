"""Fresh-session context reconstruction for model calls."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from constrained_agent.agents.protocol import AgentContext
from constrained_agent.context.failure_summary import FailureSummary
from constrained_agent.context.repository_map import RepositoryMap
from constrained_agent.context.token_budget import TokenBudget
from constrained_agent.domain.budgets import BudgetUsage
from constrained_agent.domain.candidates import Candidate
from constrained_agent.domain.contracts import GoalContract
from constrained_agent.domain.evaluations import EvaluationResult, EvaluationVector
from constrained_agent.domain.evidence import Evidence
from constrained_agent.domain.runs import Run
from constrained_agent.repository.protocol import RepositoryStore


class ContextBuilder:
    """Reconstruct fresh context from repository state and persisted evidence."""

    def __init__(
        self,
        goal: GoalContract,
        repository_store: RepositoryStore,
        max_chars_per_file: int = 8000,
        max_files: int = 20,
        max_diff_size: int = 5000,
        max_failure_records: int = 10,
    ) -> None:
        self._goal = goal
        self._repository_store = repository_store
        self._max_chars_per_file = max_chars_per_file
        self._max_files = max_files
        self._max_diff_size = max_diff_size
        self._max_failure_records = max_failure_records
        self.last_manifest = ""

    async def build(
        self,
        run: Run,
        candidate: Candidate,
        evidence: list[Evidence],
        stagnation_report: Any,
    ) -> AgentContext:
        """Build bounded agent context for a fresh model session."""
        workspace = self._workspace()
        repository_map = RepositoryMap(workspace)
        tree = repository_map.build(workspace)
        failing_tests = self._failing_tests(stagnation_report, evidence)
        search_patterns = self._search_patterns(stagnation_report, evidence)
        relevant_files = repository_map.find_relevant_files(failing_tests, search_patterns)[
            : self._max_files
        ]

        relevant_sections: list[str] = []
        for file_path in relevant_files:
            relative = file_path.relative_to(workspace)
            content = repository_map.read_file_content(file_path, self._max_chars_per_file)
            relevant_sections.append(f"## {relative}\n{content}")
        repository_text = tree
        if relevant_sections:
            repository_text += "\n\nRelevant files:\n" + "\n\n".join(relevant_sections)

        candidate_diff = TokenBudget.truncate_to_budget(
            self._current_diff(workspace, candidate),
            max_tokens=max(1, self._max_diff_size // 4),
        )
        evaluation_failures = self._evaluation_failures(candidate, evidence, stagnation_report)
        prior_rejected = self._prior_rejected(evidence)
        remaining_budget = self._remaining_budget(run)
        goal_summary = self._goal_summary()

        context = AgentContext(
            goal_summary=goal_summary,
            repository_map=repository_text,
            candidate_diff=candidate_diff,
            evaluation_failures=evaluation_failures,
            prior_rejected=prior_rejected,
            remaining_budget=remaining_budget,
            permitted_actions=self._permitted_actions(),
            protected_summary=", ".join(self._goal.constraints.protected_paths) or "none",
            iteration=max(1, candidate.iteration + 1),
        )
        self.last_manifest = self._manifest(
            context=context,
            relevant_files=[path.relative_to(workspace) for path in relevant_files],
            failures=evaluation_failures,
        )
        return context

    def _workspace(self) -> Path:
        workspace = getattr(self._repository_store, "workspace", None)
        if workspace is None:
            raise ValueError("repository store does not expose a workspace")
        return Path(workspace)

    def _goal_summary(self) -> str:
        return f"{self._goal.task.title}: {self._goal.task.description}"

    def _failing_tests(self, stagnation_report: Any, evidence: list[Evidence]) -> list[str]:
        collected = self._collect_strings(stagnation_report, "failing_tests")
        if collected:
            return collected[: self._max_failure_records]

        discovered: list[str] = []
        for item in evidence:
            for candidate in self._collect_strings(item.payload, "failing_tests"):
                discovered.append(candidate)
            for candidate in self._extract_strings(item.payload):
                if candidate.endswith(".py") and "test" in candidate.lower():
                    discovered.append(candidate)
        return discovered[: self._max_failure_records]

    def _search_patterns(self, stagnation_report: Any, evidence: list[Evidence]) -> list[str]:
        patterns = self._collect_strings(stagnation_report, "search_patterns")
        if patterns:
            return patterns[: self._max_failure_records]

        discovered: list[str] = []
        for item in evidence[-self._max_failure_records :]:
            discovered.extend(self._extract_strings(item.payload))
        return discovered[: self._max_failure_records]

    def _current_diff(self, workspace: Path, candidate: Candidate) -> str:
        commands = [
            ["git", "diff", "--no-ext-diff", "HEAD"],
            ["git", "show", "--format=", "--no-ext-diff", candidate.repository_state_hash],
        ]
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    cwd=workspace,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except (OSError, subprocess.CalledProcessError):
                continue
            if result.stdout.strip():
                return result.stdout[: self._max_diff_size]
        return ""

    def _evaluation_failures(
        self,
        candidate: Candidate,
        evidence: list[Evidence],
        stagnation_report: Any,
    ) -> str:
        vector = candidate.evaluation or self._extract_vector(stagnation_report, evidence)
        results = self._extract_results(stagnation_report, evidence)
        if vector is None:
            return "No evaluation failures recorded."
        return FailureSummary().summarize(vector, results)

    def _prior_rejected(self, evidence: list[Evidence]) -> str:
        rejected: list[str] = []
        for item in evidence:
            if item.event_type.upper() not in {
                "PROPOSAL_REJECTED",
                "TRANSITION_DECIDED",
                "POLICY_CHECK",
            }:
                continue
            strategy = self._rejected_strategy(item)
            if strategy:
                rejected.append(strategy)
        if not rejected:
            return "none"
        return "\n".join(rejected[-self._max_failure_records :])

    def _remaining_budget(self, run: Run) -> str:
        raw_usage = run.metadata.get("budget_usage", {})
        usage = BudgetUsage.model_validate(raw_usage if isinstance(raw_usage, dict) else {})
        remaining = BudgetUsage(
            iterations_consumed=max(
                0,
                self._goal.constraints.max_iterations - usage.iterations_consumed,
            ),
            model_calls=max(0, self._goal.constraints.max_model_calls - usage.model_calls),
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            runtime_seconds=max(
                0.0,
                float(self._goal.constraints.max_runtime_seconds)
                - self._elapsed_runtime(run, usage),
            ),
            sandbox_seconds=max(0.0, usage.sandbox_seconds),
        )
        return TokenBudget.budget_remaining(remaining)

    def _elapsed_runtime(self, run: Run, usage: BudgetUsage) -> float:
        if usage.runtime_seconds > 0:
            return usage.runtime_seconds
        started = run.created_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        return max(0.0, (datetime.now(UTC) - started).total_seconds())

    def _permitted_actions(self) -> list[str]:
        actions = [
            "edit files under: "
            + (", ".join(self._goal.constraints.writable_paths) or "no writable paths configured"),
            "run allowed commands: "
            + (
                ", ".join(" ".join(command) for command in self._goal.constraints.allowed_commands)
                or "none"
            ),
        ]
        if self._goal.constraints.network_mode.value != "off":
            actions.append(f"network mode: {self._goal.constraints.network_mode.value}")
        return actions

    def _manifest(
        self,
        *,
        context: AgentContext,
        relevant_files: list[Path],
        failures: str,
    ) -> str:
        lines = [
            "Context manifest",
            f"goal={context.goal_summary}",
            f"iteration={context.iteration}",
            f"relevant_files={len(relevant_files)}",
            f"repository_map_tokens~{TokenBudget.estimate_tokens(context.repository_map)}",
            f"diff_tokens~{TokenBudget.estimate_tokens(context.candidate_diff)}",
            f"failure_tokens~{TokenBudget.estimate_tokens(failures)}",
        ]
        if relevant_files:
            lines.append("selected=" + ", ".join(str(path) for path in relevant_files))
        return "\n".join(lines)

    def _extract_vector(
        self,
        stagnation_report: Any,
        evidence: list[Evidence],
    ) -> EvaluationVector | None:
        vector_payload = self._collect_mapping(stagnation_report, "evaluation_vector")
        if vector_payload is not None:
            return EvaluationVector.model_validate(vector_payload)
        for item in reversed(evidence):
            vector_payload = self._collect_mapping(item.payload, "evaluation_vector")
            if vector_payload is not None:
                return EvaluationVector.model_validate(vector_payload)
        return None

    def _extract_results(
        self,
        stagnation_report: Any,
        evidence: list[Evidence],
    ) -> list[EvaluationResult]:
        result_payloads = self._collect_list(stagnation_report, "evaluation_results")
        if result_payloads:
            return [EvaluationResult.model_validate(payload) for payload in result_payloads]

        results: list[EvaluationResult] = []
        for item in evidence[-self._max_failure_records :]:
            for payload in self._collect_list(item.payload, "evaluation_results"):
                results.append(EvaluationResult.model_validate(payload))
        return results[: self._max_failure_records]

    def _rejected_strategy(self, item: Evidence) -> str | None:
        status = str(item.payload.get("decision", item.payload.get("status", ""))).upper()
        if item.event_type.upper() == "POLICY_CHECK" and status not in {"REJECT", "REJECTED"}:
            allowed = item.payload.get("allowed")
            if allowed is not False:
                return None
        if item.event_type.upper() == "TRANSITION_DECIDED" and status not in {"REJECT", "REJECTED"}:
            return None

        summary = item.payload.get("summary") or item.payload.get("hypothesis")
        if isinstance(summary, str) and summary.strip():
            return f"iteration {item.iteration}: {summary.strip()}"
        violations = item.payload.get("violations")
        if isinstance(violations, list) and violations:
            return (
                f"iteration {item.iteration}: policy rejected ({'; '.join(map(str, violations))})"
            )
        return f"iteration {item.iteration}: rejected without structured summary"

    def _collect_strings(self, source: Any, key: str) -> list[str]:
        value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str) and item.strip()]
        return []

    def _collect_mapping(self, source: Any, key: str) -> dict[str, Any] | None:
        value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
        if isinstance(value, dict):
            return value
        return None

    def _collect_list(self, source: Any, key: str) -> list[dict[str, Any]]:
        value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    def _extract_strings(self, source: Any) -> list[str]:
        strings: list[str] = []
        if isinstance(source, str):
            return [source]
        if isinstance(source, dict):
            values: Iterable[Any] = source.values()
        elif isinstance(source, list):
            values = source
        else:
            return strings
        for value in values:
            strings.extend(self._extract_strings(value))
        return strings


__all__ = ["AgentContext", "ContextBuilder"]
