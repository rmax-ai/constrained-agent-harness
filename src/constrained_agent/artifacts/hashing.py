"""Hashing helpers for artifacts and append-only evidence chains."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def hash_file(path: Path) -> str:
    """Return the SHA-256 digest for a file's contents."""
    digest = sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_bytes(data: bytes) -> str:
    """Return the SHA-256 digest for a byte string."""
    return sha256(data).hexdigest()


def hash_chain(previous_hash: str | None, payload: str) -> str:
    """Return SHA-256(previous || payload) with an empty prefix for the first link."""
    prefix = previous_hash or ""
    return sha256(f"{prefix}{payload}".encode()).hexdigest()


def verify_file(path: Path, expected_hash: str) -> bool:
    """Return whether a file's digest matches the expected hash."""
    return hash_file(path) == expected_hash
