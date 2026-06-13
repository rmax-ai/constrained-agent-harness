# Phase 2 — Batch 3: Repository Store, Event Store, Artifact Store

## Task

Implement the Git-backed repository store, SQLite event store with persistence, and artifact hashing.

## Files to Create

### 1. `src/constrained_agent/repository/protocol.py`

- `RepositoryState` — Pydantic BaseModel: commit_sha (str), parent_sha (str | None), branch_name (str), tree_hash (str), diff_statistics (dict | None), evaluation_ref (str | None), created_iteration (int)

- `RepositoryStore` — Protocol:
  - `initialize(self, source: Path) -> RepositoryState`
  - `checkpoint(self, message: str) -> RepositoryState`
  - `restore(self, state: RepositoryState)` -> None
  - `diff(self, before: RepositoryState, after: RepositoryState) -> str`
  - `create_branch(self, state: RepositoryState, name: str) -> RepositoryState`

### 2. `src/constrained_agent/repository/git_store.py`

- `GitRepositoryStore` — implements RepositoryStore using GitPython or subprocess git calls
  - Uses `.cah/runs/<run-id>/workspace` as run workspace
  - Uses temporary branches or detached worktrees
  - Never operates on original working tree
  - `initialize()` — clones source repo to workspace
  - `checkpoint()` — commits all changes, returns state
  - `restore()` — git reset --hard to specific commit
  - `diff()` — git diff between two states
  - Handle repos with uncommitted changes — refuse ambiguous operations

### 3. `src/constrained_agent/repository/worktree.py`

- Git worktree management utilities
- Create/remove detached worktrees
- Check if worktree is clean
- List active worktrees

### 4. `src/constrained_agent/persistence/database.py`

- `DatabaseEngine` — async SQLAlchemy engine management
- `get_session()` — session factory
- `init_db()` — create all tables
- Engine configured from settings.database_url

### 5. `src/constrained_agent/persistence/models.py`

SQLAlchemy 2.x ORM models:
- `RunModel` — id, status, goal_hash, initial_commit, experiment_mode, created_at, updated_at
- `EventModel` — id, run_id, event_type, iteration, source_state, target_state, payload (JSON), event_hash, previous_event_hash, timestamp
- `CandidateModel` — id, run_id, repository_state_hash, parent_id, depth, status, iteration, created_at
- `EvaluationModel` — id, candidate_id, run_id, vector (JSON), tier, timestamp
- `ArtifactModel` — id, run_id, path, hash, size_bytes, description, timestamp

### 6. `src/constrained_agent/persistence/repositories.py`

Repository classes for each model:
- `RunRepository` — create, get, update, list
- `EventRepository` — create, get_by_run, get_chain
- `CandidateRepository` — create, get, list_by_run, update_status
- `ArtifactRepository` — create, list_by_run

### 7. `src/constrained_agent/artifacts/hashing.py`

- `hash_file(path: Path) -> str` — SHA-256 of file contents
- `hash_bytes(data: bytes) -> str` — SHA-256 of bytes
- `hash_chain(previous_hash: str | None, payload: str) -> str` — SHA256(previous || payload)
- `verify_file(path: Path, expected_hash: str) -> bool`

### 8. `src/constrained_agent/artifacts/store.py`

- `ArtifactStore` — stores artifacts under `.cah/runs/<run-id>/artifacts/`
  - `store(kind: str, data: str | bytes, description: str | None = None) -> ArtifactRef`
  - `retrieve(ref: ArtifactRef) -> str`
  - `verify(ref: ArtifactRef) -> bool` — verify hash matches

## Files to Modify

- All relevant __init__.py files

## Tests

Create basic unit tests that mock git and SQLite:
- Repository checkpoint/restore cycle
- Hash chain integrity
- Event persistence and retrieval
