from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.deps.auth import authenticate, current_user_id

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_NAME = "auth"


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https"


def _get_jwt(request: Request):
    container = request.app.state.container
    return container.jwt if hasattr(container, "jwt") else container.jwt_repo()


@router.post("/login", status_code=204)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
) -> None:
    user_id = authenticate(req.email, req.password)
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    jwt = _get_jwt(request)
    token = jwt.issue(subject=user_id)
    response.set_cookie(
        _COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        max_age=jwt._ttl,  # noqa: SLF001
    )


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(_COOKIE_NAME)


@router.get("/me")
async def me(user_id: str = Depends(current_user_id)) -> dict[str, str]:
    return {"userId": user_id}
