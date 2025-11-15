"""Shared dependency utilities and settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings sourced from environment variables or .env."""

    app_env: str = Field(default="development", description="Current environment name")
    pg_dsn_ro: str = Field(default="postgres://codex:codex@127.0.0.1:5432/codex", description="Read-only Postgres DSN")
    neo4j_uri_ro: str = Field(default="bolt://127.0.0.1:7687", description="Read-only Neo4j URI")
    neo4j_user_ro: str = Field(default="neo4j", description="Read-only Neo4j user")
    neo4j_pass_ro: str = Field(default="codex1234", description="Read-only Neo4j password")
    project_root: Path = Field(default=Path(__file__).resolve().parents[1], description="Path to repository root")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
