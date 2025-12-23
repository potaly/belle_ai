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
    app_version: str = "5.3.0"
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

    # Embedding settings (V2+)
    # If not set, will fall back to LLM settings
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-v2"  # 阿里百炼默认嵌入模型，支持中英文双语

    # API settings
    api_v1_prefix: str = "/api/v1"

    # Logging settings
    log_level: str = "info"  # debug, info, warning, error

    # Debug settings
    debug: bool = False  # Enable debug mode (DEBUG=true in .env)
    
    # Intent engine thresholds (conservative defaults)
    intent_min_stay_for_high: int = 60  # Minimum stay time for high intent (with strong signals)
    intent_min_visits_for_high_with_favorite: int = 2  # Min visits + favorite for high
    intent_min_visits_for_hesitating: int = 3  # Min visits for hesitating
    intent_min_stay_for_hesitating: int = 20  # Min stay for hesitating
    intent_min_visits_for_medium: int = 2  # Min visits for medium
    intent_min_stay_for_medium: int = 15  # Min stay for medium
    intent_max_stay_for_low: int = 10  # Max stay for low (single visit)
    
    # Copy generation settings (V5.3.0+)
    copy_max_length: int = 45  # Maximum length for private-chat sales copy (characters)
    
    # Vision model settings (V6.0.0+)
    vision_model: str = "qwen-vl-max"  # Vision model name
    vision_api_key: str | None = None  # Vision model API key
    vision_base_url: str | None = None  # Vision model base URL
    use_mock_vision: bool = False  # Use mock vision provider (for testing)

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

