from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def test_upload_url_for_existing_session(client: TestClient):
    _login(client)
    create = client.post("/sessions", json={"originalFilename": "x.mp4"})
    sid = create.json()["data"]["sessionId"]
    r = client.post(f"/sessions/{sid}/upload-url")
    assert r.status_code == 200
    body = r.json()["data"]
    assert "url" in body
    assert "expiresAt" in body


def test_upload_url_404_when_missing(client: TestClient):
    _login(client)
    r = client.post("/sessions/missing/upload-url")
    assert r.status_code == 404
