from fastapi.testclient import TestClient


def test_login_sets_cookie(client: TestClient):
    r = client.post("/auth/login", json={"email": "dev@local", "password": "dev"})
    assert r.status_code == 204
    assert r.cookies.get("auth")  # cookie was set


def test_logout_clears_cookie(client: TestClient):
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})
    r = client.post("/auth/logout")
    assert r.status_code == 204
    set_cookie = r.headers.get("set-cookie", "")
    assert "auth=" in set_cookie and "Max-Age=0" in set_cookie


def test_me_requires_auth(client: TestClient):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_returns_subject_when_authenticated(client: TestClient):
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["userId"] == "dev@local"
