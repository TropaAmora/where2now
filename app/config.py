"""Application settings and environment configuration."""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration loaded from environment and .env."""

    # General
    ENV: str = "dev"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./where2now.db"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_TO_FILE: bool = True
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_TO_DB: bool = False
    LOG_DB_LEVEL: str = "WARNING"

    # External APIs (future use, e.g. Google Maps/geocoding)
    GOOGLE_MAPS_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton settings instance used across the application
settings = Settings()

