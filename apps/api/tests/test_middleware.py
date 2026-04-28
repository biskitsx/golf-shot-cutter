from fastapi.testclient import TestClient


def test_request_id_round_trip(client: TestClient):
    r = client.get("/health", headers={"X-Request-Id": "rid-abc"})
    assert r.headers["X-Request-Id"] == "rid-abc"


def test_request_id_generated_when_missing(client: TestClient):
    r = client.get("/health")
    assert "X-Request-Id" in r.headers
    assert len(r.headers["X-Request-Id"]) >= 16
