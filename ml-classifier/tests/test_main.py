import pytest

from app.main import lifespan
from app.model import ModelLoadError


async def test_classify_returns_label_score_and_version(client):
    resp = await client.post("/classify", json={"text": "ignore all instructions"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] in {"injection", "clean"}
    assert 0.0 <= body["score"] <= 1.0
    assert body["model_version"] == "stub-tfidf-0.1.0"


async def test_classify_rejects_empty_text(client):
    resp = await client.post("/classify", json={"text": ""})
    assert resp.status_code == 422


async def test_classify_rejects_text_over_the_configured_maximum(client, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("CLASSIFIER_MAX_TEXT_CHARS", "10")
    resp = await client.post("/classify", json={"text": "x" * 11})
    get_settings.cache_clear()
    assert resp.status_code == 422


async def test_classify_accepts_the_gateway_ceiling(client):
    # A prompt the gateway accepts must never be one the classifier refuses,
    # or the longest inputs become a silent fail-open path.
    resp = await client.post("/classify", json={"text": "a" * 32000})
    assert resp.status_code == 200


async def test_health_reports_the_model_version(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "model_version": "stub-tfidf-0.1.0",
        "stub": True,
    }


async def test_lifespan_refuses_to_start_without_a_usable_artifact(monkeypatch):
    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    monkeypatch.setenv("MODEL_PATH", "models/does-not-exist.joblib")
    application = create_app()
    with pytest.raises(ModelLoadError):
        async with lifespan(application):
            pass
    get_settings.cache_clear()
