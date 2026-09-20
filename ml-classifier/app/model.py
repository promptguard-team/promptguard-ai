import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import sklearn


class ModelLoadError(RuntimeError):
    """The model artifact is missing, unreadable, or failed validation."""


@dataclass(frozen=True)
class Prediction:
    """One scored text."""

    label: str
    score: float


class ModelBundle:
    """The only component that knows scikit-learn is underneath."""

    def __init__(self, pipeline: Any, card: dict[str, Any]) -> None:
        self._pipeline = pipeline
        self._card = card
        classes = [str(c) for c in pipeline.classes_]
        if "injection" not in classes:
            raise ModelLoadError(
                f"model classes {classes} do not include 'injection'"
            )
        self._classes = classes
        self._injection_idx = classes.index("injection")

    @property
    def version(self) -> str:
        return str(self._card["model_version"])

    @property
    def is_stub(self) -> bool:
        return bool(self._card.get("stub", False))

    def predict(self, text: str) -> Prediction:
        """Return the argmax label and P(injection) for one text."""
        proba = self._pipeline.predict_proba([text])[0]
        return Prediction(
            label=self._classes[int(proba.argmax())],
            score=float(proba[self._injection_idx]),
        )

    @classmethod
    def load(cls, model_path: Path) -> "ModelBundle":
        """Load and validate an artifact, or raise ModelLoadError."""
        card_path = model_path.parent / f"{model_path.stem}.card.json"
        if not card_path.is_file():
            raise ModelLoadError(f"model card not found at {card_path}")
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ModelLoadError(f"unreadable model card at {card_path}") from exc

        model_version = card.get("model_version")
        if not isinstance(model_version, str) or not model_version:
            # Task 4 reads bundle.version on every request; a card missing
            # this must fail at load time rather than 500 on each call.
            raise ModelLoadError(
                f"model card at {card_path} is missing 'model_version'"
            )

        declared = card.get("environment", {}).get("scikit-learn")
        if declared != sklearn.__version__:
            raise ModelLoadError(
                f"model card declares scikit-learn {declared!r}, "
                f"but {sklearn.__version__!r} is installed; "
                "scikit-learn does not support loading pickles across versions"
            )

        try:
            # Loading a pickle executes arbitrary code from the file, so
            # artifacts enter this repository only through a reviewed pull
            # request. Bandit does not flag joblib.load (B301 covers
            # pickle/dill/shelve), so there is nothing here to suppress.
            pipeline = joblib.load(model_path)
        except Exception as exc:  # noqa: BLE001 - any failure here is fatal
            raise ModelLoadError(f"could not load artifact at {model_path}") from exc

        if not hasattr(pipeline, "predict_proba") or not hasattr(pipeline, "classes_"):
            raise ModelLoadError(
                "artifact must expose predict_proba() and classes_ "
                "(deliver an sklearn Pipeline with preprocessing inside)"
            )
        return cls(pipeline, card)
