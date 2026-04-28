from fastapi.testclient import TestClient


def test_request_id_round_trip(client: TestClient):
    r = client.get("/health", headers={"X-Request-Id": "rid-abc"})
    assert r.headers["X-Request-Id"] == "rid-abc"


def test_request_id_generated_when_missing(client: TestClient):
    r = client.get("/health")
    assert "X-Request-Id" in r.headers
    assert len(r.headers["X-Request-Id"]) >= 16


def test_cors_preflight_returns_allow_headers(client: TestClient):
    r = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Request-Id",
        },
    )
    assert r.status_code == 200
    assert "access-control-allow-origin" in r.headers
