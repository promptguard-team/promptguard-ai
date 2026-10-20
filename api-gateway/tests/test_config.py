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


@pytest.mark.parametrize(
    "field", ["classifier_block_threshold", "classifier_review_threshold"]
)
@pytest.mark.parametrize("value", ["-0.1", "1.1"])
def test_thresholds_outside_the_unit_interval_are_rejected(monkeypatch, field, value):
    monkeypatch.setenv(field.upper(), value)
    # Match the range-check message specifically (`"{field} must be within
    # [0,1]"`), not just any ValidationError: the block-below-review rule
    # also mentions classifier_review_threshold in its own message, so a
    # looser match would pass even if the range check for this field were
    # deleted from the validator.
    with pytest.raises(ValidationError, match=rf"{field} must be within \[0,1\]"):
        Settings()


async def test_classifier_client_is_available_to_requests(app):
    from app.classifier import ClassifierClient
    from app.deps import get_classifier_client

    class _FakeRequest:
        def __init__(self, app):
            self.app = app

    dependency_result = get_classifier_client(_FakeRequest(app))

    assert isinstance(dependency_result, ClassifierClient)
    # Identity, not just type: a dependency that returned some other
    # ClassifierClient (e.g. a copy-paste of get_llm_client reading the
    # wrong state attribute) would still pass an isinstance-only check.
    assert dependency_result is app.state.classifier_client


@pytest.mark.parametrize("value", ["0", "-1"])
def test_non_positive_classifier_timeout_is_rejected(monkeypatch, value):
    # anyio.fail_after(0) raises before the request is sent, so every call
    # would become a recorded fail-open: Layer 2 off, audit full of
    # ml_status=unavailable, and nothing anywhere reporting a problem.
    monkeypatch.setenv("CLASSIFIER_TIMEOUT_SECONDS", value)
    with pytest.raises(ValidationError, match="classifier_timeout_seconds"):
        Settings()
