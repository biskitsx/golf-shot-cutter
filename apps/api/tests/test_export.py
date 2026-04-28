from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def test_export_requires_ready_session(client: TestClient):
    _login(client)
    create = client.post("/sessions", json={"originalFilename": "x.mp4"})
    sid = create.json()["sessionId"]
    # session is in UPLOADING, not READY → assert_editable fails → 409
    r = client.post(f"/sessions/{sid}/export")
    assert r.status_code == 409


def test_export_when_ready_returns_signed_get_url(client: TestClient):
    from datetime import UTC, datetime

    from golf_domain.session import SessionStatus

    _login(client)
    create = client.post("/sessions", json={"originalFilename": "x.mp4"})
    sid = create.json()["sessionId"]
    container = client.app.state.container
    s = container.sessions_repo._items[sid]  # noqa: SLF001
    container.sessions_repo._items[sid] = s.model_copy(  # noqa: SLF001
        update={"status": SessionStatus.READY, "updated_at": datetime(2026, 4, 28, tzinfo=UTC)}
    )
    r = client.post(f"/sessions/{sid}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["exportId"].startswith("exp_")
    assert "signedDownloadUrl" in body
