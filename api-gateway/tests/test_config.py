import pytest
from pydantic import ValidationError

from app.config import Settings

_VALID_SECRET = "test-secret-key-not-for-production-use"  # pragma: allowlist secret


def test_database_url_assembled_from_components():
    settings = Settings(
        postgres_user="u",
        postgres_password="p",
        postgres_host="h",
        postgres_port=5432,
        postgres_db="d",
    )
    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/d"


def test_auth_settings_defaults():
    settings = Settings(
        postgres_user="u",
        postgres_password="p",
        postgres_db="d",
        proxy_secret_key=_VALID_SECRET,
    )
    assert settings.proxy_secret_key == _VALID_SECRET
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 30


def test_short_proxy_secret_key_is_rejected():
    with pytest.raises(ValidationError):
        Settings(
            postgres_user="u",
            postgres_password="p",
            postgres_db="d",
            proxy_secret_key="short",  # pragma: allowlist secret
        )


def test_classifier_defaults():
    settings = Settings()
    assert settings.classifier_url == "http://ml:7000"
    assert settings.classifier_timeout_seconds == 2.0
    assert settings.classifier_block_threshold == 0.90
    assert settings.classifier_review_threshold == 0.60


def test_block_threshold_below_review_threshold_is_rejected(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_BLOCK_THRESHOLD", "0.2")
    monkeypatch.setenv("CLASSIFIER_REVIEW_THRESHOLD", "0.8")
    with pytest.raises(ValidationError, match="review"):
        Settings()


@pytest.mark.parametrize("value", ["-0.1", "1.1"])
def test_thresholds_outside_the_unit_interval_are_rejected(monkeypatch, value):
    monkeypatch.setenv("CLASSIFIER_BLOCK_THRESHOLD", value)
    with pytest.raises(ValidationError):
        Settings()


async def test_classifier_client_is_available_to_requests(app):
    from app.classifier import ClassifierClient

    assert isinstance(app.state.classifier_client, ClassifierClient)
