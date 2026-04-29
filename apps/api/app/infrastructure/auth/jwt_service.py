from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from pydantic import BaseModel


class JwtVerifyError(Exception):
    pass


class JwtPayload(BaseModel):
    subject: str
    issued_at: datetime
    expires_at: datetime


class JwtService:
    ALGORITHM = "HS256"

    def __init__(self, *, secret: str, issuer: str, ttl_seconds: int) -> None:
        if len(secret) < 32:
            raise ValueError("JWT secret must be >= 32 chars")
        self._secret = secret
        self._issuer = issuer
        self._ttl = ttl_seconds

    def issue(self, *, subject: str) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": subject,
            "iss": self._issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._ttl)).timestamp()),
        }
        return jwt.encode(claims, self._secret, algorithm=self.ALGORITHM)

    def verify(self, token: str) -> JwtPayload:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self.ALGORITHM],
                issuer=self._issuer,
            )
        except JWTError as e:
            raise JwtVerifyError(str(e)) from e
        return JwtPayload(
            subject=claims["sub"],
            issued_at=datetime.fromtimestamp(claims["iat"], tz=UTC),
            expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
        )
