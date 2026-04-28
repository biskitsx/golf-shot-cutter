from fastapi import Cookie, HTTPException, Request

from app.repository.auth.jwt_repository import JwtVerifyError

_DEV_USERS = {"dev@local": "dev"}  # Plan 5 replaces with real user store


def authenticate(email: str, password: str) -> str | None:
    if _DEV_USERS.get(email) == password:
        return email
    return None


def current_user_id(request: Request, auth: str | None = Cookie(default=None)) -> str:
    if not auth:
        raise HTTPException(status_code=401, detail="not_authenticated")
    container = request.app.state.container
    jwt = container.jwt if hasattr(container, "jwt") else container.jwt_repo()
    try:
        payload = jwt.verify(auth)
    except JwtVerifyError as e:
        raise HTTPException(status_code=401, detail="invalid_token") from e
    return payload.subject
