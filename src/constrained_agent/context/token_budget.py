"""Token budget helpers for fresh-session context reconstruction."""

from __future__ import annotations

from constrained_agent.domain.budgets import BudgetUsage


class TokenBudget:
    """Estimate and render model-token budget usage with simple heuristics."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count using a rough chars-per-token ratio."""
        if text == "":
            return 0
        return max(1, (len(text) + 3) // 4)

    @staticmethod
    def truncate_to_budget(text: str, max_tokens: int, indicator: str = "...") -> str:
        """Truncate text to fit a token budget using the rough estimator."""
        if max_tokens <= 0:
            return indicator[:0]
        if TokenBudget.estimate_tokens(text) <= max_tokens:
            return text

        max_chars = max_tokens * 4
        if len(indicator) >= max_chars:
            return indicator[:max_chars]
        return text[: max_chars - len(indicator)] + indicator

    @staticmethod
    def budget_remaining(budget: BudgetUsage) -> str:
        """Render a human-readable summary of remaining budget."""
        return (
            f"{budget.iterations_consumed} iterations left, "
            f"{budget.model_calls} model calls left, "
            f"{budget.runtime_seconds:.1f}s runtime left, "
            f"{budget.sandbox_seconds:.1f}s sandbox left"
        )
