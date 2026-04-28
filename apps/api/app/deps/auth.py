from dependency_injector.wiring import Provide, inject
from fastapi import Cookie, Depends, HTTPException

from app.core.container import Container
from app.repository.auth.jwt_repository import JwtRepository, JwtVerifyError


_DEV_USERS = {"dev@local": "dev"}  # Plan 5 replaces with real user store


def authenticate(email: str, password: str) -> str | None:
    if _DEV_USERS.get(email) == password:
        return email
    return None


@inject
def current_user_id(
    auth: str | None = Cookie(default=None),
    jwt_repo: JwtRepository = Depends(Provide[Container.jwt_repo]),
) -> str:
    if not auth:
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        payload = jwt_repo.verify(auth)
    except JwtVerifyError as e:
        raise HTTPException(status_code=401, detail="invalid_token") from e
    return payload.subject
