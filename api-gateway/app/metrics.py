"""Prometheus metrics for the gateway.

Domain metrics are created at import time so they are registered exactly once
per process, however many apps `create_app()` builds (the test suite builds
one per test). Label values come from enums only; never put user ids, rule
names or prompt text in a label.
"""

from fastapi import FastAPI
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics

from app.models import AuditAction, MLStatus

CHAT_DECISIONS = Counter(
    "promptguard_chat_decisions_total",
    "Policy decision for each /chat request that reached the audit log.",
    labelnames=("action", "ml_status"),
)
# A labelled series does not exist until it is first touched; create all of
# them up front so dashboards and alerts see 0 rather than "no data".
for _action in AuditAction:
    for _status in MLStatus:
        CHAT_DECISIONS.labels(action=_action.value, ml_status=_status.value)

CHAT_FLAGGED = Counter(
    "promptguard_chat_flagged_total",
    "Prompts that were allowed but marked for CISO review.",
)

CLASSIFIER_REQUEST_SECONDS = Histogram(
    "promptguard_classifier_request_seconds",
    "Round trip to the ml-classifier service, including response validation.",
    labelnames=("outcome",),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
for _outcome in ("ok", "error"):
    CLASSIFIER_REQUEST_SECONDS.labels(outcome=_outcome)


# The library builds its default HTTP collectors inside each app's middleware,
# and on a second app in the same process it hits the registry's
# duplicate-series error and silently instruments nothing. Building them once
# here and handing the same closure to every app keeps all apps instrumented.
_HTTP_METRICS = metrics.default()


def setup_metrics(app: FastAPI) -> None:
    """Instrument HTTP traffic and expose GET /metrics on `app`."""
    instrumentator = Instrumentator(excluded_handlers=["^/metrics$"]).add(_HTTP_METRICS)
    instrumentator.instrument(app).expose(app, include_in_schema=False)
