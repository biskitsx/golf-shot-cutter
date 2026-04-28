from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def test_create_session_returns_signed_url(client: TestClient):
    _login(client)
    r = client.post(
        "/sessions",
        json={
            "originalFilename": "range.mp4",
            "preRollSeconds": 2.0,
            "postRollSeconds": 5.0,
        },
    )
    assert r.status_code == 201
    body = r.json()["data"]
    assert body["sessionId"].startswith("ses_")
    assert "PUT" in body["signedUploadUrl"]
    assert "expiresAt" in body


def test_list_sessions_returns_only_caller_sessions(client: TestClient):
    _login(client)
    client.post("/sessions", json={"originalFilename": "a.mp4"})
    client.post("/sessions", json={"originalFilename": "b.mp4"})
    r = client.get("/sessions")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 2


def test_get_session_returns_session_and_shots(client: TestClient):
    _login(client)
    create = client.post("/sessions", json={"originalFilename": "a.mp4"})
    sid = create.json()["data"]["sessionId"]
    r = client.get(f"/sessions/{sid}")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["session"]["id"] == sid
    assert body["shots"] == []


def test_get_session_404_when_missing(client: TestClient):
    _login(client)
    r = client.get("/sessions/does_not_exist")
    assert r.status_code == 404


def test_create_session_unauthenticated_401(client: TestClient):
    r = client.post("/sessions", json={"originalFilename": "a.mp4"})
    assert r.status_code == 401


def test_start_processing_transitions_status(client: TestClient):
    _login(client)
    create = client.post("/sessions", json={"originalFilename": "a.mp4"})
    sid = create.json()["data"]["sessionId"]
    r = client.post(f"/sessions/{sid}/process")
    assert r.status_code == 202
    detail = client.get(f"/sessions/{sid}").json()["data"]
    assert detail["session"]["status"] == "processing"
