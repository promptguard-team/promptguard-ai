"""Prometheus exposition for the gateway.

Values are read straight from the process-wide registry and compared as
deltas, so test order and the number of apps built in this process do not
matter.
"""

from httpx import ASGITransport, AsyncClient
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
    assert "http_requests_total" in resp.text


async def test_metrics_endpoint_is_hidden_from_openapi(client):
    resp = await client.get("/openapi.json")
    assert "/metrics" not in resp.json()["paths"]


async def test_http_requests_are_counted_by_route_template(client):
    labels = {"handler": "/health", "method": "GET", "status": "2xx"}
    before = sample("http_requests_total", labels)
    await client.get("/health")
    assert sample("http_requests_total", labels) == before + 1


async def test_every_app_in_the_process_is_instrumented():
    # The test suite (and app.main at import) builds many apps per process; a
    # regression here leaves every app after the first silently unmeasured.
    labels = {"handler": "/health", "method": "GET", "status": "2xx"}
    for _ in range(2):
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            before = sample("http_requests_total", labels)
            await c.get("/health")
            assert sample("http_requests_total", labels) == before + 1
