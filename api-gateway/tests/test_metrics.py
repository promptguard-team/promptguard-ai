"""Prometheus exposition for the gateway.

Values are read straight from the process-wide registry and compared as
deltas, so test order and the number of apps built in this process do not
matter.
"""

from prometheus_client import REGISTRY

from app.main import create_app


def sample(name: str, labels: dict[str, str] | None = None) -> float:
    """Current value of one series, or 0.0 if it has never been observed."""
    value = REGISTRY.get_sample_value(name, labels or {})
    return 0.0 if value is None else value


async def test_metrics_endpoint_is_public_and_in_prometheus_format(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "# HELP" in resp.text


async def test_metrics_endpoint_is_hidden_from_openapi(client):
    resp = await client.get("/openapi.json")
    assert "/metrics" not in resp.json()["paths"]


async def test_http_requests_are_counted_by_route_template(client):
    labels = {"handler": "/health", "method": "GET", "status": "2xx"}
    before = sample("http_requests_total", labels)
    await client.get("/health")
    assert sample("http_requests_total", labels) == before + 1


def test_create_app_twice_does_not_collide_on_the_registry():
    create_app()
    create_app()
