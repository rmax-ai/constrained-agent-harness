"""Application settings using pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with layered precedence.

    Precedence (highest first):
    1. CLI flags
    2. Goal contract
    3. Environment variables
    4. pyproject.toml [tool.cah] section
    5. Defaults
    """

    model_config = SettingsConfigDict(
        env_prefix="CAH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Model
    model: str = "gemini-3.5-flash"

    # Google AI / Vertex AI
    google_api_key: str | None = None
    google_cloud_project: str | None = None
    google_cloud_location: str | None = None
    use_vertex_ai: bool = False

    # Paths
    runtime_dir: Path = Path(".cah")
    database_url: str = "sqlite:///.cah/cah.db"

    # Sandbox
    default_sandbox_image: str = "python:3.13-slim"

    # Logging
    log_level: str = "INFO"

    def resolve_model(self, goal_model: str | None = None, cli_model: str | None = None) -> str:
        """Resolve model with precedence: CLI > goal contract > env > default."""
        return cli_model or goal_model or self.model or "gemini-3.5-flash"
