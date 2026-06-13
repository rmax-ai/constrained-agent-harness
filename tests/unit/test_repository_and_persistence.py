from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from constrained_agent.artifacts import ArtifactStore, hash_chain
from constrained_agent.persistence import DatabaseEngine
from constrained_agent.persistence.repositories import EventRepository, RunRepository
from constrained_agent.repository import GitRepositoryStore
from constrained_agent.settings import Settings


def _run_git(repository: Path, args: list[str]) -> None:
    import subprocess

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
    (repository / "README.md").write_text("initial\n", encoding="utf-8")
    _run_git(repository, ["add", "README.md"])
    _run_git(repository, ["commit", "-m", "initial commit"])
    return repository


def test_git_repository_store_checkpoint_restore_cycle(tmp_path: Path) -> None:
    source = _create_source_repo(tmp_path)
    store = GitRepositoryStore(runtime_dir=tmp_path / ".cah", run_id=uuid4())

    initial_state = store.initialize(source)
    readme_path = store.workspace / "README.md"
    readme_path.write_text("initial\nchanged\n", encoding="utf-8")

    checkpoint_state = store.checkpoint("update readme")
    diff_text = store.diff(initial_state, checkpoint_state)

    assert checkpoint_state.parent_sha == initial_state.commit_sha
    assert "changed" in diff_text
    assert checkpoint_state.diff_statistics is not None
    assert checkpoint_state.diff_statistics["files_changed"] == 1

    store.restore(initial_state)

    assert readme_path.read_text(encoding="utf-8") == "initial\n"


def test_hash_chain_and_artifact_store_detect_tampering(tmp_path: Path) -> None:
    first = hash_chain(None, "first")
    second = hash_chain(first, "second")

    assert first != second

    store = ArtifactStore(runtime_dir=tmp_path / ".cah", run_id=uuid4())
    ref = store.store("log", "payload", description="test payload")

    assert store.retrieve(ref) == "payload"
    assert store.verify(ref) is True

    Path(ref.path).write_text("tampered", encoding="utf-8")

    assert store.verify(ref) is False


@pytest.mark.asyncio
async def test_event_persistence_and_retrieval(tmp_path: Path) -> None:
    database_path = tmp_path / "cah.db"
    settings = Settings(database_url=f"sqlite:///{database_path}")
    engine = DatabaseEngine(settings)
    await engine.init_db()

    run_repository = RunRepository(engine.get_session())
    event_repository = EventRepository(engine.get_session())

    run = await run_repository.create(
        id=str(uuid4()),
        status="CREATED",
        goal_hash="a" * 64,
        initial_commit="b" * 40,
        experiment_mode="controller_decides",
    )
    first_event_hash = hash_chain(None, "run-created")
    second_event_hash = hash_chain(first_event_hash, "transition")

    first_timestamp = datetime.now(UTC)
    second_timestamp = first_timestamp + timedelta(seconds=1)

    first_event = await event_repository.create(
        id=str(uuid4()),
        run_id=run.id,
        event_type="RUN_CREATED",
        iteration=0,
        source_state=None,
        target_state="CREATED",
        payload={"message": "created"},
        event_hash=first_event_hash,
        previous_event_hash=None,
        timestamp=first_timestamp,
    )
    second_event = await event_repository.create(
        id=str(uuid4()),
        run_id=run.id,
        event_type="STATE_TRANSITION",
        iteration=1,
        source_state="CREATED",
        target_state="INITIALIZING",
        payload={"message": "transition"},
        event_hash=second_event_hash,
        previous_event_hash=first_event_hash,
        timestamp=second_timestamp,
    )

    events = await event_repository.get_by_run(run.id)
    chain = await event_repository.get_chain(run.id)

    assert [event.id for event in events] == [first_event.id, second_event.id]
    assert [event.previous_event_hash for event in chain] == [None, first_event_hash]

    await engine.dispose()
