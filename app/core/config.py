"""Application configuration using Pydantic BaseSettings."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Load .env with fallback encodings to avoid Unicode errors."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            load_dotenv(dotenv_path=env_path, encoding=encoding, override=False)
            return
        except UnicodeDecodeError:
            continue
    logger.warning("Failed to decode .env; using process env vars only.")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "AI Smart Guide Service"
    app_version: str = "1.0.0"
    app_env: str = "dev"  # Environment: dev, test, prod

    # Database settings
    database_url: str = "mysql+pymysql://root:password@localhost:3306/belle_ai?charset=utf8mb4"
    mysql_echo: str = "false"  # SQLAlchemy echo setting

    # Redis settings (optional)
    redis_url: str | None = None

    # LLM settings
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "mock-llm"

    # API settings
    api_v1_prefix: str = "/api/v1"

    # Logging settings
    log_level: str = "info"  # debug, info, warning, error

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


# Load .env file on module import
_load_env_file()

