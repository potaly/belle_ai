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
    app_name: str = "AI Smart Guide Service"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "mock-llm"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


_load_env_file()