from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str

    proxy_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    llm_api_base: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0

    classifier_url: str = "http://ml:7000"
    classifier_timeout_seconds: float = 2.0
    classifier_block_threshold: float = 0.90
    classifier_review_threshold: float = 0.60

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection URL (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @model_validator(mode="after")
    def _check_thresholds(self) -> "Settings":
        """Reject a threshold configuration that would silently collapse the
        review band: if block < review, everything flagged for review would
        already have been blocked, with no error to signal the mistake.
        """
        for name, value in (
            ("classifier_block_threshold", self.classifier_block_threshold),
            ("classifier_review_threshold", self.classifier_review_threshold),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0,1], got {value}")
        if self.classifier_block_threshold < self.classifier_review_threshold:
            raise ValueError(
                "classifier_block_threshold must be >= classifier_review_threshold"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
