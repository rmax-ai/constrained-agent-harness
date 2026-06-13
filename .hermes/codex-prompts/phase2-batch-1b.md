# Phase 2 — Batch 1b: Evaluation, Evidence, Budget Models

## Task

Create the remaining domain models for constrained-agent-harness.

## Files to Create

### 1. `src/constrained_agent/domain/evaluations.py`

Evaluation types for the evaluator pipeline.

```python
from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel
from typing import Any

class EvaluationTier(StrEnum):
    TIER_0_POLICY = "tier_0_policy"
    TIER_1_FAST_STATIC = "tier_1_fast_static"
    TIER_2_TARGETED_TESTS = "tier_2_targeted_tests"
    TIER_3_FULL_TESTS = "tier_3_full_tests"
    TIER_4_HIDDEN_AND_SECURITY = "tier_4_hidden_and_security"
```

- `EvaluationVector` — Pydantic BaseModel with: policy_violations (int), protected_file_changes (int), compilation_ok (bool | None), type_check_ok (bool | None), lint_ok (bool | None), visible_tests_passed (int), visible_tests_failed (int), hidden_tests_passed (int | None), hidden_tests_failed (int | None), security_critical (int), security_high (int), dependency_changes (int), runtime_seconds (float)

Include method `is_better_than(self, other: EvaluationVector) -> bool` using lexicographic comparison: hard gates first (policy, protected paths, critical security), then blocking check improvements, then tiebreak by cost/diff/size.

Include method `is_acceptable(self, contract: GoalContract) -> bool` — checks hard gates against contract thresholds.

- `EvaluationResult` — Pydantic BaseModel: evaluator_id (str), tier (EvaluationTier), passed (bool), stdout (str | None), stderr (str | None), exit_code (int | None), duration_seconds (float), truncated (bool = False), error (str | None)

### 2. `src/constrained_agent/domain/evidence.py`

- `Evidence` — Pydantic BaseModel: id (UUID), run_id (UUID), iteration (int), candidate_id (UUID | None), event_type (str), payload (dict), artifact_refs (list[ArtifactRef]), timestamp (datetime)
- `ArtifactRef` — Pydantic BaseModel: path (str), hash (str), size_bytes (int), description (str | None)

### 3. `src/constrained_agent/domain/budgets.py`

- `BudgetUsage` — Pydantic BaseModel: iterations_consumed (int = 0), model_calls (int = 0), input_tokens (int = 0), output_tokens (int = 0), estimated_cost_usd (float = 0.0), runtime_seconds (float = 0.0), sandbox_seconds (float = 0.0)

- `BudgetTracker` — class with methods:
  - `__init__(self, contract: GoalContract)` — sets limits from contract constraints
  - `record_iteration(self)` — increments counter
  - `record_model_call(self, input_tokens: int, output_tokens: int)` — records usage
  - `record_sandbox_time(self, seconds: float)`
  - `remaining(self) -> BudgetUsage` — returns remaining budget
  - `exceeded(self) -> list[str]` — returns list of exceeded budget names
  - `reserved(self) -> BudgetUsage` — returns reserved budget (limits)

## Files to Modify

- `src/constrained_agent/domain/__init__.py` — add new exports
