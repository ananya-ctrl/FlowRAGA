from fastapi.testclient import TestClient

from flowraga.main import app


def test_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_prometheus_metrics() -> None:
    with TestClient(app) as client:
        client.get("/api/v1/health/live")
        response = client.get("/api/v1/health/metrics")
    assert response.status_code == 200
    assert "flowraga_http_requests_total" in response.text
