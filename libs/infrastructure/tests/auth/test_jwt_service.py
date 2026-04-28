import pytest

from golf_infrastructure.auth.jwt_service import JwtService, JwtVerifyError


def _service() -> JwtService:
    return JwtService(secret="x" * 32, issuer="golf-test", ttl_seconds=60)


def test_round_trip_token_returns_subject():
    s = _service()
    token = s.issue(subject="u_1")
    payload = s.verify(token)
    assert payload.subject == "u_1"


def test_verify_rejects_tampered_token():
    s = _service()
    token = s.issue(subject="u_1")
    bad = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(JwtVerifyError):
        s.verify(bad)


def test_verify_rejects_wrong_issuer():
    issued = _service().issue(subject="u_1")
    other = JwtService(secret="x" * 32, issuer="other", ttl_seconds=60)
    with pytest.raises(JwtVerifyError):
        other.verify(issued)
