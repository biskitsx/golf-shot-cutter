import pytest

from golf_infrastructure.settings import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://test:27017")
    monkeypatch.setenv("MONGODB_DATABASE", "golf_test")
    monkeypatch.setenv("REDIS_URL", "redis://test:6379/0")
    monkeypatch.setenv("R2_ENDPOINT", "https://r2.test")
    monkeypatch.setenv("R2_ACCESS_KEY", "ak")
    monkeypatch.setenv("R2_SECRET_KEY", "sk")
    monkeypatch.setenv("R2_BUCKET", "golf-test")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "golf-shot-cutter")
    s = Settings()
    assert s.mongodb_database == "golf_test"
    assert s.r2_bucket == "golf-test"
    assert s.jwt_issuer == "golf-shot-cutter"
    assert s.signed_url_ttl_seconds == 900  # default


def test_settings_missing_required_raises(monkeypatch):
    for var in [
        "MONGODB_URI",
        "MONGODB_DATABASE",
        "REDIS_URL",
        "R2_ENDPOINT",
        "R2_ACCESS_KEY",
        "R2_SECRET_KEY",
        "R2_BUCKET",
        "JWT_SECRET",
        "JWT_ISSUER",
    ]:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(Exception):
        Settings()
