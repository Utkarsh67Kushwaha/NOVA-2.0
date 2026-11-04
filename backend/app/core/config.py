from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable override support."""

    APP_NAME: str = "NOVA Desktop Assistant"
    VERSION: str = "0.1.0"
    NOVA_ENV: str = "development"

    # Server binding
    NOVA_HOST: str = "127.0.0.1"
    NOVA_PORT: int = 8000

    # Logging
    LOG_LEVEL: str = "INFO"
    LOGS_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent / "logs"

    # CORS origins for local UI
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
