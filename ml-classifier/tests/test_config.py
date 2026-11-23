import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas import ClassifyResponse


def test_settings_defaults():
    settings = Settings()
    assert settings.model_dir == "models/xlm-roberta-pi"
    assert settings.model_card_path == "models/xlm-roberta-pi.card.json"
    assert settings.classifier_max_text_chars == 32000
    assert settings.classifier_max_windows == 8
    assert settings.classifier_max_concurrency == 1
    assert settings.classifier_torch_threads is None


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("MODEL_DIR", "/models/x")
    monkeypatch.setenv("MODEL_CARD_PATH", "/models/x.card.json")
    monkeypatch.setenv("CLASSIFIER_MAX_TEXT_CHARS", "500")
    monkeypatch.setenv("CLASSIFIER_MAX_WINDOWS", "4")
    monkeypatch.setenv("CLASSIFIER_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("CLASSIFIER_TORCH_THREADS", "3")
    settings = Settings()
    assert settings.model_dir == "/models/x"
    assert settings.model_card_path == "/models/x.card.json"
    assert settings.classifier_max_text_chars == 500
    assert settings.classifier_max_windows == 4
    assert settings.classifier_max_concurrency == 2
    assert settings.classifier_torch_threads == 3


@pytest.mark.parametrize(
    "name",
    [
        "CLASSIFIER_MAX_WINDOWS",
        "CLASSIFIER_MAX_CONCURRENCY",
        "CLASSIFIER_TORCH_THREADS",
    ],
)
def test_counts_must_be_positive(monkeypatch, name):
    monkeypatch.setenv(name, "0")
    with pytest.raises(ValidationError):
        Settings()


def test_classify_response_allows_model_version_field():
    # pydantic v2 reserves the `model_` prefix; without protected_namespaces=()
    # this field name raises a UserWarning at class definition time.
    response = ClassifyResponse(label="clean", score=0.1, model_version="stub-0")
    assert response.model_version == "stub-0"
