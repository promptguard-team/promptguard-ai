"""Locations of the committed artifact, shared by tests and conftest."""

from pathlib import Path

MODELS = Path(__file__).resolve().parents[1] / "models"
ARTIFACT = MODELS / "stub-tfidf-0.1.0.joblib"
CARD = MODELS / "stub-tfidf-0.1.0.card.json"
