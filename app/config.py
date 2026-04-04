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

    # Google Maps
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    GOOGLE_DISTANCE_MATRIX_BASE_URL: str = "https://maps.googleapis.com/maps/api/distancematrix/json"
    GOOGLE_DISTANCE_MATRIX_TIMEOUT: float = 10.0
    GOOGLE_DISTANCE_MATRIX_MAX_RETRIES: int = 2

    # Geocoding
    GEOCODER_ENABLED: bool = True
    GEOCODER_PROVIDER: str = "nominatim" # use "nominatim", "geoapify" or "google"
    GEOCODER_TIMEOUT: float = 5.0
    GEOCODER_API_KEY: str | None = None

    # Travel time subsystem
    TRAVEL_TIME_PROVIDERS: str = "google"
    TRAVEL_TIME_STRATEGY: str = "single"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton settings instance used across the application
settings = Settings()

