from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )

    model_dir: str = "models/xlm-roberta-pi"
    model_card_path: str = "models/xlm-roberta-pi.card.json"
    classifier_max_text_chars: int = 32000
    # Windows scored per request; bounds latency on very long prompts. The default
    # of 3 fits the gateway budget at 2 CPUs (measured, see README "Latency").
    classifier_max_windows: int = Field(3, ge=1)
    # Inferences allowed at once; extra requests queue instead of sharing the CPU.
    classifier_max_concurrency: int = Field(1, ge=1)
    # Longest a request may wait for an inference slot. The gateway gives up
    # after 2 s, so a request still queued past this is abandoned by its caller
    # anyway; do not spend an inference on it.
    classifier_queue_timeout_seconds: float = Field(1.5, gt=0)
    # torch intra-op threads; None keeps torch's own default.
    classifier_torch_threads: int | None = Field(None, ge=1)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
