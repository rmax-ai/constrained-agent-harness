"""Budget usage tracking for constrained runs."""

from __future__ import annotations

from time import monotonic

from pydantic import BaseModel, ConfigDict, Field

from constrained_agent.domain.contracts import GoalContract


class BudgetUsage(BaseModel):
    """Usage or reservation snapshot for bounded execution budgets."""

    model_config = ConfigDict(extra="forbid")

    iterations_consumed: int = Field(ge=0, default=0)
    model_calls: int = Field(ge=0, default=0)
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    estimated_cost_usd: float = Field(ge=0.0, default=0.0)
    runtime_seconds: float = Field(ge=0.0, default=0.0)
    sandbox_seconds: float = Field(ge=0.0, default=0.0)


class BudgetTracker:
    """Tracks consumed budget against goal-contract limits."""

    def __init__(self, contract: GoalContract) -> None:
        self._contract = contract
        self._usage = BudgetUsage()
        self._reserved = BudgetUsage(
            iterations_consumed=contract.constraints.max_iterations,
            model_calls=contract.constraints.max_model_calls,
            runtime_seconds=float(contract.constraints.max_runtime_seconds),
        )
        self._started_at = monotonic()

    def record_iteration(self) -> None:
        """Record one controller iteration."""
        self._usage.iterations_consumed += 1

    def record_model_call(self, input_tokens: int, output_tokens: int) -> None:
        """Record one model call and its token usage."""
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must be non-negative")
        self._usage.model_calls += 1
        self._usage.input_tokens += input_tokens
        self._usage.output_tokens += output_tokens

    def record_sandbox_time(self, seconds: float) -> None:
        """Accumulate time spent inside sandbox execution."""
        if seconds < 0:
            raise ValueError("sandbox seconds must be non-negative")
        self._usage.sandbox_seconds += seconds

    def remaining(self) -> BudgetUsage:
        """Return the remaining reserved budget."""
        elapsed = monotonic() - self._started_at
        return BudgetUsage(
            iterations_consumed=max(
                0, self._reserved.iterations_consumed - self._usage.iterations_consumed
            ),
            model_calls=max(0, self._reserved.model_calls - self._usage.model_calls),
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            runtime_seconds=max(0.0, self._reserved.runtime_seconds - elapsed),
            sandbox_seconds=0.0,
        )

    def exceeded(self) -> list[str]:
        """Return the names of any exceeded budget categories."""
        elapsed = monotonic() - self._started_at
        exceeded: list[str] = []
        if self._usage.iterations_consumed > self._reserved.iterations_consumed:
            exceeded.append("iterations_consumed")
        if self._usage.model_calls > self._reserved.model_calls:
            exceeded.append("model_calls")
        if elapsed > self._reserved.runtime_seconds:
            exceeded.append("runtime_seconds")
        return exceeded

    def reserved(self) -> BudgetUsage:
        """Return the reserved budget limits derived from the contract."""
        return self._reserved.model_copy(deep=True)
