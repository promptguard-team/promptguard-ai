from app.config import Settings
from app.schemas import ClassifyResponse


def test_settings_defaults():
    settings = Settings()
    assert settings.model_path == "models/stub-tfidf-0.1.0.joblib"
    assert settings.classifier_max_text_chars == 32000


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("MODEL_PATH", "models/other.joblib")
    monkeypatch.setenv("CLASSIFIER_MAX_TEXT_CHARS", "500")
    settings = Settings()
    assert settings.model_path == "models/other.joblib"
    assert settings.classifier_max_text_chars == 500


def test_classify_response_allows_model_version_field():
    # pydantic v2 reserves the `model_` prefix; without protected_namespaces=()
    # this field name raises a UserWarning at class definition time.
    response = ClassifyResponse(label="clean", score=0.1, model_version="stub-0")
    assert response.model_version == "stub-0"
