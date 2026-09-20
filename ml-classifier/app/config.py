from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )

    model_path: str = "models/stub-tfidf-0.1.0.joblib"
    classifier_max_text_chars: int = 32000


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
