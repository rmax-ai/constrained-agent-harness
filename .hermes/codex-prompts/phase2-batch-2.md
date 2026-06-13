# Phase 2 — Batch 2: Policy Engine

## Task

Implement the policy engine — path, command, and dependency enforcement.

## Files to Create

### 1. `src/constrained_agent/policy/paths.py`

- `PathPolicy` — class:
  - `__init__(self, writable_paths: list[str], protected_paths: list[str])` — accepts glob patterns
  - `is_writable(self, path: Path) -> bool` — normalized comparison
  - `is_protected(self, path: Path) -> bool` — cannot be modified by agent
  - `reject_path_traversal(self, path: Path) -> bool` — reject `../` escapes, symlink escapes
  - `reject_symlink_escape(self, path: Path) -> bool` — check resolved path isn't outside workspace
  - `resolve(self, path: Path, base: Path) -> Path` — normalize and resolve
  - Use `Path.resolve()` and compare against allowed roots

### 2. `src/constrained_agent/policy/commands.py`

- `CommandPolicy` — class:
  - `__init__(self, allowed_commands: list[str], forbidden_patterns: list[str])`
  - `is_allowed(self, argv: list[str]) -> bool` — check command base name is in allowed list
  - `has_forbidden_pattern(self, argv: list[str]) -> bool` — check for patterns like `rm -rf`, `curl`
  - `reject_shell_strings(self, proposal_command) -> bool` — ensure commands are argument arrays, not shell strings
  - `all_timeouts_within_limit(self, commands: list, max_timeout: int) -> bool`

### 3. `src/constrained_agent/policy/dependencies.py`

- `DependencyPolicy` — class:
  - `__init__(self, allow_changes: bool)`
  - `check_dependency_changes(self, diff_output: str) -> bool` — detect changes to dependency files (pyproject.toml, requirements.txt, etc.)
  - `requires_approval(self, diff_output: str) -> ApprovalGate | None`

### 4. `src/constrained_agent/policy/approvals.py`

- Minimal approval gate definitions matching the ApprovalGate enum
- `ApprovalRegistry` — maps gate types to descriptions and required conditions

### 5. `src/constrained_agent/policy/engine.py`

- `PolicyEngine` — orchestrates the sub-policies:
  - `__init__(self, contract: GoalContract)`
  - `check_proposal(self, proposal: AgentProposal, workspace: Path) -> PolicyReport` — comprehensive check
  - `PolicyReport` — Pydantic: allowed (bool), violations (list[str]), protected_file_attempts (list[str]), rejected_commands (list[str]), requires_approval (list[ApprovalGate]), details (dict)

## Tests

Create `tests/unit/test_policy_engine.py`:
- Path traversal attempts are rejected
- Protected file edits are blocked
- Allowed commands pass through
- Forbidden patterns are caught
- Dependency changes detected
