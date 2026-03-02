"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "FPL Team Picker"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # FPL API
    fpl_base_url: str = "https://fantasy.premierleague.com/api"
    fpl_rate_limit: float = 1.0  # requests per second

    # Cache
    cache_dir: str = ".cache"
    cache_bootstrap_ttl: int = 21600  # 6 hours
    cache_element_ttl: int = 14400  # 4 hours
    cache_fixtures_ttl: int = 86400  # 24 hours
    cache_live_ttl: int = 60  # 60 seconds
    cache_predictions_ttl: int = 3600  # 1 hour

    # Gemini Vision API
    gemini_api_key: str = ""

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = {"env_file": ".env", "env_prefix": "FPL_"}


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
