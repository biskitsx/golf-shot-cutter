from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def _ready_session_with_two_auto_shots(client: TestClient) -> str:
    """Helper: create session, mark session ready by directly seeding container."""
    create = client.post("/sessions", json={"originalFilename": "a.mp4"})
    sid = create.json()["data"]["sessionId"]

    from datetime import UTC, datetime

    from app.core.models.session import SessionStatus
    from app.core.models.shot import Shot, ShotSource
    from app.core.models.value_objects import Confidence

    container = client.app.state.container
    sessions = container.sessions_repo()
    shots = container.shots_repo()
    s = sessions._items[sid]  # noqa: SLF001
    sessions._items[sid] = s.model_copy(  # noqa: SLF001
        update={"status": SessionStatus.READY, "shot_count": 2}
    )
    now = datetime(2026, 4, 28, tzinfo=UTC)
    for i in (1, 2):
        shots._items[f"shot_{i}"] = Shot(  # noqa: SLF001
            id=f"shot_{i}",
            session_id=sid,
            index=i,
            t_impact=10.0 * i,
            t_start=8.0 * i,
            t_end=15.0 * i,
            confidence=Confidence(value=0.9),
            source=ShotSource.AUTO,
            clip_key=None,
            created_at=now,
            updated_at=now,
        )
    return sid


def test_update_shot_boundary(client: TestClient):
    _login(client)
    sid = _ready_session_with_two_auto_shots(client)
    r = client.patch(
        f"/sessions/{sid}/shots/shot_1",
        json={"tStart": 7.0, "tEnd": 16.0},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["tStart"] == 7.0
    assert body["tEnd"] == 16.0


def test_update_shot_boundary_invalid_window_returns_422(client: TestClient):
    _login(client)
    sid = _ready_session_with_two_auto_shots(client)
    r = client.patch(
        f"/sessions/{sid}/shots/shot_1",
        json={"tStart": 11.0, "tEnd": 12.0},  # impact 10 outside [11,12]
    )
    assert r.status_code == 422


def test_add_manual_shot(client: TestClient):
    _login(client)
    sid = _ready_session_with_two_auto_shots(client)
    r = client.post(
        f"/sessions/{sid}/shots",
        json={"tImpact": 100.0, "tStart": 98.0, "tEnd": 105.0},
    )
    assert r.status_code == 201
    body = r.json()["data"]
    assert body["index"] == 3
    assert body["source"] == "manual"


def test_delete_shot(client: TestClient):
    _login(client)
    sid = _ready_session_with_two_auto_shots(client)
    r = client.delete(f"/sessions/{sid}/shots/shot_1")
    assert r.status_code == 204
    detail = client.get(f"/sessions/{sid}").json()["data"]
    assert {s["id"] for s in detail["shots"]} == {"shot_2"}


def test_update_unauthenticated(client: TestClient):
    r = client.patch("/sessions/x/shots/y", json={"tStart": 1.0, "tEnd": 2.0})
    assert r.status_code == 401
