"""Prometheus metrics for the classifier service.

Metrics are created at import time so they are registered exactly once per
process, however many apps the test suite builds. No metric carries the
scored text or anything derived from it beyond the score. Label values must
never come from request data: only route templates and the served model's card.
"""

from fastapi import FastAPI
from prometheus_client import Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics

from app.model import ModelBundle

INFERENCE_SECONDS = Histogram(
    "promptguard_ml_inference_seconds",
    "Time spent in ModelBundle.predict for one text.",
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
)

# Distribution of P(injection). Together with the gateway's thresholds this
# shows how much traffic sits near the block/review boundaries. The 0.6 and 0.9
# edges match the gateway's DEFAULT review/block thresholds
# (CLASSIFIER_REVIEW_THRESHOLD / CLASSIFIER_BLOCK_THRESHOLD, configured on the
# gateway, not here). Prometheus buckets are `le` while the gateway compares
# `>=`, so a score of exactly a threshold counts below it. Revisit the buckets
# if the thresholds are moved.
SCORE = Histogram(
    "promptguard_ml_score",
    "P(injection) returned by /classify.",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

MODEL_INFO = Gauge(
    "promptguard_ml_model_info",
    "Always 1; the labels identify the artifact being served.",
    labelnames=("model_version", "stub"),
)

# The library builds its default HTTP collectors inside each app's middleware,
# and on a second app in the same process it hits the registry's
# duplicate-series error and silently instruments nothing. Building them once
# here and handing the same closure to every app keeps all apps instrumented.
_HTTP_METRICS = metrics.default()


def record_model(bundle: ModelBundle) -> None:
    """Publish which artifact this process serves.

    Clears any previous label set first so only one series is ever live,
    even if a second bundle is loaded in the same process.
    """
    MODEL_INFO.clear()
    MODEL_INFO.labels(
        model_version=bundle.version, stub=str(bundle.is_stub).lower()
    ).set(1)


def setup_metrics(app: FastAPI) -> None:
    """Instrument HTTP traffic and expose GET /metrics on `app`."""
    instrumentator = Instrumentator(excluded_handlers=["^/metrics$"]).add(_HTTP_METRICS)
    instrumentator.instrument(app).expose(app, include_in_schema=False)
