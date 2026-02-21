"""
app/core/config.py
──────────────────
Central settings loaded from .env (or environment variables).
Import `settings` anywhere in the app — never import os.environ directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MongoDB
    mongodb_uri:     str = "mongodb://localhost:27017"
    mongodb_db_name: str = "spacesync"
    mongodb_required: bool = True

    # Serial
    serial_baud:    int = 9600
    serial_timeout: int = 2

    # Data collection
    snapshot_interval: int = 60    # seconds between DB snapshots
    history_maxlen:    int = 200   # in-memory history per desk

    # Mock data
    jitter_interval: int = 3       # seconds between mock updates
    simulation_enabled: bool = False

    # App
    log_level: str = "INFO"


settings = Settings()
