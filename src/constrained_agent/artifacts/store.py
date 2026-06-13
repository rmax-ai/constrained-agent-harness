"""Artifact storage backed by the run runtime directory."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from constrained_agent.artifacts.hashing import hash_bytes, verify_file
from constrained_agent.domain import ArtifactRef
from constrained_agent.errors import ArtifactIntegrityError


class ArtifactStore:
    """Persist append-only artifact files under a run-specific directory."""

    def __init__(self, *, runtime_dir: Path, run_id: UUID | str) -> None:
        self._artifact_root = runtime_dir / "runs" / str(run_id) / "artifacts"
        self._artifact_root.mkdir(parents=True, exist_ok=True)

    def store(self, kind: str, data: str | bytes, description: str | None = None) -> ArtifactRef:
        """Store artifact data and return its immutable reference."""
        payload = data.encode("utf-8") if isinstance(data, str) else data
        digest = hash_bytes(payload)
        extension = kind.strip().replace("/", "_").replace(" ", "_") or "artifact"
        artifact_path = self._artifact_root / f"{digest}.{extension}"
        artifact_path.write_bytes(payload)
        return ArtifactRef(
            path=str(artifact_path),
            hash=digest,
            size_bytes=len(payload),
            description=description,
        )

    def retrieve(self, ref: ArtifactRef) -> str:
        """Retrieve a UTF-8 artifact after verifying its recorded hash."""
        if not self.verify(ref):
            raise ArtifactIntegrityError(f"artifact verification failed: {ref.path}")
        return Path(ref.path).read_text(encoding="utf-8")

    def verify(self, ref: ArtifactRef) -> bool:
        """Return whether an artifact still matches its recorded digest."""
        artifact_path = Path(ref.path)
        if not artifact_path.exists():
            return False
        if artifact_path.stat().st_size != ref.size_bytes:
            return False
        return verify_file(artifact_path, ref.hash)

    def find_by_hash(self, artifact_hash: str) -> ArtifactRef | None:
        """Resolve an artifact reference from its content hash."""
        matches = sorted(self._artifact_root.glob(f"{artifact_hash}.*"))
        if not matches:
            return None
        artifact_path = matches[0]
        return ArtifactRef(
            path=str(artifact_path),
            hash=artifact_hash,
            size_bytes=artifact_path.stat().st_size,
            description=None,
        )
