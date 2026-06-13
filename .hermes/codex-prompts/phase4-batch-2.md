# Phase 4 — Batch 2: Context Builder + Repository Map + Token Budget

## Task

Implement the context reconstruction system for fresh-session model calls. Build the repository map, failure summary, and token budget controls.

## Files to Create

### 1. `src/constrained_agent/context/builder.py`

- `ContextBuilder` — reconstructs fresh context for every model call:
  - `__init__(self, goal: GoalContract, repository_store: RepositoryStore, max_chars_per_file: int = 8000, max_files: int = 20, max_diff_size: int = 5000, max_failure_records: int = 10)`
  - `async build(run, candidate, evidence, stagnation_report) -> AgentContext`:
    1. Gets goal summary from contract
    2. Gets repository map from current state (file listing)
    3. Gets relevant source files (filename matching, import relationships)
    4. Gets current diff
    5. Gets latest evaluation failures
    6. Gets prior rejected strategies from evidence
    7. Gets remaining budget
    8. Applies truncation limits
    9. Returns AgentContext with all fields populated
  - Generated a human-readable context manifest for each call

### 2. `src/constrained_agent/context/repository_map.py`

- `RepositoryMap` — maps repository structure for context:
  - `build(path: Path) -> str` — returns indented file tree
  - `find_relevant_files(failing_tests: list[str], search_patterns: list[str]) -> list[Path]` — finds files by:
    - Filename matching (e.g., "test_webhook" → "app.py", "database.py")
    - Import relationships
    - Python AST symbol references
    - Failing stack traces
  - `read_file_content(path: Path, max_chars: int) -> str` — reads with truncation

### 3. `src/constrained_agent/context/failure_summary.py`

- `FailureSummary` — summarizes evaluation failures:
  - `summarize(evaluation_vector: EvaluationVector, evaluation_results: list[EvaluationResult]) -> str`
  - Formats failures into readable text
  - Groups by tier
  - Includes stdout/stderr from failing evaluators (truncated)

### 4. `src/constrained_agent/context/token_budget.py`

- `TokenBudget` — estimates and manages token budgets:
  - `estimate_tokens(text: str) -> int` — rough character/4 estimate
  - `truncate_to_budget(text: str, max_tokens: int, indicator: str = "...") -> str` — truncate with indicator
  - `budget_remaining(budget: BudgetUsage) -> str` — human-readable remaining budget

## Tests

Create `tests/unit/test_context_builder.py`:
- Context builder produces valid AgentContext
- Repository map handles missing directories
- Truncation respects limits
- Token estimation is reasonable

## Files to Modify

- `src/constrained_agent/context/__init__.py`
